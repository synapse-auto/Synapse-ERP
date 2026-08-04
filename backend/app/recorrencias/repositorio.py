"""Acesso a dados das recorrências. **Sem regra de negócio aqui** (Princípio IV).

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T078).
O que veio dela e está aplicado:

- **`recorrencias_a_gerar_idx`** é `(gerada_ate) where ativa and excluido_em is null` —
  exatamente a forma da varredura da rotina diária. `a_materializar` foi escrita para
  casar com esse índice, e não o contrário.
- **`on conflict do nothing` na ocorrência**, apoiado no índice único
  `(recorrencia_id, data)`: é o que faz a rotina poder rodar duas vezes no mesmo dia sem
  duplicar nada, sem precisar de `select` antes de cada `insert` (D-08).
- **Nada de N+1**: a contagem de ocorrências da lista sai por `left join lateral`, não
  por uma consulta por linha.
- **Nenhum valor entra em SQL por concatenação.**

Tarefa: T078
"""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_SELECAO = """
  r.id, r.mundo, r.tipo, r.descricao, r.valor,
  r.frequencia, r.intervalo_dias, r.dia_vencimento, r.mes_vencimento,
  r.data_inicio, r.data_fim, r.total_parcelas,
  r.efetivar_automaticamente, r.gerada_ate, r.ativa,
  r.categoria_id, r.subcategoria_id, r.servico_id, r.centro_custo_id,
  r.cliente_id, r.funcionario_id, r.criado_em, r.criado_por, r.excluido_em,
  c.nome as categoria_nome, c.cor as categoria_cor, c.icone as categoria_icone,
  c.especial as categoria_especial, c.vinculo as categoria_vinculo,
  s.nome as subcategoria_nome,
  sv.nome as servico_nome, cc.nome as centro_custo_nome
"""

_JUNCOES = """
  from recorrencias r
  join categorias c on c.id = r.categoria_id
  left join subcategorias s on s.id = r.subcategoria_id
  left join servicos sv on sv.id = r.servico_id
  left join centros_custo cc on cc.id = r.centro_custo_id
"""

# Colunas que o `POST` e o `PUT` gravam. Numa lista só para os dois não divergirem.
CAMPOS_GRAVAVEIS = (
    "tipo",
    "descricao",
    "valor",
    "categoria_id",
    "subcategoria_id",
    "servico_id",
    "centro_custo_id",
    "frequencia",
    "intervalo_dias",
    "dia_vencimento",
    "mes_vencimento",
    "data_inicio",
    "data_fim",
    "total_parcelas",
    "efetivar_automaticamente",
)


async def lista(
    conexao: AsyncConnection,
    *,
    mundos: list[str],
    apenas_ativas: bool,
    limite: int,
    deslocamento: int,
) -> list[dict[str, Any]]:
    """Lista com `ocorrencias_geradas` e `proxima_ocorrencia` (contracts §3)."""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select {_SELECAO},
                           coalesce(o.geradas, 0) as ocorrencias_geradas,
                           o.proxima as proxima_ocorrencia
                    {_JUNCOES}
                    left join lateral (
                      select count(*) as geradas,
                             min(l.data) filter (
                               where l.data >= current_date and l.status <> 'cancelado'
                             ) as proxima
                      from lancamentos l
                      where l.recorrencia_id = r.id and l.excluido_em is null
                    ) o on true
                    where r.excluido_em is null
                      and r.mundo = any(cast(:mundos as mundo[]))
                      and (not :apenas_ativas or r.ativa)
                    order by r.ativa desc, lower(r.descricao)
                    limit :limite offset :deslocamento
                    """),
                {
                    "mundos": mundos,
                    "apenas_ativas": apenas_ativas,
                    "limite": limite,
                    "deslocamento": deslocamento,
                },
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def conta(conexao: AsyncConnection, *, mundos: list[str], apenas_ativas: bool) -> int:
    return (
        await conexao.execute(
            text("""
                select count(*) from recorrencias r
                where r.excluido_em is null
                  and r.mundo = any(cast(:mundos as mundo[]))
                  and (not :apenas_ativas or r.ativa)
                """),
            {"mundos": mundos, "apenas_ativas": apenas_ativas},
        )
    ).scalar_one()


async def por_id(conexao: AsyncConnection, recorrencia_id: UUID) -> dict[str, Any] | None:
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select {_SELECAO},
                           coalesce(o.geradas, 0) as ocorrencias_geradas,
                           o.proxima as proxima_ocorrencia
                    {_JUNCOES}
                    left join lateral (
                      select count(*) as geradas,
                             min(l.data) filter (
                               where l.data >= current_date and l.status <> 'cancelado'
                             ) as proxima
                      from lancamentos l
                      where l.recorrencia_id = r.id and l.excluido_em is null
                    ) o on true
                    where r.id = :id and r.excluido_em is null
                    """),
                {"id": str(recorrencia_id)},
            )
        )
        .mappings()
        .first()
    )
    return dict(linha) if linha else None


