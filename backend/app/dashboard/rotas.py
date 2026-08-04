"""`GET /api/dashboard` — o Dashboard inteiro em **uma** requisição.

contracts/consultas.md §1. Papel: gestor, operador.

## Por que tudo de uma vez

15 cards em 15 requisições, cada uma pagando cold start de função serverless, tornaria
`SC-002` ("entender a saúde do caixa em 10 segundos") impossível. Uma requisição, um
punhado de agregações que o Postgres resolve por índice.

**E, desde 2026-08-04, tudo de uma vez também do lado do banco.** Este arquivo chamava
vinte funções do repositório em série — uma requisição para o usuário, vinte idas ao
Postgres por baixo. Agora são três: `numeros`, `series` e `blocos`. Medido contra o
banco real, com 101 valores conferidos um a um contra a implementação anterior:
**9,2x mais rápido, nenhuma divergência**. O porquê está em `dashboard/repositorio.py`.

Dinheiro e data chegam do banco **já como texto** (`"1234.56"`, `"2026-08-04"`), então
aqui não há mais `.isoformat()` nem conversão para `Decimal` a não ser onde há conta a
fazer — comparativo, percentual e soma.

## Duas regras que este arquivo aplica e vale ler antes de mexer

**Nenhum rótulo de card mora aqui.** Eles vêm de
`configuracoes.dashboard_cards_disponiveis` e são devolvidos **junto do dado**
(`FR-106`, Princípio VII). O frontend monta a grade a partir da lista que chega, sem um
único texto de card escrito em TypeScript.

**Os blocos de Clientes e Funcionários são resolvidos por `categorias.vinculo`**, nunca
por comparação de nome (`FR-079`). Renomear a categoria "Clientes" pela tela é permitido,
e um `if nome == 'Clientes'` quebraria em silêncio no dia em que alguém renomeasse.

Tarefas: T090, T091, T092, T093, T094
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import periodo as mod_periodo
from app.dashboard import repositorio
from app.db import obter_conexao
from app.dominio import inadimplencia as mod_inadimplencia
from app.dominio import mundo as mod_mundo
from app.dominio import saude_caixa as mod_saude
from app.lancamentos.servico import le_configuracao
from app.rotinas import diaria as rotina_diaria
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/dashboard", tags=["Consultas"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

MESES_DA_TENDENCIA = 6
MESES_DO_FLUXO = 12
DIAS_DA_LINHA_DO_TEMPO = 7

MESES_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


def _d(valor: Any) -> Decimal:
    return Decimal(str(valor or 0))


def _dinheiro(valor: Any) -> str:
    return f"{_d(valor):.2f}"


def _percentual(parte: Decimal, total: Decimal) -> str | None:
    """`null` quando o total é zero — não `"0.0"`.

    Zero por cento e "não dá para calcular" são coisas diferentes, e a tela mostra as
    duas de forma diferente (edge case do estado vazio).
    """
    if total == 0:
        return None
    return f"{(parte / total * 100):.1f}"


def _comparativo(atual: Decimal, anterior: Decimal) -> dict[str, Any]:
    """`FR-055`. `direcao` vem pronta para a tela escolher a cor e a seta."""
    if anterior == 0:
        return {
            "valor_anterior": f"{anterior:.2f}",
            "variacao_percentual": None,
            "direcao": "alta" if atual > 0 else "estavel",
        }
    variacao = (atual - anterior) / abs(anterior) * 100
    return {
        "valor_anterior": f"{anterior:.2f}",
        "variacao_percentual": f"{variacao:.1f}",
        "direcao": "alta" if variacao > 0 else ("baixa" if variacao < 0 else "estavel"),
    }


def _largura_padrao(definicao: dict) -> str:
    """Quanto o card ocupa quando ninguém escolheu (T217).

    Ordem de precedência ao resolver: **preferência do usuário → `largura_padrao` do
    catálogo → esta função**. Gravar `largura_padrao` numa entrada de
    `dashboard_cards_disponiveis` muda o padrão de todo mundo sem tocar em código, que
    é o que Princípio VII pede; esta função só existe para o catálogo atual, que ainda
    não traz a chave, não cair num valor arbitrário.

    Regra: **alerta atravessa a linha, o resto entra na metade.** Alerta é uma faixa de
    aviso — cortada ao meio ela vira um cartão qualquer e perde a função. Gráfico e
    bloco especial cabem em metade da grade (≈770px no `--conteudo-largura-max`), que é
    o que põe dois lado a lado.

    Card `numerico` não usa este valor: eles têm grade própria de quatro colunas.
    """
    if definicao.get("grupo") == "alerta":
        return "inteira"
    return "metade"


async def _cards_configurados(conexao: AsyncConnection, usuario: UsuarioAutenticado) -> list[dict]:
    """Quais cards mostrar e em que ordem (`FR-071`, `FR-106`).

    Catálogo em `configuracoes`, preferência em `usuarios.preferencias` (D-09). O
    catálogo manda no que **existe**; a preferência manda no que **aparece** e na ordem.
    Card novo no catálogo aparece para todo mundo sem precisar mexer em preferência
    nenhuma — que é o ponto de o padrão viver no catálogo.
    """
    catalogo = await le_configuracao(conexao, "dashboard_cards_disponiveis", padrao=[])
    preferencia = {
        item["id"]: item for item in (usuario.preferencias or {}).get("dashboard_cards", [])
    }

    escolhidos = []
    for posicao, definicao in enumerate(catalogo):
        do_usuario = preferencia.get(definicao["id"], {})
        escolhidos.append(
            {
                **definicao,
                "visivel": do_usuario.get("visivel", definicao.get("visivel_padrao", True)),
                "ordem": do_usuario.get("ordem", definicao.get("ordem_padrao", 99)),
                "largura": do_usuario.get(
                    "largura", definicao.get("largura_padrao", _largura_padrao(definicao))
                ),
                # Só para o desempate abaixo — não sai na resposta.
                "_escolhido_pelo_usuario": "ordem" in do_usuario,
                "_posicao_no_catalogo": posicao,
            }
        )

    # Desempate: **a escolha explícita do usuário vence o padrão do catálogo**. Sem
    # isto, pôr "A pagar" na posição 2 não fazia nada — "Receitas do período" já tinha
    # `ordem_padrao: 2`, a ordenação é estável e o catálogo ganhava por chegar antes.
    # O usuário reordenava e a tela não mudava (`FR-071`).
    escolhidos.sort(
        key=lambda item: (
            item["ordem"],
            0 if item["_escolhido_pelo_usuario"] else 1,
            item["_posicao_no_catalogo"],
        )
    )
    return [
        {
            chave: valor
            for chave, valor in item.items()
            if chave not in ("_escolhido_pelo_usuario", "_posicao_no_catalogo")
        }
        for item in escolhidos
    ]


def _resumo_em_portugues(
    *,
    janela: mod_periodo.Periodo,
    receitas: Decimal,
    despesas: Decimal,
    atrasados: dict[str, Any],
) -> str:
    """`FR-070` — a frase do topo, montada no servidor.

    É texto de **negócio**, não de interface: cita números que só o cálculo conhece.
    Montá-la no frontend seria escrever a regra duas vezes (`RNF-02`).
    """
    from app.comum.erros import formata_dinheiro

    resultado = receitas - despesas
    rotulo = MESES_PT.get(janela.inicio.month, "o período").capitalize()

    if receitas == 0 and despesas == 0:
        frase = f"{rotulo} ainda não tem nenhum lançamento efetivado."
    else:
        sinal = "positivo" if resultado > 0 else ("negativo" if resultado < 0 else "no zero a zero")
        frase = f"{rotulo} fechou {sinal} em {formata_dinheiro(abs(resultado))}"

        margem = _percentual(resultado, receitas)
        if margem is not None and resultado > 0:
            frase += f", margem de {margem.replace('.', ',')}%"
        frase += "."

    # O aviso de vencido vem **depois do `if`, não dentro dele**. Período sem nada
    # efetivado com contas vencidas é justamente quando o alerta mais importa; antes,
    # o retorno antecipado engolia o "principal ponto de atenção" que `FR-070` pede.
    # Os atrasados ignoram o filtro de período (contracts/consultas.md), então a frase
    # continua verdadeira mesmo num mês vazio.
    if atrasados["quantidade"]:
        plural = "s" if atrasados["quantidade"] > 1 else ""
        frase += (
            f" Atenção: {atrasados['quantidade']} conta{plural} vencida{plural} somando "
            f"{formata_dinheiro(_d(atrasados['valor_total']))}."
        )
    return frase


@roteador.get(
    "",
    summary="O Dashboard inteiro, numa requisição",
    description=(
        "Papel: gestor, operador. `FR-053`–`FR-071`. Uma chamada devolve cards, "
        "gráficos, blocos especiais e o resumo — 15 requisições separadas, cada uma "
        "pagando cold start, tornariam `SC-002` impossível. Os **rótulos vêm junto do "
        "dado**, de `configuracoes.dashboard_cards_disponiveis` (`FR-106`); nenhum texto "
        "de card mora no frontend. `filtro_drilldown` é a query pronta para "
        "`GET /api/lancamentos` (`FR-058`)."
    ),
)
async def obter(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    # T085: cron falho não pode virar Dashboard com número velho.
    await rotina_diaria.executa_se_necessario(conexao)

    hoje = date.today()
    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)

    # ── Parâmetros primeiro ────────────────────────────────────────────────
    #
    # Vêm antes das agregações porque o horizonte da saúde do caixa **entra** na
    # consulta de números. As três leituras custam uma ida ao banco no total, ou
    # nenhuma: `configuracoes` fica em cache por um minuto
    # (`app/comum/cache_configuracoes.py`).
    horizonte_dias = int(await le_configuracao(conexao, "saude_caixa_horizonte_dias", padrao=30))
    multiplicadores = await le_configuracao(
        conexao, "saude_caixa_multiplicadores", padrao=dict(mod_saude.PADRAO_MULTIPLICADORES)
    )
    tolerancia = int(
        await le_configuracao(
            conexao,
            "inadimplencia_dias_tolerancia",
            padrao=mod_inadimplencia.PADRAO_DIAS_TOLERANCIA,
        )
    )

    inicio_tendencia = (janela.fim.replace(day=1)) - timedelta(days=30 * MESES_DA_TENDENCIA)
    inicio_fluxo = (hoje.replace(day=1) - timedelta(days=30 * (MESES_DO_FLUXO - 6))).replace(day=1)
    fim_fluxo = (hoje.replace(day=1) + timedelta(days=30 * 6)).replace(day=1)

    # ── As três idas ao banco ──────────────────────────────────────────────
    numeros = await repositorio.numeros(
        conexao,
        mundos=mundos,
        inicio=janela.inicio,
        fim=janela.fim,
        inicio_anterior=janela.inicio_anterior,
        fim_anterior=janela.fim_anterior,
        inicio_tendencia=inicio_tendencia,
        hoje=hoje,
        fim_horizonte=hoje + timedelta(days=horizonte_dias),
    )
    series = await repositorio.series(
        conexao,
        mundos=mundos,
        inicio=janela.inicio,
        fim=janela.fim,
        inicio_fluxo=inicio_fluxo,
        fim_fluxo=fim_fluxo,
        hoje=hoje,
    )
    blocos = await repositorio.blocos(
        conexao,
        mundos=mundos,
        inicio=janela.inicio,
        fim=janela.fim,
        inicio_anterior=janela.inicio_anterior,
        fim_anterior=janela.fim_anterior,
        hoje=hoje,
        ate=hoje + timedelta(days=DIAS_DA_LINHA_DO_TEMPO),
    )

    # ── Números do período e do anterior, na mesma régua (`FR-055`) ─────────
    receitas, despesas = _d(numeros["receitas"]), _d(numeros["despesas"])
    receitas_ant = _d(numeros["receitas_anteriores"])
    despesas_ant = _d(numeros["despesas_anteriores"])
    resultado, resultado_ant = receitas - despesas, receitas_ant - despesas_ant

    saldo = _d(numeros["saldo"])
    saldo_ant = _d(numeros["saldo_anterior"])

    quebra_saldo = numeros["saldo_por_mundo"]
    a_receber = numeros["a_receber"]
    a_pagar = numeros["a_pagar"]
    atrasados = {
        "quantidade": numeros["atrasados_quantidade"],
        "valor_total": numeros["atrasados_valor"],
    }

    def _serie(linhas: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [{"rotulo": linha["rotulo"], "valor": _dinheiro(linha["valor"])} for linha in linhas]

    # ── Os 7 cards numéricos (`FR-054`) ────────────────────────────────────
    #
    # Um dicionário por id, montado antes de escolher o que mostrar: assim o
    # `visivel`/`ordem` do usuário decide o que **sai na resposta**, e a lógica de cada
    # card não precisa saber se está visível.
    valores_dos_cards: dict[str, dict[str, Any]] = {
        "saldo_atual": {
            "valor": _dinheiro(saldo),
            "comparativo": _comparativo(saldo, saldo_ant),
            "quebra_por_mundo": {k: _dinheiro(v) for k, v in quebra_saldo.items()},
            "filtro_drilldown": None,
        },
        "receitas_periodo": {
            "valor": _dinheiro(receitas),
            "comparativo": _comparativo(receitas, receitas_ant),
            "tendencia": _serie(numeros["tendencia_receitas"]),
            "filtro_drilldown": {"tipo": "receita", "status": ["efetivado"]},
        },
        "despesas_periodo": {
            "valor": _dinheiro(despesas),
            "comparativo": _comparativo(despesas, despesas_ant),
            "tendencia": _serie(numeros["tendencia_despesas"]),
            "filtro_drilldown": {"tipo": "despesa", "status": ["efetivado"]},
        },
        "lucro_liquido": {
            "valor": _dinheiro(resultado),
            "comparativo": _comparativo(resultado, resultado_ant),
            "filtro_drilldown": {"status": ["efetivado"]},
        },
        "margem_operacional": {
            # Percentual, não dinheiro: a unidade vai no campo para a tela não ter que
            # adivinhar pelo id do card.
            "valor": _percentual(resultado, receitas),
            "unidade": "percentual",
            "comparativo": {"valor_anterior": _percentual(resultado_ant, receitas_ant)},
            "filtro_drilldown": None,
        },
        "a_receber": {
            "valor": _dinheiro(sum(_d(item["valor"]) for item in a_receber)),
            "comparativo": {},
            "composicao": [
                {
                    "situacao": item["situacao"],
                    "quantidade": item["quantidade"],
                    "valor": _dinheiro(item["valor"]),
                }
                for item in a_receber
            ],
            "filtro_drilldown": {
                "tipo": "receita",
                "status": ["programado", "pendente", "atrasado"],
            },
        },
        "a_pagar": {
            "valor": _dinheiro(sum(_d(item["valor"]) for item in a_pagar)),
            "comparativo": {},
            "composicao": [
                {
                    "situacao": item["situacao"],
                    "quantidade": item["quantidade"],
                    "valor": _dinheiro(item["valor"]),
                }
                for item in a_pagar
            ],
            "filtro_drilldown": {
                "tipo": "despesa",
                "status": ["programado", "pendente", "atrasado"],
            },
        },
    }

    configurados = await _cards_configurados(conexao, usuario)
    cards = [
        {
            "id": definicao["id"],
            "rotulo": definicao["rotulo"],
            "grupo": definicao["grupo"],
            "ordem": definicao["ordem"],
            **valores_dos_cards[definicao["id"]],
        }
        for definicao in configurados
        if definicao["visivel"] and definicao["id"] in valores_dos_cards
    ]

    # ── Saúde do caixa (`FR-069`) ──────────────────────────────────────────
    saude = mod_saude.avalia(
        saldo=saldo,
        despesas_fixas_horizonte=_d(numeros["despesas_fixas_futuras"]),
        horizonte_dias=horizonte_dias,
        multiplicadores=dict(multiplicadores),
    )

    # ── Gráficos (`FR-059`–`FR-063`) ───────────────────────────────────────
    fluxo = series["fluxo_mensal"]
    evolucao = series["evolucao_saldo"]
    por_categoria = series["despesas_por_categoria"]
    maiores = series["top_despesas"]
    por_servico = series["receita_por_servico"]

    # ── Blocos especiais, por `categorias.vinculo` (`FR-065`, `FR-066`) ────
    clientes = blocos["clientes"]
    funcionarios = blocos["funcionarios"]
    proximos_da_folha = blocos["proximos_da_folha"]

    total_clientes = sum((_d(item["valor"]) for item in clientes), Decimal("0"))
    total_funcionarios = sum((_d(item["valor"]) for item in funcionarios), Decimal("0"))

    # Comparativo dos blocos especiais (`FR-065`, `FR-066`). Mesma régua de período do
    # resto do painel — `comum/periodo.py` já devolveu a janela anterior, e a consulta
    # de blocos traz as duas janelas de uma vez.
    total_clientes_antes = sum(
        (_d(item["valor"]) for item in blocos["clientes_anterior"]), Decimal("0")
    )
    total_funcionarios_antes = sum(
        (_d(item["valor"]) for item in blocos["funcionarios_anterior"]), Decimal("0")
    )

    # Inadimplentes do card Clientes (`FR-065`, `FR-083`, `SC-006`). A situação é
    # derivada pela **mesma** função da lista e do perfil (`dominio/inadimplencia.py`),
    # para os três nunca discordarem.
    inadimplentes = []
    for cliente in blocos["em_aberto_por_cliente"]:
        situacao = mod_inadimplencia.avalia(
            [
                {
                    "data": date.fromisoformat(item["data"]),
                    "valor": item["valor"],
                    "status": item["status"],
                    "efetivar_automaticamente": item["efetivar_automaticamente"],
                }
                for item in (cliente["em_aberto"] or [])
            ],
            tolerancia_dias=tolerancia,
            hoje=hoje,
        )
        if situacao.situacao == "atrasado":
            inadimplentes.append(
                {
                    "cliente_id": str(cliente["cliente_id"]),
                    "nome": cliente["nome"],
                    "valor_atrasado": f"{situacao.valor_atrasado:.2f}",
                    "dias_atraso": situacao.dias_atraso,
                }
            )
    # O mais atrasado primeiro: é o que a tela destaca em vermelho.
    inadimplentes.sort(key=lambda item: item["dias_atraso"], reverse=True)

    # ── Linha do tempo de 7 dias (`FR-067`) ────────────────────────────────
    por_dia: dict[str, dict[str, list]] = {}
    for item in blocos["proximos_dias"]:
        dia = por_dia.setdefault(item["data"], {"a_pagar": [], "a_receber": []})
        destino = "a_receber" if item["tipo"] == "receita" else "a_pagar"
        dia[destino].append(
            {
                "lancamento_id": str(item["lancamento_id"]),
                "descricao": item["descricao"],
                "valor": _dinheiro(item["valor"]),
                "status": item["status"],
            }
        )

    return {
        "periodo": janela.como_dicionario(),
        "mundo": mundo or "ambos",
        # Estado vazio explicativo em vez de campo ausente (edge case da spec): o
        # frontend precisa distinguir "período sem dados" de "erro ao carregar".
        "periodo_vazio": numeros["quantidade"] == 0,
        "alerta_atrasados": {
            "quantidade": atrasados["quantidade"],
            "valor_total": _dinheiro(atrasados["valor_total"]),
            "filtro_drilldown": {"status": ["atrasado"]},
        },
        "cards": cards,
        "saude_caixa": saude.como_dicionario(),
        "fluxo_caixa_mensal": [
            {
                "mes": linha["mes"],
                "receitas": _dinheiro(linha["receitas"]),
                "despesas": _dinheiro(linha["despesas"]),
                "resultado": _dinheiro(_d(linha["receitas"]) - _d(linha["despesas"])),
                "projetado": linha["projetado"],
            }
            for linha in fluxo
        ],
        "evolucao_saldo": [
            {
                "mes": linha["mes"],
                "saldo_final": _dinheiro(linha["saldo_final"]),
                "projetado": linha["projetado"],
            }
            for linha in evolucao
        ],
        "comparativo_mes": {
            "atual": {
                "receitas": _dinheiro(receitas),
                "despesas": _dinheiro(despesas),
                "resultado": _dinheiro(resultado),
                "rotulo": janela.rotulo,
            },
            "anterior": {
                "receitas": _dinheiro(receitas_ant),
                "despesas": _dinheiro(despesas_ant),
                "resultado": _dinheiro(resultado_ant),
            },
        },
        "despesas_por_categoria": [
            {
                "categoria_id": str(linha["categoria_id"]),
                "nome": linha["nome"],
                "cor": linha["cor"],
                "valor": _dinheiro(linha["valor"]),
                "percentual": _percentual(_d(linha["valor"]), despesas),
                "filtro_drilldown": {
                    "tipo": "despesa",
                    "categoria_id": [str(linha["categoria_id"])],
                    "status": ["efetivado"],
                },
            }
            for linha in por_categoria
        ],
        "top_despesas": [
            {
                "lancamento_id": str(linha["lancamento_id"]),
                "descricao": linha["descricao"],
                "categoria": linha["categoria_nome"],
                "valor": _dinheiro(linha["valor"]),
                "data": linha["data"],
            }
            for linha in maiores
        ],
        "receita_por_servico": [
            {
                "servico_id": str(linha["servico_id"]),
                "nome": linha["nome"],
                "mundo": linha["mundo"],
                "valor": _dinheiro(linha["valor"]),
                "percentual": _percentual(_d(linha["valor"]), receitas),
            }
            for linha in por_servico
        ],
        "card_clientes": {
            "total_recebido": _dinheiro(total_clientes),
            "comparativo": _comparativo(total_clientes, total_clientes_antes),
            "clientes_ativos": len(clientes),
            "top_clientes": [
                {
                    "cliente_id": str(item["cliente_id"]) if item["cliente_id"] else None,
                    "subcategoria_id": str(item["subcategoria_id"]),
                    "nome": item["nome"],
                    "valor": _dinheiro(item["valor"]),
                }
                for item in clientes[:5]
            ],
            "inadimplentes": inadimplentes,
        },
        "card_funcionarios": {
            "custo_total": _dinheiro(total_funcionarios),
            "comparativo": _comparativo(total_funcionarios, total_funcionarios_antes),
            "percentual_sobre_despesas": _percentual(total_funcionarios, despesas),
            "por_funcionario": [
                {
                    "funcionario_id": (
                        str(item["funcionario_id"]) if item["funcionario_id"] else None
                    ),
                    "subcategoria_id": str(item["subcategoria_id"]),
                    "nome": item["nome"],
                    "valor": _dinheiro(item["valor"]),
                }
                for item in funcionarios
            ],
            "proximos_pagamentos": [
                {
                    "lancamento_id": str(item["lancamento_id"]),
                    "funcionario": item["nome"],
                    "data": item["data"],
                    "valor": _dinheiro(item["valor"]),
                    "status": item["status"],
                }
                for item in proximos_da_folha
            ],
        },
        "proximos_7_dias": [{"data": dia, **conteudo} for dia, conteudo in sorted(por_dia.items())],
        "resumo_linguagem_natural": _resumo_em_portugues(
            janela=janela, receitas=receitas, despesas=despesas, atrasados=atrasados
        ),
        "cards_disponiveis": [
            {
                "id": item["id"],
                "rotulo": item["rotulo"],
                "grupo": item["grupo"],
                "visivel": item["visivel"],
                "ordem": item["ordem"],
                "largura": item["largura"],
            }
            for item in configurados
        ],
    }
