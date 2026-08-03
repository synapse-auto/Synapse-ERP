"""Extrato — agrupamento por dia, semana ou mês, com saldo acumulado.

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T095).
Só leitura: o módulo não tem `repositorio.py` separado porque não há escrita a isolar
(plan.md §Project Structure já previa `extrato/` com `rotas.py` e `servico.py`).

## A garantia que este módulo precisa dar

**O `saldo_acumulado` do último grupo é igual a `resumo.saldo_final`.** É o teste de
aceitação da história 7, e o servidor garante — não é coincidência de arredondamento. Sai
disso a decisão mais importante daqui: o acumulado parte do saldo **anterior ao período**
(tudo que já estava efetivado antes do primeiro dia) e soma grupo a grupo. Começar do zero
daria um número que não bate com o saldo real, porque não existe saldo inicial (`FR-114`).

**Grupo futuro não entra no acumulado** (`FR-052`, `RN-05`). Ele aparece marcado
`previsto: true`, com seus próprios totais, e o acumulado dele repete o último valor
realizado. Somar o previsto no acumulado faria a linha do saldo mostrar dinheiro que não
existe.

Tarefa: T095
"""

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroValidacao

Agrupamento = Literal["dia", "semana", "mes"]

AGRUPAMENTOS: tuple[str, ...] = ("dia", "semana", "mes")

# `date_trunc` não aceita parâmetro vindo do cliente sem virar SQL montado por
# concatenação. A tradução passa por este dicionário fechado: o que não está aqui é
# recusado antes de chegar perto do banco.
_UNIDADE = {"dia": "day", "semana": "week", "mes": "month"}

_SEM_PAI_DE_SPLIT = """
  not exists (select 1 from lancamentos p
              where p.lancamento_pai_id = l.id and p.excluido_em is null)
"""

MESES_PT = {
    1: "jan",
    2: "fev",
    3: "mar",
    4: "abr",
    5: "mai",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "set",
    10: "out",
    11: "nov",
    12: "dez",
}


def valida_agrupamento(agrupamento: str) -> str:
    if agrupamento not in AGRUPAMENTOS:
        raise ErroValidacao(
            f"Agrupamento '{agrupamento}' não existe.",
            requisito="FR-047",
            campos={"agrupamento": f"Aceitos: {', '.join(AGRUPAMENTOS)}."},
        )
    return agrupamento


def rotulo_do_grupo(inicio: date, fim: date, agrupamento: str) -> str:
    """Texto pronto para a tela, em PT-BR (`RNF-03`).

    Montado no servidor porque o rótulo depende do agrupamento escolhido, e o frontend
    reimplementaria a mesma regra em outra língua.
    """
    if agrupamento == "dia":
        return inicio.strftime("%d/%m/%Y")
    if agrupamento == "semana":
        return f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m/%Y')}"
    return f"{MESES_PT[inicio.month]}/{inicio.year}"


async def saldo_antes(conexao: AsyncConnection, *, mundos: list[str], inicio: date) -> Decimal:
    """Tudo que já estava efetivado antes do período — a base do acumulado."""
    valor = (
        await conexao.execute(
            text(f"""
                select coalesce(sum(
                  case when l.tipo = 'receita' then l.valor else -l.valor end), 0)
                from lancamentos_ativos l
                where l.mundo = any(cast(:mundos as mundo[]))
                  and l.status = 'efetivado' and {_SEM_PAI_DE_SPLIT}
                  and l.data < :inicio
                """),
            {"mundos": mundos, "inicio": inicio},
        )
    ).scalar_one()
    return Decimal(str(valor or 0))


