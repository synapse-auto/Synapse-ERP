"""Acesso a dados de clientes. **Sem regra de negócio aqui** (Princípio IV).

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T105).

## O filtro de mundo é derivado — e é a consequência de D-04

`clientes` **não tem coluna `mundo`** (2ª exceção documentada a `RN-15`, decisão do dono do
projeto). Então `?mundo=digital` não é um `where`: é "clientes com ao menos um lançamento
não excluído no mundo digital", calculado por `exists` sobre a subcategoria espelho.

E daí sai o caso que precisa de tratamento explícito: **cliente sem nenhum lançamento não
pertence a mundo nenhum**, e sumiria dos três estados do seletor. Ele aparece em todos, com
`sem_movimentacao: true`, para a tela poder explicar em vez de o usuário achar que o
cadastro se perdeu (`FR-002`).

Outras decisões vindas da Skill:

- **`exists` em vez de `join` + `distinct`** no filtro de movimentação: para com a primeira
  linha que casa, e não materializa o conjunto inteiro para depois deduplicar.
- **Agregações por `left join lateral`**, não uma consulta por cliente — o N+1 aqui seria
  50 idas ao banco numa lista de 50.
- **Nenhum valor entra em SQL por concatenação.**

Tarefa: T105
"""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# A movimentação de um cliente é a dos lançamentos da subcategoria espelho dele.
_TEM_MOVIMENTACAO_NO_MUNDO = """
  exists (
    select 1
    from lancamentos_ativos l
    join subcategorias s on s.id = l.subcategoria_id
    where s.cliente_id = c.id
      and l.mundo = any(cast(:mundos as mundo[]))
  )
"""

_SEM_MOVIMENTACAO_NENHUMA = """
  not exists (
    select 1 from lancamentos_ativos l
    join subcategorias s on s.id = l.subcategoria_id
    where s.cliente_id = c.id
  )
"""

# `RN-11`: o pai de um split não conta, só as partes. Vale nas **somas** e no
# `em_aberto` que alimenta a inadimplência — não no filtro de movimentação acima,
# onde a pergunta é "houve movimento", e pai de split também é movimento.
#
# Repetido aqui em vez de importado dos repositórios irmãos pelo mesmo motivo que
# eles repetem entre si: import entre repositórios cria dependência de camada que o
# Princípio IV não quer.
_SEM_PAI_DE_SPLIT = """
  not exists (select 1 from lancamentos p
              where p.lancamento_pai_id = l.id and p.excluido_em is null)
"""

# "Cliente desde" é **derivado**, não coluna — o mesmo raciocínio da situação de
# inadimplência (data-model §3.4): a data já está no dado, e gravá-la criaria uma
# segunda verdade para manter em dia quando um lançamento antigo é editado ou
# cancelado.
#
# É a receita **efetivada** mais antiga do cliente, limitada por baixo pela data de
# cadastro: um cliente novo, cuja primeira mensalidade só vence no mês que vem, é
# cliente desde hoje — não desde o mês que vem. `least` ignora `null`, então cada
# metade cobre o buraco da outra sem `coalesce` aninhado.
#
# Custo: uma varredura por índice em `lancamentos(subcategoria_id)` por linha, na
# página de 50 — a mesma forma correlacionada que `_SEM_MOVIMENTACAO_NENHUMA` já usa
# aqui. Não é ida ao banco extra, que é o que custa caro neste projeto (ver `db.py`).
_CLIENTE_DESDE = """
  least(
    c.criado_em::date,
    (select min(l.data)
       from lancamentos_ativos l
       join subcategorias s on s.id = l.subcategoria_id
      where s.cliente_id = c.id
        and l.tipo = 'receita'
        and l.status = 'efetivado')
  ) as cliente_desde
"""

_SELECAO = f"""
  c.id, c.nome, c.empresa, c.contato_email, c.contato_telefone,
  c.tipo_cobranca, c.valor_recorrente, c.dia_cobranca, c.mundo_cobranca,
  c.observacoes, c.arquivado_em, c.criado_em,
  {_CLIENTE_DESDE}
"""


def monta_filtros(
    *,
    mundos: list[str],
    filtrando_por_mundo: bool,
    incluir_arquivados: bool,
    busca: str | None,
) -> tuple[list[str], dict[str, Any]]:
    condicoes: list[str] = []
    parametros: dict[str, Any] = {"mundos": mundos}

    if not incluir_arquivados:
        condicoes.append("c.arquivado_em is null")

    if filtrando_por_mundo:
        # O `or` é a regra de D-04, não uma folga: cliente sem lançamento nenhum
        # aparece nos três estados do seletor.
        condicoes.append(f"({_TEM_MOVIMENTACAO_NO_MUNDO} or {_SEM_MOVIMENTACAO_NENHUMA})")

    if busca:
        # `%` (pg_trgm) uma vez só — ver a nota em lancamentos/repositorio.py.
        condicoes.append("(c.nome % :busca or c.empresa % :busca)")
        parametros["busca"] = busca

    return condicoes or ["true"], parametros


