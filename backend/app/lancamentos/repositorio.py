"""Acesso a dados dos lançamentos. **Sem regra de negócio aqui** (Princípio IV).

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T053).
O que veio dela e está aplicado:

- **Parte sempre de `lancamentos_ativos`**, a view que já filtra o soft delete
  (Princípio III) — assim nenhuma consulta esquece o filtro.
- **Índices parciais casam com o filtro**: `lancamentos_mundo_data_idx` é
  `(mundo, data desc) where excluido_em is null`, exatamente a forma da consulta de
  lista.
- **Busca por texto usa `pg_trgm`** com `%` (similaridade), que usa o índice GIN. `like
  '%texto%'` não usaria.
- **Nenhum valor entra em SQL por concatenação.** O único trecho montado como texto é o
  `ORDER BY`, e ele vem de uma lista fechada (`app/comum/paginacao.py`).
- **Agregação numa passada só** com `filter (where …)`, em vez de uma consulta por
  número — é o que faz `resumo_filtrado` não custar três varreduras.

Tarefa: T053
"""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# Nome público → expressão SQL (contracts/lancamentos.md: data|valor|descricao|categoria|status)
COLUNAS_ORDENAVEIS: dict[str, str] = {
    "data": "l.data",
    "valor": "l.valor",
    "descricao": "lower(l.descricao)",
    "categoria": "lower(c.nome)",
    "status": "l.status",
}
ORDEM_PADRAO = "l.data"

# `RN-11`: o pai de um split sai dos totais. Fica num lugar só para lista, resumo e
# saldo aplicarem exatamente o mesmo recorte.
_SEM_PAI_DE_SPLIT = """
  not exists (select 1 from lancamentos p
              where p.lancamento_pai_id = l.id and p.excluido_em is null)
"""

_SELECAO = """
  l.id, l.mundo, l.tipo, l.descricao, l.valor, l.data, l.status,
  l.efetivar_automaticamente, l.efetivado_em, l.observacoes,
  l.moeda_origem, l.valor_origem, l.cotacao, l.cotacao_data, l.cotacao_manual,
  l.recorrencia_id, l.parcelamento_id, l.parcela_numero, l.parcela_total,
  l.lancamento_pai_id, l.versao, l.criado_em, l.criado_por, l.excluido_em,
  c.id as categoria_id, c.nome as categoria_nome, c.cor as categoria_cor,
  c.icone as categoria_icone, c.especial as categoria_especial, c.vinculo as categoria_vinculo,
  s.id as subcategoria_id, s.nome as subcategoria_nome, s.cor as subcategoria_cor,
  s.cliente_id as subcategoria_cliente_id, s.funcionario_id as subcategoria_funcionario_id,
  sv.id as servico_id, sv.nome as servico_nome, sv.mundo as servico_mundo,
  cc.id as centro_custo_id, cc.nome as centro_custo_nome, cc.mundo as centro_custo_mundo,
  -- `RF-013a`: o anexo fica no pai e as partes do split leem por herança. Contar só
  -- pelo próprio id faria a parte aparecer "sem comprovante" tendo um.
  (select count(*) from anexos a
   where a.lancamento_id = coalesce(l.lancamento_pai_id, l.id)) as quantidade_anexos,
  exists (select 1 from lancamentos p
          where p.lancamento_pai_id = l.id and p.excluido_em is null) as tem_partes
"""

_JUNCOES = """
  from lancamentos_ativos l
  join categorias c        on c.id  = l.categoria_id
  left join subcategorias s on s.id = l.subcategoria_id
  left join servicos sv     on sv.id = l.servico_id
  left join centros_custo cc on cc.id = l.centro_custo_id
"""


