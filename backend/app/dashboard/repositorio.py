"""Agregações do Dashboard — **todas em uma requisição** (`SC-002`).

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T089).
É aqui que `SC-002` ("entender a saúde do caixa em 10 segundos") se ganha ou se perde,
então o que veio da Skill está anotado consulta a consulta:

- **`filter (where …)` em vez de uma consulta por número.** Os 5 cards numéricos, o
  comparativo e a quebra por mundo saem de **uma** varredura do período. Sete consultas
  fariam sete varreduras do mesmo intervalo.
- **Os índices existentes cobrem as consultas, e não o contrário.**
  `lancamentos_mundo_data_idx` é `(mundo, data desc) where excluido_em is null`, que é a
  forma de todo filtro daqui; `lancamentos_status_data_idx` cobre A pagar/A receber e
  atrasados; `lancamentos_categoria_idx` cobre despesas por categoria.
- **`generate_series` para o eixo do tempo**, não um `GROUP BY` cru: mês sem movimento
  precisa aparecer com zero, senão o gráfico de 12 meses pula meses e a linha mente.
- **Nada de N+1.** Cada bloco é uma consulta que já volta agrupada.
- **Nenhum valor entra em SQL por concatenação.**

Toda consulta parte de `lancamentos_ativos` (a view que já filtra o soft delete) e
exclui o pai de split, exatamente como `lancamentos/repositorio.py` — as duas telas têm
que mostrar o mesmo número.

Tarefa: T089, T091, T092
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# `RN-11`: o pai de um split não conta; só as partes. Repetido aqui de propósito em vez
# de importado de `lancamentos/repositorio.py` — são módulos irmãos, e um import entre
# repositórios criaria dependência de camada que o Princípio IV não quer. O teste de
# integração compara os dois números.
_SEM_PAI_DE_SPLIT = """
  not exists (select 1 from lancamentos p
              where p.lancamento_pai_id = l.id and p.excluido_em is null)
"""

_EFETIVADO = f"l.status = 'efetivado' and {_SEM_PAI_DE_SPLIT}"

# `RN-05`: o que ainda não aconteceu — entra em projeção e nos cards A pagar/A receber,
# nunca no realizado.
_EM_ABERTO = f"l.status in ('programado','pendente','atrasado') and {_SEM_PAI_DE_SPLIT}"


async def totais_do_periodo(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date
) -> dict[str, Any]:
    """Receitas, despesas e contagem do período — uma varredura só."""
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'receita' and {_EFETIVADO}), 0) as receitas,
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'despesa' and {_EFETIVADO}), 0) as despesas,
                      count(*) filter (where {_EFETIVADO}) as quantidade
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.data between :inicio and :fim
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .one()
    )
    return dict(linha)


async def saldo_acumulado(
    conexao: AsyncConnection, *, mundos: list[str], ate: date | None = None
) -> dict[str, Any]:
    """Saldo desde sempre, opcionalmente cortado numa data.

    Sem recorte de início: não existe saldo inicial (`FR-114`), o saldo **é** o
    acumulado dos efetivados. `ate` serve ao comparativo (saldo no fim do período
    anterior) e à evolução mensal.
    """
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select
                      coalesce(sum(l.valor) filter (where l.tipo = 'receita'), 0)
                      - coalesce(sum(l.valor) filter (where l.tipo = 'despesa'), 0) as saldo
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and {_EFETIVADO}
                      and (:ate::date is null or l.data <= :ate)
                    """),
                {"mundos": mundos, "ate": ate},
            )
        )
        .mappings()
        .one()
    )
    return dict(linha)