async def totais_do_periodo(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date
) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text(f"""
                    select
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'receita' and l.status = 'efetivado'
                          and {_SEM_PAI_DE_SPLIT}), 0) as receitas,
                      coalesce(sum(l.valor) filter (
                        where l.tipo = 'despesa' and l.status = 'efetivado'
                          and {_SEM_PAI_DE_SPLIT}), 0) as despesas,
                      count(*) filter (where l.status = 'efetivado') as quantidade
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


async def lancamentos_do_periodo(
    conexao: AsyncConnection, *, mundos: list[str], inicio: date, fim: date, agrupamento: str
) -> list[dict[str, Any]]:
    """Os lançamentos com a chave do grupo já calculada pelo banco.

    Agrupar no Postgres e não em Python: `date_trunc('week', …)` conhece a semana ISO
    (que começa na segunda, a mesma convenção de `comum/periodo.py`), e reimplementar
    isso em Python daria duas definições de semana no mesmo sistema.
    """
    unidade = _UNIDADE[valida_agrupamento(agrupamento)]
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select
                      date_trunc('{unidade}', l.data)::date as grupo_inicio,
                      (date_trunc('{unidade}', l.data)
                        + interval '1 {unidade}' - interval '1 day')::date as grupo_fim,
                      l.id, l.mundo, l.tipo, l.descricao, l.valor, l.data, l.status,
                      c.nome as categoria_nome, c.cor as categoria_cor,
                      s.nome as subcategoria_nome
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    left join subcategorias s on s.id = l.subcategoria_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.data between :inicio and :fim
                      and l.status <> 'cancelado'
                      and {_SEM_PAI_DE_SPLIT}
                    order by l.data, l.criado_em
                    """),
                {"mundos": mundos, "inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def pendencias(conexao: AsyncConnection, *, mundos: list[str], hoje: date) -> dict[str, Any]:
    """A seção fixa "A pagar / A receber" (`FR-051`).

    **Ignora o filtro de período de propósito**: pendência não é histórico. Uma conta
    vencida em maio continua a pagar em julho, e escondê-la porque o filtro está em
    julho é exatamente o erro que a seção existe para evitar.
    """
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select l.id as lancamento_id, l.tipo, l.descricao, l.valor, l.data,
                           l.status, l.data < :hoje as vencido
                    from lancamentos_ativos l
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.status in ('programado','pendente','atrasado')
                      and {_SEM_PAI_DE_SPLIT}
                    order by l.data
                    """),
                {"mundos": mundos, "hoje": hoje},
            )
        )
        .mappings()
        .all()
    )

    def _monta(tipo: str) -> list[dict[str, Any]]:
        return [
            {
                "lancamento_id": str(linha["lancamento_id"]),
                "descricao": linha["descricao"],
                "valor": f"{Decimal(str(linha['valor'])):.2f}",
                "data": linha["data"].isoformat(),
                "status": linha["status"],
                "vencido": linha["vencido"],
            }
            for linha in linhas
            if linha["tipo"] == tipo
        ]

    return {"a_pagar": _monta("despesa"), "a_receber": _monta("receita")}


def monta_grupos(
    linhas: list[dict[str, Any]], *, agrupamento: str, saldo_base: Decimal, hoje: date
) -> list[dict[str, Any]]:
    """Agrupa e acumula. **Só `efetivado` move o acumulado** (`RN-05`).

    O grupo futuro aparece com `previsto: true` e seus totais próprios, mas o acumulado
    dele repete o último valor realizado — a linha do saldo não pode subir por causa de
    dinheiro que ainda não entrou.
    """
    grupos: dict[date, dict[str, Any]] = {}
    for linha in linhas:
        chave = linha["grupo_inicio"]
        grupo = grupos.setdefault(
            chave,
            {
                "inicio": chave,
                "fim": linha["grupo_fim"],
                "lancamentos": [],
                "receitas": Decimal("0.00"),
                "despesas": Decimal("0.00"),
                "receitas_efetivadas": Decimal("0.00"),
                "despesas_efetivadas": Decimal("0.00"),
            },
        )
        valor = Decimal(str(linha["valor"]))
        grupo["lancamentos"].append(
            {
                "id": str(linha["id"]),
                "mundo": linha["mundo"],
                "tipo": linha["tipo"],
                "descricao": linha["descricao"],
                "valor": f"{valor:.2f}",
                "data": linha["data"].isoformat(),
                "status": linha["status"],
                "categoria": {"nome": linha["categoria_nome"], "cor": linha["categoria_cor"]},
                "subcategoria": linha["subcategoria_nome"],
            }
        )
        if linha["tipo"] == "receita":
            grupo["receitas"] += valor
            if linha["status"] == "efetivado":
                grupo["receitas_efetivadas"] += valor
        else:
            grupo["despesas"] += valor
            if linha["status"] == "efetivado":
                grupo["despesas_efetivadas"] += valor

    acumulado = saldo_base
    montados = []
    for chave in sorted(grupos):
        grupo = grupos[chave]
        previsto = grupo["inicio"] > hoje
        if not previsto:
            acumulado += grupo["receitas_efetivadas"] - grupo["despesas_efetivadas"]
        montados.append(
            {
                "rotulo": rotulo_do_grupo(grupo["inicio"], grupo["fim"], agrupamento),
                "inicio": grupo["inicio"].isoformat(),
                "fim": grupo["fim"].isoformat(),
                "previsto": previsto,
                "lancamentos": grupo["lancamentos"],
                "totais": {
                    "receitas": f"{grupo['receitas']:.2f}",
                    "despesas": f"{grupo['despesas']:.2f}",
                },
                "saldo_acumulado": f"{acumulado:.2f}",
            }
        )
    return montados


def monta_grafico(grupos: list[dict[str, Any]]) -> list[dict[str, str]]:
    """`FR-050` — receitas × despesas por grupo, o mesmo recorte da lista.

    O `rotulo` aqui é a **data ISO**, não o texto do cabeçalho do grupo
    (contracts/consultas.md §2: `"rotulo": "2026-07-10"` no gráfico contra
    `"10/07/2026"` na lista). São coisas diferentes de propósito: o cabeçalho já é
    texto pronto, e o eixo do gráfico precisa da data para poder formatá-la no
    tamanho que couber. Devolver o texto pronto nos dois fazia a tela chamar
    `dataCurta("05/08/2026")` e morrer em `RangeError: Invalid time value`,
    derrubando o Extrato inteiro.
    """
    return [
        {
            "rotulo": grupo["inicio"],
            "receitas": grupo["totais"]["receitas"],
            "despesas": grupo["totais"]["despesas"],
            "previsto": grupo["previsto"],
        }
        for grupo in grupos
    ]