def monta_filtros(
    *,
    mundos: list[str],
    inicio: date | None = None,
    fim: date | None = None,
    tipo: str | None = None,
    categoria_ids: list[UUID] | None = None,
    subcategoria_ids: list[UUID] | None = None,
    servico_ids: list[UUID] | None = None,
    centro_custo_ids: list[UUID] | None = None,
    tag_ids: list[UUID] | None = None,
    status: list[str] | None = None,
    valor_min: Any = None,
    valor_max: Any = None,
    busca: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Os filtros combináveis de `FR-037`, como lista de condições e parâmetros.

    Cada filtro só entra na cláusula quando foi informado. Condição sempre presente com
    `(:param is null or …)` impede o Postgres de escolher o índice parcial certo.
    """
    condicoes = ["l.mundo = any(cast(:mundos as mundo[]))"]
    parametros: dict[str, Any] = {"mundos": mundos}

    if inicio is not None and fim is not None:
        condicoes.append("l.data between :inicio and :fim")
        parametros |= {"inicio": inicio, "fim": fim}
    if tipo:
        condicoes.append("l.tipo = cast(:tipo as tipo_lancamento)")
        parametros["tipo"] = tipo
    if categoria_ids:
        condicoes.append("l.categoria_id = any(cast(:categoria_ids as uuid[]))")
        parametros["categoria_ids"] = [str(x) for x in categoria_ids]
    if subcategoria_ids:
        condicoes.append("l.subcategoria_id = any(cast(:subcategoria_ids as uuid[]))")
        parametros["subcategoria_ids"] = [str(x) for x in subcategoria_ids]
    if servico_ids:
        condicoes.append("l.servico_id = any(cast(:servico_ids as uuid[]))")
        parametros["servico_ids"] = [str(x) for x in servico_ids]
    if centro_custo_ids:
        condicoes.append("l.centro_custo_id = any(cast(:centro_custo_ids as uuid[]))")
        parametros["centro_custo_ids"] = [str(x) for x in centro_custo_ids]
    if status:
        condicoes.append("l.status = any(cast(:status as status_lancamento[]))")
        parametros["status"] = status
    if valor_min is not None:
        condicoes.append("l.valor >= :valor_min")
        parametros["valor_min"] = valor_min
    if valor_max is not None:
        condicoes.append("l.valor <= :valor_max")
        parametros["valor_max"] = valor_max
    if tag_ids:
        condicoes.append(
            "exists (select 1 from lancamentos_tags lt "
            "where lt.lancamento_id = l.id and lt.tag_id = any(cast(:tag_ids as uuid[])))"
        )
        parametros["tag_ids"] = [str(x) for x in tag_ids]
    if busca:
        # `%` é o operador de similaridade do pg_trgm e usa o índice GIN.
        # `ilike '%x%'` faria varredura completa.
        #
        # Um `%` só, nunca `%%`: o dialeto asyncpg do SQLAlchemy usa parâmetro
        # numerado (`$1`), não `pyformat`, e por isso **não** desescapa `%%` —
        # o par ia literal para o Postgres e virava `operator does not exist:
        # text %% unknown`, um 500 em toda busca por texto.
        condicoes.append("(l.descricao % :busca or l.observacoes ilike :busca_like)")
        parametros |= {"busca": busca, "busca_like": f"%{busca}%"}

    return condicoes, parametros


async def lista(
    conexao: AsyncConnection,
    *,
    condicoes: list[str],
    parametros: dict[str, Any],
    ordem: str,
    limite: int,
    deslocamento: int,
) -> list[dict[str, Any]]:
    onde = " and ".join(condicoes)
    consulta = text(f"""
        select {_SELECAO}
        {_JUNCOES}
        where {onde}
        order by {ordem}, l.criado_em desc
        limit :limite offset :deslocamento
        """)
    linhas = (
        (
            await conexao.execute(
                consulta, parametros | {"limite": limite, "deslocamento": deslocamento}
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def conta_e_soma(
    conexao: AsyncConnection, *, condicoes: list[str], parametros: dict[str, Any]
) -> dict[str, Any]:
    """Contador e somas do **conjunto filtrado inteiro** (`FR-038`).

    Precisa vir do banco, não da página: somar só os 50 visíveis daria um número que
    contradiz o contador ao lado dele.
    """
    onde = " and ".join(condicoes)
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select
                      count(*) as quantidade,
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'receita' and l.status = 'efetivado' and {_SEM_PAI_DE_SPLIT}
                      ), 0) as total_receitas,
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'despesa' and l.status = 'efetivado' and {_SEM_PAI_DE_SPLIT}
                      ), 0) as total_despesas
                    from lancamentos_ativos l
                    where {onde}
                    """),
                parametros,
            )
        )
        .mappings()
        .one()
    )
    return dict(linha)