async def saldo_por_mundo(conexao: AsyncConnection, *, ate: date | None = None) -> dict[str, Any]:
    """Quebra do saldo. Os dois mundos sempre aparecem, mesmo zerados (`FR-003`)."""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.mundo,
                      coalesce(sum(l.valor) filter (where l.tipo = 'receita'), 0)
                      - coalesce(sum(l.valor) filter (where l.tipo = 'despesa'), 0) as saldo
                    from lancamentos_ativos l
                    where {_EFETIVADO} and (:ate::date is null or l.data <= :ate)
                    group by l.mundo
                    """),
                {"ate": ate},
            )
        )
        .mappings()
        .all()
    )
    resultado = {"digital": 0, "infra": 0}
    for linha in linhas:
        resultado[linha["mundo"]] = linha["saldo"]
    return resultado


async def em_aberto(
    conexao: AsyncConnection, *, mundos: list[str], tipo: str, hoje: date
) -> list[dict[str, Any]]:
    """Composição de A pagar / A receber por situação (`FR-056`).

    **Ignora o período de propósito**: uma conta vencida em maio continua a pagar em
    julho. Filtrar por período esconderia justamente a que mais importa.
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.status as situacao, count(*) as quantidade,
                           coalesce(sum(l.valor), 0) as valor
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.tipo = cast(:tipo as tipo_lancamento)
                      and {_EM_ABERTO}
                    group by l.status
                    """),
                {"mundos": mundos, "tipo": tipo, "hoje": hoje},
            )
        )
        .mappings()
        .all()
    )
    por_situacao = {linha["situacao"]: linha for linha in linhas}
    # As três situações sempre aparecem, zeradas quando não há nada — estado vazio
    # explicativo em vez de card com uma linha só (edge case da spec).
    return [
        {
            "situacao": situacao,
            "quantidade": por_situacao.get(situacao, {}).get("quantidade", 0),
            "valor": por_situacao.get(situacao, {}).get("valor", 0),
        }
        for situacao in ("programado", "pendente", "atrasado")
    ]


async def atrasados(conexao: AsyncConnection, *, mundos: list[str]) -> dict[str, Any]:
    """O alerta fixo de `FR-068`. Também ignora período."""
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select count(*) as quantidade, coalesce(sum(l.valor), 0) as valor_total
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.status = 'atrasado' and {_SEM_PAI_DE_SPLIT}
                    """),
                {"mundos": mundos},
            )
        )
        .mappings()
        .one()
    )
    return dict(linha)


async def despesas_fixas_futuras(
    conexao: AsyncConnection, *, mundos: list[str], hoje: date, ate: date
) -> Any:
    """Despesas **já lançadas** para a janela — a base do semáforo (`RF-46b`).

    "Fixa" aqui é o que já existe no futuro, não uma média histórica: o sistema conhece
    o que vem porque as recorrências foram materializadas. Ver `dominio/saude_caixa.py`.
    """
    return (
        await conexao.execute(
            text(f"""
                select coalesce(sum(l.valor), 0)
                from lancamentos_ativos l
                where l.mundo = any(cast(:mundos as mundo[]))
                  and l.tipo = 'despesa'
                  and l.data between :hoje and :ate
                  and {_EM_ABERTO}
                """),
            {"mundos": mundos, "hoje": hoje, "ate": ate},
        )
    ).scalar_one()


