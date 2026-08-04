"""Agregações do Dashboard — **três idas ao banco**, não vinte (`SC-002`).

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T089) e
de novo na revisão de desempenho de 2026-08-04.

## O que mudou em 2026-08-04, e por quê

A versão anterior tinha uma função por bloco e `dashboard/rotas.py` chamava vinte, uma
esperando a outra. Cada consulta custava **0,18 ms de execução no Postgres e uma
viagem de rede inteira** — e a viagem é o que manda: com o pooler em `us-east-2` e o
cache de statement obrigatoriamente desligado (ver `app/db.py`), `EXPLAIN` real dava
`Planning 1.45 ms` contra `Execution 0.18 ms`.

Somar `filter (where …)` numa consulta já era certo e continua. O que faltava era o
passo seguinte: **somar as consultas também**. Agora são três, uma por família:

| Função | O que traz | Substitui |
|---|---|---|
| `numeros` | cards numéricos, saldo, A pagar/A receber, atrasados, sparklines, despesa fixa | 11 consultas |
| `series` | fluxo mensal, evolução do saldo, despesa por categoria, maiores, receita por serviço | 5 consultas |
| `blocos` | clientes, funcionários, folha, inadimplência, próximos 7 dias | 6 consultas |

O SQL de cada bloco é o mesmo de antes, movido para dentro de um CTE. Nenhuma regra
mudou de lugar: quem decide inadimplência continua sendo `dominio/inadimplencia.py`,
em Python.

## O resto do que veio da Skill, e continua valendo

- **`filter (where …)` em vez de uma consulta por número.** Os cards saem de **uma**
  varredura.
- **Os índices existentes cobrem as consultas, e não o contrário.**
  `lancamentos_mundo_data_idx` é `(mundo, data desc) where excluido_em is null`;
  `lancamentos_status_data_idx` cobre A pagar/A receber e atrasados;
  `lancamentos_categoria_idx` cobre despesas por categoria.
- **`generate_series` para o eixo do tempo**: mês sem movimento aparece com zero,
  senão o gráfico de 12 meses pula meses e a linha mente.
- **Nada de N+1.** Cada bloco volta agrupado.
- **Nenhum valor entra em SQL por concatenação.**
- **O pai de split é resolvido por junção lateral, não por `not exists` repetido** —
  ver `_PARTES` abaixo.

## Dinheiro e data saem como texto do Postgres

`numeric(14,2)::text` devolve `"1234.56"` e `date::text` devolve o ISO 8601 que o
contrato pede. Assim o valor atravessa `jsonb` sem virar float em ponto nenhum
(`Convenções`: nunca float) e sem custar conversão para `Decimal` e de volta no
Python. Quem precisa de conta — comparativo, percentual — converte na rota.

Tarefa: T089, T091, T092
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# ── O pai de split (`RN-11`) ────────────────────────────────────────────────
#
# O pai de um split não conta; só as partes. A condição vem de uma **junção lateral**
# e não de um `not exists` repetido em cada agregado, porque dentro de
# `filter (where …)` o `not exists` não vira anti-join: o planejador o executa por
# linha e **não reaproveita entre agregados**. O `EXPLAIN` da versão anterior mostrava
# `SubPlan 1`, `SubPlan 3` e `SubPlan 5` — três planos idênticos para a mesma
# pergunta. Com a lateral sobra um, com `loops` igual ao número de linhas.
#
# Repetido aqui de propósito em vez de importado de `lancamentos/repositorio.py` — são
# módulos irmãos, e um import entre repositórios criaria dependência de camada que o
# Princípio IV não quer. O teste de integração compara os dois números.
_PARTES = """
  left join lateral (
    select exists (
      select 1 from lancamentos p
      where p.lancamento_pai_id = l.id and p.excluido_em is null
    ) as tem_partes
  ) sp on true