async def quebra_por_mundo(
    conexao: AsyncConnection, *, condicoes: list[str], parametros: dict[str, Any]
) -> dict[str, str]:
    """Resultado por mundo, para o modo "Ambos" (`FR-003`).

    Os dois mundos sempre aparecem, mesmo zerados — mundo sem movimento mostra zero em
    vez de sumir (edge case da spec).
    """
    onde = " and ".join(condicoes)
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.mundo,
                           coalesce(sum(
                             case when l.tipo = 'receita' then l.valor else -l.valor end
                           ) filter (where l.status = 'efetivado' and {_SEM_PAI_DE_SPLIT}), 0) as resultado
                    from lancamentos_ativos l
                    where {onde}
                    group by l.mundo
                    """),
                parametros,
            )
        )
        .mappings()
        .all()
    )
    resultado = {"digital": "0.00", "infra": "0.00"}
    for linha in linhas:
        resultado[linha["mundo"]] = f"{linha['resultado']:.2f}"
    return resultado


async def para_exportacao(
    conexao: AsyncConnection,
    *,
    condicoes: list[str],
    parametros: dict[str, Any],
    limite: int,
) -> list[dict[str, Any]]:
    """Linhas achatadas para o CSV (`FR-045`), com os mesmos filtros da lista.

    Nome em vez de id em toda coluna: o arquivo é lido por uma pessoa numa planilha,
    onde `uuid` não diz nada. As tags vêm concatenadas numa coluna só, porque CSV não
    tem lista.

    `string_agg` numa junção lateral evita repetir a linha do lançamento uma vez por
    tag — sem isso, um lançamento com 3 tags viraria 3 linhas no arquivo e as somas da
    planilha ficariam erradas.
    """
    onde = " and ".join(condicoes)
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.data, l.mundo, l.tipo, l.descricao, l.valor, l.status,
                           c.nome as categoria, s.nome as subcategoria,
                           sv.nome as servico, cc.nome as centro_custo,
                           coalesce(tg.tags, '') as tags,
                           l.moeda_origem, l.valor_origem, l.cotacao, l.observacoes
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    left join subcategorias s on s.id = l.subcategoria_id
                    left join servicos sv on sv.id = l.servico_id
                    left join centros_custo cc on cc.id = l.centro_custo_id
                    left join lateral (
                      select string_agg(t.nome, ', ' order by lower(t.nome)) as tags
                      from lancamentos_tags lt join tags t on t.id = lt.tag_id
                      where lt.lancamento_id = l.id
                    ) tg on true
                    where {onde}
                    order by l.data, l.criado_em
                    limit :limite_exportacao
                    """),
                parametros | {"limite_exportacao": limite},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def por_id(
    conexao: AsyncConnection, lancamento_id: UUID, *, incluir_excluido: bool = False
) -> dict[str, Any] | None:
    """Um lançamento. `incluir_excluido` só para a lixeira e a restauração."""
    origem = "lancamentos" if incluir_excluido else "lancamentos_ativos"
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select {_SELECAO}
                    from {origem} l
                    join categorias c        on c.id  = l.categoria_id
                    left join subcategorias s on s.id = l.subcategoria_id
                    left join servicos sv     on sv.id = l.servico_id
                    left join centros_custo cc on cc.id = l.centro_custo_id
                    where l.id = :id
                    """),
                {"id": str(lancamento_id)},
            )
        )
        .mappings()
        .first()
    )
    return dict(linha) if linha else None


async def tags_de(conexao: AsyncConnection, ids: list[UUID]) -> dict[str, list[dict[str, Any]]]:
    """Tags de vários lançamentos numa consulta só.

    Uma consulta por lançamento seria o problema N+1 que a Skill (`data-n-plus-one`)
    manda evitar: 50 linhas na página virariam 51 idas ao banco.
    """
    if not ids:
        return {}
    linhas = (
        (
            await conexao.execute(
                text("""
                    select lt.lancamento_id, t.id, t.nome, t.cor
                    from lancamentos_tags lt
                    join tags t on t.id = lt.tag_id
                    where lt.lancamento_id = any(cast(:ids as uuid[]))
                    order by lower(t.nome)
                    """),
                {"ids": [str(x) for x in ids]},
            )
        )
        .mappings()
        .all()
    )
    agrupadas: dict[str, list[dict[str, Any]]] = {}
    for linha in linhas:
        agrupadas.setdefault(str(linha["lancamento_id"]), []).append(
            {"id": str(linha["id"]), "nome": linha["nome"], "cor": linha["cor"]}
        )
    return agrupadas


async def saldo_por_mundo(conexao: AsyncConnection, mundos: list[str]) -> dict[str, Any]:
    """`RN-05` / `RN-16` — só `efetivado` entra, e o pai de split não conta.

    Sem recorte de período de propósito: saldo é acumulado desde o primeiro lançamento.
    Não existe saldo inicial (`FR-114`).
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.mundo,
                           coalesce(sum(l.valor) filter (where l.tipo = 'receita'), 0) as receitas,
                           coalesce(sum(l.valor) filter (where l.tipo = 'despesa'), 0) as despesas
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.status = 'efetivado'
                      and {_SEM_PAI_DE_SPLIT}
                    group by l.mundo
                    """),
                {"mundos": mundos},
            )
        )
        .mappings()
        .all()
    )
    return {linha["mundo"]: dict(linha) for linha in linhas}