async def fluxo_mensal(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, hoje: date
) -> list[dict[str, Any]]:
    """Receitas e despesas por mês, com os meses vazios presentes (`FR-059`).

    `generate_series` cria o eixo antes do `left join`: sem isso, um mês sem lançamento
    sumiria e a linha do gráfico ligaria junho a agosto como se julho não existisse.

    `projetado` marca o mês **posterior ao atual** — nele os valores incluem o que ainda
    não aconteceu, e `RN-05` exige que isso seja visualmente distinto.
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    with meses as (
                      select generate_series(
                        date_trunc('month', :inicio::date),
                        date_trunc('month', :fim::date),
                        interval '1 month'
                      )::date as mes
                    )
                    select
                      to_char(m.mes, 'YYYY-MM') as mes,
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'receita' and {_SEM_PAI_DE_SPLIT}), 0) as receitas,
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'despesa' and {_SEM_PAI_DE_SPLIT}), 0) as despesas,
                      m.mes > date_trunc('month', :hoje::date) as projetado
                    from meses m
                    left join lancamentos_ativos l
                      on date_trunc('month', l.data) = m.mes
                     and l.mundo = any(cast(:mundos as mundo[]))
                     and l.status <> 'cancelado'
                    group by m.mes
                    order by m.mes
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim, "hoje": hoje},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def evolucao_saldo(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, hoje: date
) -> list[dict[str, Any]]:
    """Saldo **acumulado** no fim de cada mês (`FR-060`).

    `sum() over (order by mes)` faz o acumulado numa passada. Calcular mês a mês em
    Python custaria 12 consultas — e o acumulado tem que partir do começo dos tempos,
    não do começo do período, porque não existe saldo inicial (`FR-114`).
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    with meses as (
                      select generate_series(
                        date_trunc('month', :inicio::date),
                        date_trunc('month', :fim::date),
                        interval '1 month'
                      )::date as mes
                    ),
                    anterior as (
                      select coalesce(sum(
                        case when l.tipo = 'receita' then l.valor else -l.valor end), 0) as base
                      from lancamentos_ativos l
                      where l.mundo = any(cast(:mundos as mundo[]))
                        and {_EFETIVADO}
                        and l.data < date_trunc('month', :inicio::date)
                    ),
                    por_mes as (
                      select m.mes,
                             coalesce(sum(
                               case when l.tipo = 'receita' then l.valor else -l.valor end
                             ) filter (where {_EFETIVADO}), 0) as resultado
                      from meses m
                      left join lancamentos_ativos l
                        on date_trunc('month', l.data) = m.mes
                       and l.mundo = any(cast(:mundos as mundo[]))
                      group by m.mes
                    )
                    select to_char(p.mes, 'YYYY-MM') as mes,
                           (select base from anterior)
                             + sum(p.resultado) over (order by p.mes) as saldo_final,
                           p.mes > date_trunc('month', :hoje::date) as projetado
                    from por_mes p
                    order by p.mes
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim, "hoje": hoje},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def despesas_por_categoria(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date
) -> list[dict[str, Any]]:
    """`FR-062`. Só efetivado — o gráfico mostra o que aconteceu, não o previsto."""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select c.id as categoria_id, c.nome, c.cor,
                           coalesce(sum(l.valor), 0) as valor
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.tipo = 'despesa'
                      and l.data between :inicio and :fim
                      and {_EFETIVADO}
                    group by c.id, c.nome, c.cor
                    order by valor desc
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def top_despesas(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, limite: int = 5
) -> list[dict[str, Any]]:
    """`FR-063` — as maiores despesas individuais do período."""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.id as lancamento_id, l.descricao, l.valor, l.data,
                           c.nome as categoria_nome
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.tipo = 'despesa'
                      and l.data between :inicio and :fim
                      and {_EFETIVADO}
                    order by l.valor desc
                    limit :limite
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim, "limite": limite},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def receita_por_servico(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date
) -> list[dict[str, Any]]:
    """`RF-43b`. Lançamento sem serviço fica de fora — não vira um "Outros" inventado."""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select s.id as servico_id, s.nome, s.mundo,
                           coalesce(sum(l.valor), 0) as valor
                    from lancamentos_ativos l
                    join servicos s on s.id = l.servico_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.tipo = 'receita'
                      and l.data between :inicio and :fim
                      and {_EFETIVADO}
                    group by s.id, s.nome, s.mundo
                    order by valor desc
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def por_vinculo_de_categoria(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, vinculo: str
) -> list[dict[str, Any]]:
    """Totais por subcategoria das categorias **especiais** (`FR-065`, `FR-066`).

    **Resolvido por `categorias.vinculo`, nunca por nome** (`FR-079`). Um
    `where c.nome = 'Clientes'` funcionaria hoje e quebraria no dia em que alguém
    renomeasse a categoria pela tela — e renomear é permitido.
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select s.id as subcategoria_id, s.nome,
                           s.cliente_id, s.funcionario_id,
                           coalesce(sum(l.valor), 0) as valor
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    join subcategorias s on s.id = l.subcategoria_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and c.vinculo = cast(:vinculo as vinculo_subcategoria)
                      and l.data between :inicio and :fim
                      and {_EFETIVADO}
                    group by s.id, s.nome, s.cliente_id, s.funcionario_id
                    order by valor desc
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim, "vinculo": vinculo},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def proximos_pagamentos_por_vinculo(
    conexao: AsyncConnection, *, mundos: list[str], hoje: date, vinculo: str, limite: int = 10
) -> list[dict[str, Any]]:
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.id as lancamento_id, s.nome, l.data, l.valor, l.status
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    join subcategorias s on s.id = l.subcategoria_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and c.vinculo = cast(:vinculo as vinculo_subcategoria)
                      and l.data >= :hoje and {_EM_ABERTO}
                    order by l.data
                    limit :limite
                    """),
                {"mundos": mundos, "hoje": hoje, "vinculo": vinculo, "limite": limite},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def proximos_dias(
    conexao: AsyncConnection, *, mundos: list[str], hoje: date, ate: date
) -> list[dict[str, Any]]:
    """A linha do tempo de 7 dias (`FR-067`)."""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.id as lancamento_id, l.data, l.tipo, l.descricao,
                           l.valor, l.status
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.data between :hoje and :ate
                      and {_EM_ABERTO}
                    order by l.data, l.tipo
                    """),
                {"mundos": mundos, "hoje": hoje, "ate": ate},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def tendencia_mensal(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, tipo: str | None
) -> list[dict[str, Any]]:
    """Série curta para as sparklines dos cards (`FR-057`)."""
    filtro_tipo = "and l.tipo = cast(:tipo as tipo_lancamento)" if tipo else ""
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    with meses as (
                      select generate_series(
                        date_trunc('month', :inicio::date),
                        date_trunc('month', :fim::date),
                        interval '1 month'
                      )::date as mes
                    )
                    select to_char(m.mes, 'YYYY-MM') as rotulo,
                           coalesce(sum(l.valor), 0) as valor
                    from meses m
                    left join lancamentos_ativos l
                      on date_trunc('month', l.data) = m.mes
                     and l.mundo = any(cast(:mundos as mundo[]))
                     and l.status = 'efetivado'
                     {filtro_tipo}
                    group by m.mes
                    order by m.mes
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim, "tipo": tipo},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]