"""

# `RN-05`: o que ainda não aconteceu — entra em projeção e nos cards A pagar/A receber,
# nunca no realizado.
_EM_ABERTO_STATUS = "('programado','pendente','atrasado')"


async def numeros(
    conexao: AsyncConnection,
    *,
    mundos: list[str],
    inicio: date,
    fim: date,
    inicio_anterior: date,
    fim_anterior: date,
    inicio_tendencia: date,
    hoje: date,
    fim_horizonte: date,
) -> dict[str, Any]:
    """Tudo que é número de card, numa consulta.

    `base` é varrida **uma vez** e todos os recortes saem dela por `filter`. Os cards
    que ignoram o período de propósito — atrasados e A pagar/A receber — não recebem
    condição de data: uma conta vencida em maio continua a pagar em julho, e filtrar
    por período esconderia justamente a que mais importa (contracts/consultas.md).

    `por_mundo` é a única parte que **não** herda o filtro de mundo: `FR-003` manda os
    dois mundos aparecerem sempre, mesmo quando a tela está num só.
    """
    dados = (
        await conexao.execute(
            text(f"""
                with base as (
                  select l.tipo, l.valor, l.data, l.status, not sp.tem_partes as conta
                  from lancamentos_ativos l
                  {_PARTES}
                  where l.mundo = any(cast(:mundos as mundo[]))
                ),
                todos_os_mundos as (
                  select l.mundo, l.tipo, l.valor
                  from lancamentos_ativos l
                  {_PARTES}
                  where l.status = 'efetivado' and not sp.tem_partes
                ),
                periodo as (
                  select
                    coalesce(sum(valor) filter (
                      where tipo = 'receita' and status = 'efetivado' and conta
                        and data between :inicio and :fim), 0)::text as receitas,
                    coalesce(sum(valor) filter (
                      where tipo = 'despesa' and status = 'efetivado' and conta
                        and data between :inicio and :fim), 0)::text as despesas,
                    count(*) filter (
                      where status = 'efetivado' and conta
                        and data between :inicio and :fim) as quantidade,
                    coalesce(sum(valor) filter (
                      where tipo = 'receita' and status = 'efetivado' and conta
                        and data between :inicio_anterior and :fim_anterior), 0)::text
                      as receitas_anteriores,
                    coalesce(sum(valor) filter (
                      where tipo = 'despesa' and status = 'efetivado' and conta
                        and data between :inicio_anterior and :fim_anterior), 0)::text
                      as despesas_anteriores,
                    -- Saldo sem recorte de início: não existe saldo inicial (`FR-114`),
                    -- o saldo **é** o acumulado dos efetivados.
                    (coalesce(sum(valor) filter (
                       where tipo = 'receita' and status = 'efetivado' and conta), 0)
                     - coalesce(sum(valor) filter (
                       where tipo = 'despesa' and status = 'efetivado' and conta), 0))::text
                      as saldo,
                    (coalesce(sum(valor) filter (
                       where tipo = 'receita' and status = 'efetivado' and conta
                         and data <= :fim_anterior), 0)
                     - coalesce(sum(valor) filter (
                       where tipo = 'despesa' and status = 'efetivado' and conta
                         and data <= :fim_anterior), 0))::text as saldo_anterior,
                    count(*) filter (where status = 'atrasado' and conta)
                      as atrasados_quantidade,
                    coalesce(sum(valor) filter (
                      where status = 'atrasado' and conta), 0)::text as atrasados_valor,
                    -- `RF-46b`: "fixa" é o que já está lançado no futuro, não uma média
                    -- histórica. Ver `dominio/saude_caixa.py`.
                    coalesce(sum(valor) filter (
                      where tipo = 'despesa' and status in {_EM_ABERTO_STATUS} and conta
                        and data between :hoje and :fim_horizonte), 0)::text
                      as despesas_fixas_futuras
                  from base
                ),
                aberto as (
                  select tipo, status, count(*) as quantidade,
                         coalesce(sum(valor), 0)::text as valor
                  from base
                  where status in {_EM_ABERTO_STATUS} and conta
                  group by tipo, status
                ),
                por_mundo as (
                  select mundo,
                         (coalesce(sum(valor) filter (where tipo = 'receita'), 0)
                          - coalesce(sum(valor) filter (where tipo = 'despesa'), 0))::text
                           as saldo
                  from todos_os_mundos
                  group by mundo
                ),
                -- Sparkline dos cards (`FR-057`). Sem o recorte de split, igual à
                -- versão anterior: é série de tendência, não número de fechamento.
                eixo as (
                  select m.mes, t.tipo
                  from generate_series(
                         date_trunc('month', cast(:inicio_tendencia as date)),
                         date_trunc('month', cast(:fim as date)),
                         interval '1 month'
                       ) m(mes)
                  cross join (
                    select unnest(cast(array['receita','despesa'] as tipo_lancamento[])) as tipo
                  ) t
                ),
                tendencia as (
                  select to_char(e.mes, 'YYYY-MM') as rotulo, e.tipo::text as tipo,
                         coalesce(sum(b.valor), 0)::text as valor
                  from eixo e
                  left join base b
                    on date_trunc('month', b.data) = e.mes
                   and b.tipo = e.tipo
                   and b.status = 'efetivado'
                  group by e.mes, e.tipo
                  order by e.mes
                )
                select jsonb_build_object(
                  'periodo',   (select to_jsonb(p) from periodo p),
                  'aberto',    (select coalesce(jsonb_agg(to_jsonb(a)), jsonb_build_array())
                                from aberto a),
                  'por_mundo', (select coalesce(jsonb_object_agg(mundo, saldo),
                                                jsonb_build_object())
                                from por_mundo),
                  'tendencia', (select coalesce(
                                  jsonb_agg(to_jsonb(t) order by t.rotulo),
                                  jsonb_build_array())
                                from tendencia t)
                )
                """),
            {
                "mundos": mundos,
                "inicio": inicio,
                "fim": fim,
                "inicio_anterior": inicio_anterior,
                "fim_anterior": fim_anterior,
                "inicio_tendencia": inicio_tendencia,
                "hoje": hoje,
                "fim_horizonte": fim_horizonte,
            },
        )
    ).scalar_one()

    # Os dois mundos sempre presentes, zerados quando não houve movimento (`FR-003`).
    por_mundo = {"digital": "0", "infra": "0"} | dados["por_mundo"]

    # As três situações sempre aparecem em cada tipo, zeradas quando não há nada —
    # estado vazio explicativo em vez de card com uma linha só (edge case da spec).
    por_tipo_e_situacao = {(linha["tipo"], linha["status"]): linha for linha in dados["aberto"]}

    def _composicao(tipo: str) -> list[dict[str, Any]]:
        return [
            {
                "situacao": situacao,
                "quantidade": por_tipo_e_situacao.get((tipo, situacao), {}).get("quantidade", 0),
                "valor": por_tipo_e_situacao.get((tipo, situacao), {}).get("valor", "0"),
            }
            for situacao in ("programado", "pendente", "atrasado")
        ]

    def _serie(tipo: str) -> list[dict[str, str]]:
        return [
            {"rotulo": linha["rotulo"], "valor": linha["valor"]}
            for linha in dados["tendencia"]
            if linha["tipo"] == tipo
        ]

    return {
        **dados["periodo"],
        "saldo_por_mundo": por_mundo,
        "a_receber": _composicao("receita"),
        "a_pagar": _composicao("despesa"),
        "tendencia_receitas": _serie("receita"),
        "tendencia_despesas": _serie("despesa"),
    }


async def series(
    conexao: AsyncConnection,
    *,
    mundos: list[str],
    inicio: date,
    fim: date,
    inicio_fluxo: date,
    fim_fluxo: date,
    hoje: date,
    limite_maiores: int = 5,
) -> dict[str, Any]:
    """Os gráficos (`FR-059`–`FR-063`), numa consulta.

    `meses` cria o eixo antes dos `left join`: sem isso, um mês sem lançamento sumiria
    e a linha do gráfico ligaria junho a agosto como se julho não existisse.

    `projetado` marca o mês **posterior ao atual** — nele os valores incluem o que
    ainda não aconteceu, e `RN-05` exige que isso seja visualmente distinto.

    `sum() over (order by mes)` faz o acumulado da evolução numa passada. Calcular mês
    a mês em Python custaria 12 consultas — e o acumulado parte do começo dos tempos,
    não do começo do período, porque não existe saldo inicial (`FR-114`).
    """
    dados = (
        await conexao.execute(
            text(f"""
                with base as (
                  select l.id, l.tipo, l.valor, l.data, l.status, l.descricao,
                         l.categoria_id, l.servico_id, not sp.tem_partes as conta
                  from lancamentos_ativos l
                  {_PARTES}
                  where l.mundo = any(cast(:mundos as mundo[]))
                ),
                meses as (
                  select generate_series(
                    date_trunc('month', cast(:inicio_fluxo as date)),
                    date_trunc('month', cast(:fim_fluxo as date)),
                    interval '1 month'
                  )::date as mes
                ),
                fluxo as (
                  select to_char(m.mes, 'YYYY-MM') as mes,
                         coalesce(sum(b.valor) filter (
                           where b.tipo = 'receita' and b.conta), 0)::text as receitas,
                         coalesce(sum(b.valor) filter (
                           where b.tipo = 'despesa' and b.conta), 0)::text as despesas,
                         m.mes > date_trunc('month', cast(:hoje as date)) as projetado
                  from meses m
                  left join base b
                    on date_trunc('month', b.data) = m.mes
                   and b.status <> 'cancelado'
                  group by m.mes
                ),
                anterior as (
                  select coalesce(sum(
                    case when tipo = 'receita' then valor else -valor end), 0) as saldo_base
                  from base
                  where status = 'efetivado' and conta
                    and data < date_trunc('month', cast(:inicio_fluxo as date))
                ),
                por_mes as (
                  select m.mes,
                         coalesce(sum(
                           case when b.tipo = 'receita' then b.valor else -b.valor end
                         ) filter (where b.status = 'efetivado' and b.conta), 0) as resultado
                  from meses m
                  left join base b on date_trunc('month', b.data) = m.mes
                  group by m.mes
                ),
                evolucao as (
                  select to_char(p.mes, 'YYYY-MM') as mes,
                         ((select saldo_base from anterior)
                          + sum(p.resultado) over (order by p.mes))::text as saldo_final,
                         p.mes > date_trunc('month', cast(:hoje as date)) as projetado
                  from por_mes p
                ),
                categoria as (
                  select c.id::text as categoria_id, c.nome, c.cor,
                         coalesce(sum(b.valor), 0)::text as valor
                  from base b
                  join categorias c on c.id = b.categoria_id
                  where b.tipo = 'despesa' and b.status = 'efetivado' and b.conta
                    and b.data between :inicio and :fim
                  group by c.id, c.nome, c.cor
                ),
                maiores as (
                  select b.id::text as lancamento_id, b.descricao, b.valor::text as valor,
                         b.data::text as data, c.nome as categoria_nome
                  from base b
                  join categorias c on c.id = b.categoria_id
                  where b.tipo = 'despesa' and b.status = 'efetivado' and b.conta
                    and b.data between :inicio and :fim
                  order by b.valor desc
                  limit :limite_maiores
                ),
                -- `RF-43b`. Lançamento sem serviço fica de fora — não vira um "Outros"
                -- inventado.
                servico as (
                  select s.id::text as servico_id, s.nome, s.mundo::text as mundo,
                         coalesce(sum(b.valor), 0)::text as valor
                  from base b
                  join servicos s on s.id = b.servico_id
                  where b.tipo = 'receita' and b.status = 'efetivado' and b.conta
                    and b.data between :inicio and :fim
                  group by s.id, s.nome, s.mundo
                )
                select jsonb_build_object(
                  'fluxo_mensal', (select coalesce(jsonb_agg(to_jsonb(f) order by f.mes),
                                                   jsonb_build_array()) from fluxo f),
                  'evolucao_saldo', (select coalesce(jsonb_agg(to_jsonb(e) order by e.mes),
                                                      jsonb_build_array()) from evolucao e),
                  'despesas_por_categoria',
                    (select coalesce(jsonb_agg(to_jsonb(c) order by c.valor::numeric desc),
                                     jsonb_build_array()) from categoria c),
                  'top_despesas',
                    (select coalesce(jsonb_agg(to_jsonb(m) order by m.valor::numeric desc),
                                     jsonb_build_array()) from maiores m),
                  'receita_por_servico',
                    (select coalesce(jsonb_agg(to_jsonb(s) order by s.valor::numeric desc),
                                     jsonb_build_array()) from servico s)
                )
                """),
            {
                "mundos": mundos,
                "inicio": inicio,
                "fim": fim,
                "inicio_fluxo": inicio_fluxo,
                "fim_fluxo": fim_fluxo,
                "hoje": hoje,
                "limite_maiores": limite_maiores,
            },
        )
    ).scalar_one()
    return dados


async def blocos(
    conexao: AsyncConnection,
    *,
    mundos: list[str],
    inicio: date,
    fim: date,
    inicio_anterior: date,
    fim_anterior: date,
    hoje: date,
    ate: date,
    limite_folha: int = 10,
) -> dict[str, Any]:
    """Clientes, funcionários, folha, inadimplência e os próximos 7 dias, numa consulta.

    **Resolvido por `categorias.vinculo`, nunca por nome** (`FR-079`). Um
    `where c.nome = 'Clientes'` funcionaria hoje e quebraria no dia em que alguém
    renomeasse a categoria pela tela — e renomear é permitido.

    `em_aberto_por_cliente` devolve os lançamentos crus agrupados por cliente em vez de
    uma situação já decidida: quem decide se o cliente está atrasado é
    `dominio/inadimplencia.py`, em Python, para a regra ser testável sem Postgres e ser
    **a mesma** na lista, no perfil, no Dashboard e na rotina diária. Sem a agregação
    seria uma consulta por cliente.

    Os blocos que ignoram o período — inadimplência e folha — ignoram de propósito:
    conta que venceu em maio continua vencida em julho.
    """
    dados = (
        await conexao.execute(
            text(f"""
                with base as (
                  select l.id, l.tipo, l.valor, l.data, l.status, l.descricao,
                         l.categoria_id, l.subcategoria_id,
                         l.efetivar_automaticamente, not sp.tem_partes as conta
                  from lancamentos_ativos l
                  {_PARTES}
                  where l.mundo = any(cast(:mundos as mundo[]))
                ),
                -- Totais por subcategoria das categorias **especiais** (`FR-065`, `FR-066`),
                -- no período e no anterior, na mesma régua.
                por_vinculo as (
                  select c.vinculo::text as vinculo,
                         case when b.data between :inicio and :fim
                              then 'atual' else 'anterior' end as janela,
                         s.id::text as subcategoria_id, s.nome,
                         s.cliente_id::text as cliente_id,
                         s.funcionario_id::text as funcionario_id,
                         coalesce(sum(b.valor), 0)::text as valor
                  from base b
                  join categorias c on c.id = b.categoria_id
                  join subcategorias s on s.id = b.subcategoria_id
                  where c.vinculo is not null
                    and b.status = 'efetivado' and b.conta
                    and (b.data between :inicio and :fim
                         or b.data between :inicio_anterior and :fim_anterior)
                  group by c.vinculo, janela, s.id, s.nome, s.cliente_id, s.funcionario_id
                ),
                folha as (
                  select b.id::text as lancamento_id, s.nome, b.data::text as data,
                         b.valor::text as valor, b.status::text as status, b.data as ordem
                  from base b
                  join categorias c on c.id = b.categoria_id
                  join subcategorias s on s.id = b.subcategoria_id
                  where c.vinculo = 'funcionario'
                    and b.data >= :hoje
                    and b.status in {_EM_ABERTO_STATUS} and b.conta
                  order by b.data
                  limit :limite_folha
                ),
                inadimplencia as (
                  select cl.id::text as cliente_id, cl.nome, a.em_aberto
                  from clientes cl
                  join lateral (
                    select jsonb_agg(jsonb_build_object(
                             'data', b.data::text, 'valor', b.valor::text,
                             'status', b.status,
                             'efetivar_automaticamente', b.efetivar_automaticamente
                           )) as em_aberto
                    from base b
                    join categorias c on c.id = b.categoria_id
                    join subcategorias s on s.id = b.subcategoria_id
                    where s.cliente_id = cl.id
                      and c.vinculo = 'cliente'
                      and b.tipo = 'receita'
                      and b.status in ('pendente','atrasado')
                  ) a on a.em_aberto is not null
                  where cl.arquivado_em is null
                ),
                proximos as (
                  select b.id::text as lancamento_id, b.data::text as data,
                         b.tipo::text as tipo, b.descricao, b.valor::text as valor,
                         b.status::text as status, b.data as ordem_data, b.tipo as ordem_tipo
                  from base b
                  where b.data between :hoje and :ate
                    and b.status in {_EM_ABERTO_STATUS} and b.conta
                )
                select jsonb_build_object(
                  'por_vinculo', (select coalesce(
                                    jsonb_agg(to_jsonb(v) order by v.valor::numeric desc),
                                    jsonb_build_array()) from por_vinculo v),
                  'folha', (select coalesce(jsonb_agg(to_jsonb(f) - 'ordem' order by f.ordem),
                                            jsonb_build_array()) from folha f),
                  'inadimplencia', (select coalesce(jsonb_agg(to_jsonb(i)),
                                                    jsonb_build_array()) from inadimplencia i),
                  'proximos', (select coalesce(
                                 jsonb_agg(to_jsonb(p) - 'ordem_data' - 'ordem_tipo'
                                           order by p.ordem_data, p.ordem_tipo),
                                 jsonb_build_array()) from proximos p)
                )
                """),
            {
                "mundos": mundos,
                "inicio": inicio,
                "fim": fim,
                "inicio_anterior": inicio_anterior,
                "fim_anterior": fim_anterior,
                "hoje": hoje,
                "ate": ate,
                "limite_folha": limite_folha,
            },
        )
    ).scalar_one()

    def _vinculo(nome: str, janela: str) -> list[dict[str, Any]]:
        return [
            item
            for item in dados["por_vinculo"]
            if item["vinculo"] == nome and item["janela"] == janela
        ]

    return {
        "clientes": _vinculo("cliente", "atual"),
        "clientes_anterior": _vinculo("cliente", "anterior"),
        "funcionarios": _vinculo("funcionario", "atual"),
        "funcionarios_anterior": _vinculo("funcionario", "anterior"),
        "proximos_da_folha": dados["folha"],
        "em_aberto_por_cliente": dados["inadimplencia"],
        "proximos_dias": dados["proximos"],
    }