async def lista(
    conexao: AsyncConnection,
    *,
    condicoes: list[str],
    parametros: dict[str, Any],
    inicio: date,
    fim: date,
    limite: int,
    deslocamento: int,
) -> list[dict[str, Any]]:
    """Clientes com os totais e os lançamentos em aberto necessários à situação.

    Os lançamentos em aberto vêm **agregados em `jsonb`** numa junção lateral. Parece
    exótico e resolve um problema real: a situação de inadimplência é calculada em
    Python (`dominio/inadimplencia.py`, para ser testável sem banco), e sem isto seria
    uma consulta por cliente só para descobrir se ele está atrasado.
    """
    onde = " and ".join(condicoes)
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select {_SELECAO},
                           coalesce(t.historico, 0) as total_recebido_historico,
                           coalesce(t.periodo, 0) as total_recebido_periodo,
                           coalesce(a.em_aberto, '[]'::jsonb) as em_aberto,
                           {_SEM_MOVIMENTACAO_NENHUMA} as sem_movimentacao
                    from clientes c
                    left join lateral (
                      select
                        sum(l.valor) filter (where l.status = 'efetivado') as historico,
                        sum(l.valor) filter (
                          where l.status = 'efetivado' and l.data between :inicio and :fim
                        ) as periodo
                      from lancamentos_ativos l
                      join subcategorias s on s.id = l.subcategoria_id
                      where s.cliente_id = c.id and l.tipo = 'receita'
                        and {_SEM_PAI_DE_SPLIT}
                    ) t on true
                    left join lateral (
                      select jsonb_agg(jsonb_build_object(
                               'data', l.data, 'valor', l.valor, 'status', l.status,
                               'efetivar_automaticamente', l.efetivar_automaticamente
                             )) as em_aberto
                      from lancamentos_ativos l
                      join subcategorias s on s.id = l.subcategoria_id
                      where s.cliente_id = c.id
                        and l.tipo = 'receita'
                        and l.status in ('pendente','atrasado')
                        and {_SEM_PAI_DE_SPLIT}
                    ) a on true
                    where {onde}
                    order by lower(c.nome)
                    limit :limite offset :deslocamento
                    """),
                parametros
                | {"inicio": inicio, "fim": fim, "limite": limite, "deslocamento": deslocamento},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def conta(
    conexao: AsyncConnection, *, condicoes: list[str], parametros: dict[str, Any]
) -> int:
    onde = " and ".join(condicoes)
    return (
        await conexao.execute(text(f"select count(*) from clientes c where {onde}"), parametros)
    ).scalar_one()


async def por_id(conexao: AsyncConnection, cliente_id: UUID) -> dict[str, Any] | None:
    linha = (
        (
            await conexao.execute(
                text(f"select {_SELECAO} from clientes c where c.id = :id"),
                {"id": str(cliente_id)},
            )
        )
        .mappings()
        .first()
    )
    return dict(linha) if linha else None


async def em_aberto(conexao: AsyncConnection, cliente_id: UUID) -> list[dict[str, Any]]:
    """Lançamentos de receita ainda não confirmados — alimenta `RN-10`."""
    linhas = (
        (
            await conexao.execute(
                text("""
                    select l.data, l.valor, l.status, l.efetivar_automaticamente
                    from lancamentos_ativos l
                    join subcategorias s on s.id = l.subcategoria_id
                    where s.cliente_id = :cliente
                      and l.tipo = 'receita'
                      and l.status in ('pendente','atrasado')
                      and not exists (select 1 from lancamentos p
                                      where p.lancamento_pai_id = l.id
                                        and p.excluido_em is null)
                    """),
                {"cliente": str(cliente_id)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def quebra_por_mundo(conexao: AsyncConnection, cliente_id: UUID) -> dict[str, Any]:
    """`FR-081`: o cliente não tem mundo, mas a receita dele tem (D-04)."""
    linhas = (
        (
            await conexao.execute(
                text("""
                    select l.mundo, coalesce(sum(l.valor), 0) as valor
                    from lancamentos_ativos l
                    join subcategorias s on s.id = l.subcategoria_id
                    where s.cliente_id = :cliente
                      and l.tipo = 'receita' and l.status = 'efetivado'
                    group by l.mundo
                    """),
                {"cliente": str(cliente_id)},
            )
        )
        .mappings()
        .all()
    )
    resultado = {"digital": 0, "infra": 0}
    for linha in linhas:
        resultado[linha["mundo"]] = linha["valor"]
    return resultado


async def receita_mensal(
    conexao: AsyncConnection, cliente_id: UUID, *, meses: int = 12
) -> list[dict[str, Any]]:
    """Série mensal do perfil. `generate_series` para mês sem receita aparecer zerado."""
    linhas = (
        (
            await conexao.execute(
                text("""
                    with meses as (
                      select generate_series(
                        date_trunc('month', current_date) - make_interval(months => :meses - 1),
                        date_trunc('month', current_date),
                        interval '1 month'
                      )::date as mes
                    )
                    select to_char(m.mes, 'YYYY-MM') as mes,
                           coalesce(sum(l.valor), 0) as valor
                    from meses m
                    left join subcategorias s on s.cliente_id = :cliente
                    left join lancamentos_ativos l
                      on l.subcategoria_id = s.id
                     and date_trunc('month', l.data) = m.mes
                     and l.tipo = 'receita' and l.status = 'efetivado'
                    group by m.mes
                    order by m.mes
                    """),
                {"cliente": str(cliente_id), "meses": meses},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def proximos_recebimentos(
    conexao: AsyncConnection, cliente_id: UUID, *, hoje: date, limite: int = 12
) -> list[dict[str, Any]]:
    linhas = (
        (
            await conexao.execute(
                text("""
                    select l.id as lancamento_id, l.data, l.valor, l.status, l.mundo
                    from lancamentos_ativos l
                    join subcategorias s on s.id = l.subcategoria_id
                    where s.cliente_id = :cliente
                      and l.tipo = 'receita'
                      and l.data >= :hoje
                      and l.status in ('programado','pendente','atrasado')
                    order by l.data
                    limit :limite
                    """),
                {"cliente": str(cliente_id), "hoje": hoje, "limite": limite},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def lancamentos_do_cliente(
    conexao: AsyncConnection,
    cliente_id: UUID,
    *,
    inicio: date,
    fim: date,
    limite: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Lançamentos do cliente no período, e quantos existem ao todo.

    O vínculo cliente → lançamento é a **subcategoria espelho** (research.md D-07), não
    uma coluna `cliente_id` no lançamento: é por isso que o `join` passa por
    `subcategorias`. Traz receita e despesa, ao contrário de `receita_mensal` — a tela
    lista o movimento do cliente, e um estorno é movimento dele também.

    Devolve `(itens, total)` porque contracts/cadastros.md §3 promete o envelope
    paginado (`{"itens": [], "paginacao": {}}`) neste campo.
    """
    condicoes = """
        from lancamentos_ativos l
        join subcategorias s on s.id = l.subcategoria_id
        where s.cliente_id = :cliente and l.data between :inicio and :fim
    """
    parametros = {"cliente": str(cliente_id), "inicio": inicio, "fim": fim}

    total = (await conexao.execute(text(f"select count(*) {condicoes}"), parametros)).scalar_one()

    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.id, l.data, l.descricao, l.valor, l.tipo, l.status, l.mundo
                    {condicoes}
                    order by l.data desc, l.criado_em desc
                    limit :limite
                    """),
                parametros | {"limite": limite},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas], total


async def recorrencia_do_cliente(
    conexao: AsyncConnection, cliente_id: UUID
) -> dict[str, Any] | None:
    linha = (
        (
            await conexao.execute(
                text("""
                    select id, mundo, valor, frequencia, dia_vencimento, mes_vencimento,
                           intervalo_dias, ativa, efetivar_automaticamente
                    from recorrencias
                    where cliente_id = :cliente and excluido_em is null
                    order by criado_em desc
                    limit 1
                    """),
                {"cliente": str(cliente_id)},
            )
        )
        .mappings()
        .first()
    )
    return dict(linha) if linha else None


async def servicos_do_cliente(conexao: AsyncConnection, cliente_id: UUID) -> list[dict[str, Any]]:
    linhas = (
        (
            await conexao.execute(
                text("""
                    select s.id, s.nome, s.mundo
                    from clientes_servicos cs
                    join servicos s on s.id = cs.servico_id
                    where cs.cliente_id = :cliente
                    order by s.ordem, lower(s.nome)
                    """),
                {"cliente": str(cliente_id)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def define_servicos(
    conexao: AsyncConnection, cliente_id: UUID, servico_ids: list[UUID]
) -> None:
    await conexao.execute(
        text("delete from clientes_servicos where cliente_id = :cliente"),
        {"cliente": str(cliente_id)},
    )
    if not servico_ids:
        return
    await conexao.execute(
        text("""
            insert into clientes_servicos (cliente_id, servico_id)
            select :cliente, unnest(cast(:ids as uuid[])) on conflict do nothing
            """),
        {"cliente": str(cliente_id), "ids": [str(x) for x in servico_ids]},
    )