async def ocorrencias(
    conexao: AsyncConnection, recorrencia_id: UUID, *, limite: int = 200
) -> list[dict[str, Any]]:
    """As ocorrências materializadas, da mais recente para trás."""
    linhas = (
        (
            await conexao.execute(
                text("""
                    select l.id, l.data, l.valor, l.status, l.descricao
                    from lancamentos_ativos l
                    where l.recorrencia_id = :id
                    order by l.data desc
                    limit :limite
                    """),
                {"id": str(recorrencia_id), "limite": limite},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def insere(
    conexao: AsyncConnection, *, campos: dict[str, Any], mundo: str, usuario_id: UUID
) -> dict[str, Any]:
    parametros = {chave: campos.get(chave) for chave in CAMPOS_GRAVAVEIS}
    parametros |= {
        "mundo": mundo,
        "usuario": str(usuario_id),
        "cliente_id": campos.get("cliente_id"),
        "funcionario_id": campos.get("funcionario_id"),
    }
    linha = (
        (
            await conexao.execute(
                text("""
                    insert into recorrencias (
                      mundo, tipo, descricao, valor,
                      categoria_id, subcategoria_id, servico_id, centro_custo_id,
                      frequencia, intervalo_dias, dia_vencimento, mes_vencimento,
                      data_inicio, data_fim, total_parcelas,
                      efetivar_automaticamente, cliente_id, funcionario_id, criado_por
                    ) values (
                      cast(:mundo as mundo), cast(:tipo as tipo_lancamento), :descricao, :valor,
                      cast(:categoria_id as uuid), cast(:subcategoria_id as uuid),
                      cast(:servico_id as uuid), cast(:centro_custo_id as uuid),
                      cast(:frequencia as frequencia_recorrencia), :intervalo_dias,
                      :dia_vencimento, :mes_vencimento,
                      :data_inicio, :data_fim, :total_parcelas,
                      :efetivar_automaticamente, cast(:cliente_id as uuid),
                      cast(:funcionario_id as uuid), cast(:usuario as uuid)
                    )
                    returning id
                    """),
                parametros,
            )
        )
        .mappings()
        .one()
    )
    return dict(linha)


async def atualiza(
    conexao: AsyncConnection, recorrencia_id: UUID, *, campos: dict[str, Any]
) -> None:
    """Atualiza a regra. `mundo` **não** está entre os campos graváveis (`RN-15`)."""
    parametros = {chave: campos.get(chave) for chave in CAMPOS_GRAVAVEIS}
    parametros["id"] = str(recorrencia_id)
    await conexao.execute(
        text("""
            update recorrencias set
              tipo = cast(:tipo as tipo_lancamento), descricao = :descricao, valor = :valor,
              categoria_id = cast(:categoria_id as uuid),
              subcategoria_id = cast(:subcategoria_id as uuid),
              servico_id = cast(:servico_id as uuid),
              centro_custo_id = cast(:centro_custo_id as uuid),
              frequencia = cast(:frequencia as frequencia_recorrencia),
              intervalo_dias = :intervalo_dias, dia_vencimento = :dia_vencimento,
              mes_vencimento = :mes_vencimento, data_inicio = :data_inicio,
              data_fim = :data_fim, total_parcelas = :total_parcelas,
              efetivar_automaticamente = :efetivar_automaticamente
            where id = :id
            """),
        parametros,
    )


async def marca_gerada_ate(conexao: AsyncConnection, recorrencia_id: UUID, ate: date) -> None:
    """Avança o marcador de materialização.

    `greatest` para nunca **retroceder**: uma execução parcial que terminasse antes da
    anterior faria a rotina seguinte regerar o que já existe, e a proteção contra
    duplicata passaria a ser só o índice único — que recusaria em silêncio, mas
    desperdiçando a invocação inteira.
    """
    await conexao.execute(
        text(
            "update recorrencias set gerada_ate = greatest(coalesce(gerada_ate, :ate), :ate) "
            "where id = :id"
        ),
        {"id": str(recorrencia_id), "ate": ate},
    )


async def marca_gerada_ate_em_lote(conexao: AsyncConnection, cursores: dict[UUID, date]) -> None:
    """O mesmo que `marca_gerada_ate`, para várias recorrências numa ida ao banco.

    A rotina diária avança o marcador de até 100 recorrências por execução, e fazia
    isso com um `UPDATE` cada — `pg_stat_statements` contou 609 execuções da forma
    singular. `update … from unnest(…)` faz as 100 numa (Skill: `data-batch-inserts`).
    """
    if not cursores:
        return
    await conexao.execute(
        text("""
            update recorrencias r
            set gerada_ate = greatest(coalesce(r.gerada_ate, novo.ate), novo.ate)
            from unnest(cast(:ids as uuid[]), cast(:ates as date[])) as novo(id, ate)
            where r.id = novo.id
            """),
        {
            "ids": [str(chave) for chave in cursores],
            "ates": list(cursores.values()),
        },
    )


async def insere_ocorrencias(
    conexao: AsyncConnection,
    *,
    recorrencia: dict[str, Any],
    ocorrencias: list[tuple[date, str]],
    usuario_id: UUID,
) -> int:
    """Grava as ocorrências de **uma** recorrência numa ida ao banco.

    Devolve quantas foram criadas de fato — as que já existiam não contam.

    O `on conflict do nothing` sobre `(recorrencia_id, data)` é o coração da
    idempotência de D-08: a rotina não precisa saber o que já gerou, só tentar.

    **Era uma linha por `INSERT`** (Skill: `data-batch-inserts`). Com o lote de geração
    em 100 datas, uma recorrência nova custava 100 idas ao banco; `pg_stat_statements`
    registrava 7117 execuções da forma singular, com média de 16 ms cada — quase tudo
    rede. O `unnest` de dois arrays paralelos (a data e o status daquela data) resolve
    numa. Tudo que **não** varia por data continua como parâmetro escalar.
    """
    if not ocorrencias:
        return 0
    resultado = await conexao.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status,
              categoria_id, subcategoria_id, servico_id, centro_custo_id,
              efetivar_automaticamente, efetivado_em, efetivado_por,
              recorrencia_id, criado_por
            )
            select
              cast(:mundo as mundo), cast(:tipo as tipo_lancamento), :descricao, :valor,
              o.quando, o.status,
              :categoria_id, :subcategoria_id, :servico_id, :centro_custo_id,
              :efetivar_automaticamente,
              case when o.status = 'efetivado' then now() end,
              case when o.status = 'efetivado' then cast(:usuario as uuid) end,
              cast(:recorrencia_id as uuid), cast(:usuario as uuid)
            from unnest(
              cast(:datas as date[]),
              cast(:status_por_data as status_lancamento[])
            ) as o(quando, status)
            on conflict (recorrencia_id, data) where recorrencia_id is not null do nothing
            """),
        {
            "mundo": recorrencia["mundo"],
            "tipo": recorrencia["tipo"],
            "descricao": recorrencia["descricao"],
            "valor": recorrencia["valor"],
            "categoria_id": recorrencia["categoria_id"],
            "subcategoria_id": recorrencia["subcategoria_id"],
            "servico_id": recorrencia["servico_id"],
            "centro_custo_id": recorrencia["centro_custo_id"],
            "efetivar_automaticamente": recorrencia["efetivar_automaticamente"],
            "recorrencia_id": str(recorrencia["id"]),
            "usuario": str(usuario_id),
            "datas": [quando for quando, _ in ocorrencias],
            "status_por_data": [status for _, status in ocorrencias],
        },
    )
    return resultado.rowcount or 0


async def remove_futuras_nao_efetivadas(
    conexao: AsyncConnection,
    recorrencia_id: UUID,
    *,
    a_partir_de: date,
    usuario_id: UUID,
    definitivo: bool = False,
) -> int:
    """Remove as ocorrências futuras ainda não efetivadas.

    Usado por desativar, por editar com `esta_e_futuras` (que apaga e regera) e pelo
    arquivamento de cliente/funcionário. **Nunca toca em efetivada** (`RN-05`,
    `RN-07`): o dinheiro que já se moveu fica no histórico, mesmo que a regra morra.

    ## `definitivo` — por que a edição de série precisa apagar de verdade

    O índice único da migração `010` é `(recorrencia_id, data)` **sem** filtro de
    `excluido_em`, e isso é deliberado: excluir uma ocorrência não pode fazê-la renascer
    na próxima execução da rotina (data-model §3.13).

    A consequência é que o soft delete **não libera a data**. Na edição com
    `esta_e_futuras` — que apaga e regera — o `insert … on conflict do nothing` da
    materialização batia nas linhas soft-deleted e não inseria nada. Resultado observado:
    a edição limpava o futuro e **não regerava ocorrência nenhuma**, silenciosamente.
    `RN-07`/`FR-034` prometem o contrário.

    Com `definitivo=True` a linha é apagada de verdade, a data é liberada e a
    regeneração acontece. É seguro porque o alvo é estreito: ocorrência **gerada pelo
    sistema**, **nunca efetivada**, de uma regra que acabou de ser substituída — não é
    histórico financeiro, que é o que `RN-08` protege. A mudança da regra fica registrada
    na auditoria da recorrência.

    Repare que o `where` continua exigindo `excluido_em is null`: uma ocorrência que o
    **usuário** apagou à mão permanece apagada e não é regerada pela edição da série —
    exatamente o que o *edge case* "excluir uma ocorrência afeta só aquela" pede.

    Nos outros dois usos (desativar, arquivar cliente/funcionário) nada é regerado
    depois, então o soft delete continua sendo o certo: some da tela e a linha fica.
    """
    if definitivo:
        resultado = await conexao.execute(
            text("""
                delete from lancamentos
                where recorrencia_id = :id
                  and data >= :a_partir_de
                  and status <> 'efetivado'
                  and excluido_em is null
                """),
            {"id": str(recorrencia_id), "a_partir_de": a_partir_de},
        )
        return resultado.rowcount or 0

    resultado = await conexao.execute(
        text("""
            update lancamentos
            set excluido_em = now(), excluido_por = cast(:usuario as uuid)
            where recorrencia_id = :id
              and data >= :a_partir_de
              and status <> 'efetivado'
              and excluido_em is null
            """),
        {"id": str(recorrencia_id), "a_partir_de": a_partir_de, "usuario": str(usuario_id)},
    )
    return resultado.rowcount or 0


async def desativa(conexao: AsyncConnection, recorrencia_id: UUID) -> None:
    await conexao.execute(
        text("update recorrencias set ativa = false where id = :id"), {"id": str(recorrencia_id)}
    )


async def exclui(conexao: AsyncConnection, recorrencia_id: UUID, *, usuario_id: UUID) -> None:
    """Soft delete da **regra**. As ocorrências efetivadas continuam (contracts §3)."""
    await conexao.execute(
        text("""
            update recorrencias
            set excluido_em = now(), excluido_por = cast(:usuario as uuid), ativa = false
            where id = :id
            """),
        {"id": str(recorrencia_id), "usuario": str(usuario_id)},
    )


async def a_materializar(conexao: AsyncConnection, *, ate: date) -> list[dict[str, Any]]:
    """Recorrências ativas que ainda têm o que gerar — a varredura da rotina diária.

    Escrita para casar com `recorrencias_a_gerar_idx`, que é parcial em
    `ativa and excluido_em is null`.
    """
    linhas = (
        (
            await conexao.execute(
                text("""
                    select r.id, r.mundo, r.tipo, r.descricao, r.valor,
                           r.frequencia, r.intervalo_dias, r.dia_vencimento, r.mes_vencimento,
                           r.data_inicio, r.data_fim, r.total_parcelas,
                           r.efetivar_automaticamente, r.gerada_ate,
                           r.categoria_id, r.subcategoria_id, r.servico_id, r.centro_custo_id,
                           r.criado_por
                    from recorrencias r
                    where r.ativa and r.excluido_em is null
                      and (r.gerada_ate is null or r.gerada_ate < :ate)
                    order by r.gerada_ate nulls first
                    """),
                {"ate": ate},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]
