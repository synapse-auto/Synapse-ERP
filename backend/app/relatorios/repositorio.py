"""Agregações dos relatórios — contracts/consultas.md §3.

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T114).
O que veio dela:

- **Uma consulta traz categoria e subcategoria juntas**, com `grouping sets`. A
  alternativa — uma consulta por categoria para buscar as subcategorias — seria N+1 no
  relatório que mais tem linhas.
- **`lancamentos_categoria_idx` é `(categoria_id, data)`**, exatamente a forma do recorte
  do DRE. Nenhum índice novo foi preciso.
- **`generate_series` para o eixo de meses** na matriz e na variação: mês sem movimento
  precisa aparecer com zero, senão a comparação entre meses compara meses diferentes.
- **Nenhum valor entra em SQL por concatenação.**

Todas as consultas partem de `lancamentos_ativos` e excluem o pai de split, o mesmo
recorte do Dashboard e do Extrato — os três têm que dar o mesmo número.

Tarefa: T114
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# Continua como `not exists` solto, e não como a junção lateral de
# `lancamentos/repositorio.py`, **porque aqui ele sempre cai no `WHERE`**. No `WHERE` o
# planejador transforma `not exists` em anti-join de verdade (uma passada); é dentro de
# `filter (where …)` que ele vira subconsulta por linha, e é lá que a lateral foi
# necessária. Conferido por `EXPLAIN` em 2026-08-04.
_SEM_PAI_DE_SPLIT = """
  not exists (select 1 from lancamentos p
              where p.lancamento_pai_id = l.id and p.excluido_em is null)
"""

_EFETIVADO = f"l.status = 'efetivado' and {_SEM_PAI_DE_SPLIT}"


async def por_categoria_e_subcategoria(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, tipo: str
) -> list[dict[str, Any]]:
    """Totais por categoria **e** por subcategoria numa consulta só.

    `grouping sets` devolve as duas granularidades juntas: a linha com
    `subcategoria_id` nulo é o total da categoria. Sem isso, seria uma consulta por
    categoria para buscar as filhas — o N+1 clássico de relatório hierárquico.
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select c.id as categoria_id, c.nome as categoria_nome, c.cor,
                           s.id as subcategoria_id, s.nome as subcategoria_nome,
                           coalesce(sum(l.valor), 0) as valor,
                           count(*) as quantidade
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    left join subcategorias s on s.id = l.subcategoria_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.tipo = cast(:tipo as tipo_lancamento)
                      and l.data between :inicio and :fim
                      and {_EFETIVADO}
                    group by grouping sets (
                      (c.id, c.nome, c.cor),
                      (c.id, c.nome, c.cor, s.id, s.nome)
                    )
                    order by c.nome, s.nome nulls first
                    """),
                {"mundos": mundos, "tipo": tipo, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def totais(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date
) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select
                      coalesce(sum(l.valor) filter (where l.tipo = 'receita'), 0) as receitas,
                      coalesce(sum(l.valor) filter (where l.tipo = 'despesa'), 0) as despesas
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.data between :inicio and :fim
                      and {_EFETIVADO}
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .one()
    )
    return dict(linha)


async def por_cliente(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date
) -> list[dict[str, Any]]:
    """Ranking de clientes com quebra por mundo (`FR-091`).

    A quebra existe porque **o cliente não tem mundo** (D-04), mas a receita dele tem.
    Sai como `jsonb` na mesma consulta para não custar uma ida por cliente.
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select cl.id as cliente_id, cl.nome, cl.empresa,
                           coalesce(sum(l.valor), 0) as total,
                           jsonb_object_agg(
                             l.mundo, coalesce(t.por_mundo, 0)
                           ) filter (where l.mundo is not null) as quebra
                    from clientes cl
                    left join subcategorias s on s.cliente_id = cl.id
                    left join lancamentos_ativos l
                      on l.subcategoria_id = s.id
                     and l.tipo = 'receita'
                     and l.mundo = any(cast(:mundos as mundo[]))
                     and l.data between :inicio and :fim
                     and {_EFETIVADO}
                    left join lateral (
                      select coalesce(sum(l2.valor), 0) as por_mundo
                      from lancamentos_ativos l2
                      where l2.subcategoria_id = s.id
                        and l2.mundo = l.mundo
                        and l2.tipo = 'receita'
                        and l2.data between :inicio and :fim
                        and l2.status = 'efetivado'
                    ) t on true
                    where cl.arquivado_em is null
                    group by cl.id, cl.nome, cl.empresa
                    order by total desc, lower(cl.nome)
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def evolucao_mensal_por_cliente(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date
) -> list[dict[str, Any]]:
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select s.cliente_id, to_char(date_trunc('month', l.data), 'YYYY-MM') as mes,
                           coalesce(sum(l.valor), 0) as valor
                    from lancamentos_ativos l
                    join subcategorias s on s.id = l.subcategoria_id
                    where s.cliente_id is not null
                      and l.tipo = 'receita'
                      and l.mundo = any(cast(:mundos as mundo[]))
                      and l.data between :inicio and :fim
                      and {_EFETIVADO}
                    group by s.cliente_id, date_trunc('month', l.data)
                    order by s.cliente_id, date_trunc('month', l.data)
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def matriz_mensal(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, tipo: str | None
) -> tuple[list[str], list[dict[str, Any]]]:
    """Meses × categorias, com os meses vazios presentes (`FR-093`).

    O eixo vem de `generate_series` e o cruzamento de um `cross join` com as categorias
    que tiveram movimento: sem isso, um mês sem lançamento sumiria da matriz e a
    comparação entre colunas passaria a comparar meses diferentes.
    """
    filtro_tipo = "and l.tipo = cast(:tipo as tipo_lancamento)" if tipo else ""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    with meses as (
                      select generate_series(
                        date_trunc('month', cast(:inicio as date)),
                        date_trunc('month', cast(:fim as date)),
                        interval '1 month'
                      )::date as mes
                    ),
                    categorias_com_movimento as (
                      select distinct c.id, c.nome, c.cor
                      from lancamentos_ativos l
                      join categorias c on c.id = l.categoria_id
                      where l.mundo = any(cast(:mundos as mundo[]))
                        and l.data between :inicio and :fim
                        and {_EFETIVADO}
                        {filtro_tipo}
                    )
                    select cc.id as categoria_id, cc.nome, cc.cor,
                           to_char(m.mes, 'YYYY-MM') as mes,
                           coalesce(sum(l.valor), 0) as valor
                    from categorias_com_movimento cc
                    cross join meses m
                    left join lancamentos_ativos l
                      on l.categoria_id = cc.id
                     and date_trunc('month', l.data) = m.mes
                     and l.mundo = any(cast(:mundos as mundo[]))
                     and l.status = 'efetivado'
                     {filtro_tipo}
                    group by cc.id, cc.nome, cc.cor, m.mes
                    order by cc.nome, m.mes
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim, "tipo": tipo},
            )
        )
        .mappings()
        .all()
    )

    meses = sorted({linha["mes"] for linha in linhas})
    return meses, [dict(linha) for linha in linhas]
