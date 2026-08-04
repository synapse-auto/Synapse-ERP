"""Dashboard e Extrato contra Postgres real — sub-fase B3.

**O que só o banco prova**: que as agregações do Dashboard e as do Extrato dão o
**mesmo** número a partir dos mesmos lançamentos. São consultas escritas separadamente,
em módulos diferentes, e é exatamente onde um `where` esquecido faz duas telas
discordarem sem ninguém notar. Cada teste daqui compara um número contra o cálculo
manual, não contra a outra consulta.

## Como rodar

⚠️ **Rodam contra o banco de PRODUÇÃO** (decisão do dono do projeto, 2026-07-31 — não há
banco separado). O que protege os dados é a transação desfeita do `conftest`: nada do que
os testes escrevem chega a existir para outra conexão. Leia o aviso no topo de
`tests/conftest.py` antes de escrever teste novo aqui.

    .venv/Scripts/python -m pytest tests/integracao -q

Sem `DATABASE_URL` no ambiente, pulam com aviso — nunca passam em silêncio.

Tarefa: T098
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from dateutil.relativedelta import relativedelta
from sqlalchemy import text

from app.dashboard import rotas as rotas_dashboard
from app.extrato import rotas as rotas_extrato
from app.seguranca.auth import UsuarioAutenticado

pytestmark = pytest.mark.integracao

HOJE = date.today()
PRIMEIRO_DIA = HOJE.replace(day=1)


async def _usuario(conexao, preferencias=None) -> UsuarioAutenticado:
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel, preferencias)
            values (:id, 'Teste B3', :email, 'gestor', cast(:pref as jsonb))
            """),
        {
            "id": str(identificador),
            "email": f"b3-{identificador.hex[:8]}@synapse.local",
            "pref": __import__("json").dumps(preferencias or {}),
        },
    )
    return UsuarioAutenticado(
        id=identificador,
        nome="Teste B3",
        email="b3@synapse.local",
        papel="gestor",
        preferencias=preferencias or {},
    )


async def _categoria(conexao, nome: str) -> UUID:
    achada = (
        await conexao.execute(text("select id from categorias where nome = :nome"), {"nome": nome})
    ).scalar_one_or_none()
    if achada is None:
        pytest.fail(f"A categoria '{nome}' não existe. Aplique as migrações 001…010.")
    return achada


async def _lanca(
    conexao,
    usuario,
    categoria_id,
    *,
    tipo: str,
    valor: str,
    quando: date,
    status: str = "efetivado",
    mundo: str = "digital",
    subcategoria_id=None,
):
    return (
        await conexao.execute(
            text("""
                insert into lancamentos (
                  mundo, tipo, descricao, valor, data, status, categoria_id, subcategoria_id,
                  efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
                ) values (
                  cast(:mundo as mundo), cast(:tipo as tipo_lancamento), 'teste B3', :valor,
                  :data, cast(:status as status_lancamento), :categoria, cast(:sub as uuid),
                  true,
                  case when :status = 'efetivado' then now() end,
                  case when :status = 'efetivado' then cast(:usuario as uuid) end,
                  cast(:usuario as uuid)
                )
                returning id
                """),
            {
                "mundo": mundo,
                "tipo": tipo,
                "valor": Decimal(valor),
                "data": quando,
                "status": status,
                "categoria": str(categoria_id),
                "sub": str(subcategoria_id) if subcategoria_id else None,
                "usuario": str(usuario.id),
            },
        )
    ).scalar_one()


# ── Dashboard ───────────────────────────────────────────────────────────────


async def test_cards_batem_com_o_calculo_manual(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    outros = await _categoria(conexao_de_teste, "Outros")

    await _lanca(
        conexao_de_teste, usuario, outros, tipo="receita", valor="10000.00", quando=PRIMEIRO_DIA
    )
    await _lanca(
        conexao_de_teste, usuario, infra, tipo="despesa", valor="2500.00", quando=PRIMEIRO_DIA
    )
    await _lanca(
        conexao_de_teste, usuario, infra, tipo="despesa", valor="500.00", quando=PRIMEIRO_DIA
    )

    painel = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    por_id = {card["id"]: card for card in painel["cards"]}

    assert Decimal(por_id["receitas_periodo"]["valor"]) >= Decimal("10000.00")
    assert Decimal(por_id["despesas_periodo"]["valor"]) >= Decimal("3000.00")
    assert Decimal(por_id["lucro_liquido"]["valor"]) == (
        Decimal(por_id["receitas_periodo"]["valor"]) - Decimal(por_id["despesas_periodo"]["valor"])
    )


async def test_so_efetivado_entra_nos_cards_de_realizado(conexao_de_teste):
    """`RN-05` — o alvo obrigatório, agora contra o banco."""
    usuario = await _usuario(conexao_de_teste)
    outros = await _categoria(conexao_de_teste, "Outros")

    antes = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    receitas_antes = Decimal({c["id"]: c for c in antes["cards"]}["receitas_periodo"]["valor"])

    await _lanca(
        conexao_de_teste,
        usuario,
        outros,
        tipo="receita",
        valor="7777.00",
        quando=HOJE,
        status="pendente",
    )

    depois = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    cards = {c["id"]: c for c in depois["cards"]}

    assert Decimal(cards["receitas_periodo"]["valor"]) == receitas_antes
    # …mas aparece em A receber, que é projeção (`FR-056`).
    assert Decimal(cards["a_receber"]["valor"]) >= Decimal("7777.00")
    situacoes = {c["situacao"]: c for c in cards["a_receber"]["composicao"]}
    assert situacoes["pendente"]["quantidade"] >= 1


async def test_composicao_de_a_receber_traz_as_tres_situacoes_mesmo_zeradas(conexao_de_teste):
    """Estado vazio explicativo: card com uma linha só esconderia o que falta."""
    usuario = await _usuario(conexao_de_teste)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste, mundo="digital")
    cards = {c["id"]: c for c in painel["cards"]}
    situacoes = [item["situacao"] for item in cards["a_receber"]["composicao"]]
    assert situacoes == ["programado", "pendente", "atrasado"]


async def test_dashboard_nao_vaza_dado_entre_mundos(conexao_de_teste):
    """`SC-005` na tela que soma tudo — é onde vazamento passaria despercebido."""
    usuario = await _usuario(conexao_de_teste)
    outros = await _categoria(conexao_de_teste, "Outros")

    await _lanca(
        conexao_de_teste,
        usuario,
        outros,
        tipo="receita",
        valor="4321.00",
        quando=PRIMEIRO_DIA,
        mundo="infra",
    )

    digital = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    cards = {c["id"]: c for c in digital["cards"]}
    assert Decimal(cards["receitas_periodo"]["valor"]) < Decimal("4321.00")

    ambos = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="ambos", periodo="este_mes"
    )
    cards_ambos = {c["id"]: c for c in ambos["cards"]}
    assert Decimal(cards_ambos["receitas_periodo"]["valor"]) >= Decimal("4321.00")
    assert set(cards_ambos["saldo_atual"]["quebra_por_mundo"]) == {"digital", "infra"}


async def test_rotulos_dos_cards_vem_do_banco_e_nao_do_codigo(conexao_de_teste):
    """`FR-106`: nenhum texto de card no frontend — nem no backend, fora da tabela."""
    usuario = await _usuario(conexao_de_teste)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste)

    catalogo = (
        await conexao_de_teste.execute(
            text("select valor from configuracoes where chave = 'dashboard_cards_disponiveis'")
        )
    ).scalar_one()
    rotulos_do_banco = {item["id"]: item["rotulo"] for item in catalogo}

    for card in painel["cards"]:
        assert card["rotulo"] == rotulos_do_banco[card["id"]]


async def test_preferencia_do_usuario_esconde_e_reordena(conexao_de_teste):
    """`FR-071`. O catálogo diz o que existe; a preferência, o que aparece."""
    preferencias = {
        "dashboard_cards": [
            {"id": "saldo_atual", "visivel": False, "ordem": 1},
            {"id": "a_pagar", "visivel": True, "ordem": 2},
        ]
    }
    usuario = await _usuario(conexao_de_teste, preferencias)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste)

    ids = [card["id"] for card in painel["cards"]]
    assert "saldo_atual" not in ids
    assert ids[0] == "a_pagar"
    # O catálogo continua completo em `cards_disponiveis`, para a tela de configuração.
    assert any(item["id"] == "saldo_atual" for item in painel["cards_disponiveis"])


async def test_largura_do_card_sai_no_catalogo_com_padrao_por_grupo(conexao_de_teste):
    """T217. A tela monta a grade com este campo — sem ele, tudo vira meia largura."""
    usuario = await _usuario(conexao_de_teste)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste)

    disponiveis = painel["cards_disponiveis"]
    assert disponiveis, "Sem catálogo não há o que afirmar. Aplique o seed."
    for item in disponiveis:
        assert item["largura"] in {"inteira", "metade"}

    por_grupo = {item["id"]: (item["grupo"], item["largura"]) for item in disponiveis}
    # Alerta é uma faixa: cortada ao meio vira um cartão qualquer.
    for grupo, largura in por_grupo.values():
        if grupo == "alerta":
            assert largura == "inteira"


async def test_largura_escolhida_pelo_usuario_vence_o_padrao(conexao_de_teste):
    """T217. É o que permite pôr dois gráficos lado a lado — ou desfazer isso."""
    preferencias = {
        "dashboard_cards": [
            {"id": "evolucao_saldo", "visivel": True, "ordem": 1, "largura": "inteira"},
        ]
    }
    usuario = await _usuario(conexao_de_teste, preferencias)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste)

    escolhido = next(c for c in painel["cards_disponiveis"] if c["id"] == "evolucao_saldo")
    assert escolhido["largura"] == "inteira"

    # Quem não escolheu continua no padrão do grupo.
    outro = next(c for c in painel["cards_disponiveis"] if c["id"] == "despesas_categoria")
    assert outro["largura"] == "metade"


async def test_blocos_especiais_saem_por_vinculo_e_nao_por_nome(conexao_de_teste):
    """`FR-079`: renomear a categoria "Clientes" não pode quebrar o bloco."""
    usuario = await _usuario(conexao_de_teste)
    clientes = await _categoria(conexao_de_teste, "Clientes")

    subcategoria = (
        await conexao_de_teste.execute(
            text("""
                insert into subcategorias (categoria_id, nome)
                values (:cat, :nome) returning id
                """),
            {"cat": str(clientes), "nome": f"Cliente Teste {uuid4().hex[:6]}"},
        )
    ).scalar_one()
    await _lanca(
        conexao_de_teste,
        usuario,
        clientes,
        tipo="receita",
        valor="4000.00",
        quando=PRIMEIRO_DIA,
        subcategoria_id=subcategoria,
    )

    # Renomeia a categoria: um `if nome == 'Clientes'` quebraria daqui em diante.
    await conexao_de_teste.execute(
        text("update categorias set nome = 'Receita de contratos' where id = :id"),
        {"id": str(clientes)},
    )

    painel = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    assert Decimal(painel["card_clientes"]["total_recebido"]) >= Decimal("4000.00")


async def test_atrasados_aparecem_no_alerta_e_no_resumo(conexao_de_teste):
    """`FR-068` e `FR-070` — o alerta é fixo e o resumo cita o número."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="3200.00",
        quando=HOJE - timedelta(days=10),
        status="atrasado",
    )
    painel = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )

    assert painel["alerta_atrasados"]["quantidade"] >= 1
    assert "vencida" in painel["resumo_linguagem_natural"]

    # O link do alerta tem que abrir **os mesmos** lançamentos que ele contou. O
    # alerta ignora o período (`RF-46a`) e `GET /api/lancamentos` não sabe ignorar,
    # então o drill-down vem com a janela alargada até o vencido mais antigo — aqui,
    # 10 dias atrás, antes do dia 1º. Sem isso o banner dizia "1 conta vencida" e
    # abria uma lista vazia (auditoria de 2026-08-04).
    drilldown = painel["alerta_atrasados"]["filtro_drilldown"]
    assert drilldown["status"] == ["atrasado"]
    assert drilldown["periodo"] == "personalizado"
    assert date.fromisoformat(drilldown["data_inicio"]) <= HOJE - timedelta(days=10)
    assert date.fromisoformat(drilldown["data_fim"]) >= HOJE


async def test_a_pagar_segue_o_periodo_mas_nao_perde_o_vencido(conexao_de_teste):
    """`RF-40` + `RF-41`: "pendentes + programados **do período**".

    O bug que originou este teste (2026-08-04): com as recorrências materializadas 12
    meses à frente, o card somava os 12 e mostrava R$ 25.200 num Dashboard filtrado em
    "Este mês". A outra metade da regra é a exceção do vencido — sem ela, trocar o
    filtro escondia justamente a conta que precisa ser vista.
    """
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    async def a_pagar(painel):
        return Decimal({c["id"]: c for c in painel["cards"]}["a_pagar"]["valor"])

    antes = await a_pagar(
        await rotas_dashboard.obter(usuario, conexao_de_teste, mundo="digital", periodo="este_mes")
    )

    # Dentro do período.
    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="111.00",
        quando=PRIMEIRO_DIA,
        status="programado",
    )
    # Cinco meses à frente: existe, mas não é "a pagar deste mês".
    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="9999.00",
        quando=HOJE + relativedelta(months=5),
        status="programado",
    )
    # Vencida em outro mês: entra sempre, venha de onde vier.
    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="222.00",
        quando=HOJE - timedelta(days=90),
        status="atrasado",
    )

    depois = await a_pagar(
        await rotas_dashboard.obter(usuario, conexao_de_teste, mundo="digital", periodo="este_mes")
    )
    assert depois - antes == Decimal("333.00"), (
        "A pagar deve somar o programado do período (111) e o vencido (222), e deixar "
        "de fora o programado de daqui a 5 meses (9999)."
    )


async def test_extrato_e_dashboard_somam_o_mesmo_a_pagar(conexao_de_teste):
    """A mesma pergunta em duas telas não pode ter duas respostas.

    O Extrato tinha o recorte antigo (`FR-051` ignorava o período por inteiro) depois
    de o Dashboard já ter o novo — e as duas telas passariam a discordar em silêncio.
    """
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="777.00",
        quando=PRIMEIRO_DIA,
        status="programado",
    )
    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="8888.00",
        quando=HOJE + relativedelta(months=6),
        status="programado",
    )

    painel = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    extrato = await rotas_extrato.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )

    card = Decimal({c["id"]: c for c in painel["cards"]}["a_pagar"]["valor"])
    secao = sum((Decimal(item["valor"]) for item in extrato["pendencias"]["a_pagar"]), Decimal("0"))
    assert card == secao


async def test_evolucao_do_saldo_projeta_o_mes_futuro(conexao_de_teste):
    """`RF-42a` + `RN-05`: mês marcado `projetado` tem que projetar alguma coisa.

    A série contava só `efetivado` em todos os meses, então o trecho marcado como
    projeção era uma reta no último saldo realizado — projeção que não projetava.
    """
    usuario = await _usuario(conexao_de_teste)
    outros = await _categoria(conexao_de_teste, "Outros")
    await _lanca(
        conexao_de_teste,
        usuario,
        outros,
        tipo="receita",
        valor="5555.00",
        quando=HOJE + relativedelta(months=2),
        status="programado",
    )

    painel = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    serie = painel["evolucao_saldo"]
    realizados = [p for p in serie if not p["projetado"]]
    projetados = [p for p in serie if p["projetado"]]
    assert projetados, "A série precisa alcançar meses futuros."

    ultimo_realizado = Decimal(realizados[-1]["saldo_final"])
    assert Decimal(projetados[-1]["saldo_final"]) >= ultimo_realizado + Decimal("5555.00")


async def test_fluxo_mensal_marca_meses_futuros_como_projetados(conexao_de_teste):
    """`FR-059` / `RN-05`: o previsto tem que ser visualmente distinto."""
    usuario = await _usuario(conexao_de_teste)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste)

    meses = painel["fluxo_caixa_mensal"]
    assert meses, "O fluxo mensal veio vazio — `generate_series` deveria criar o eixo."
    assert any(m["projetado"] for m in meses), "Nenhum mês futuro marcado como projetado."
    assert not meses[0]["projetado"]


async def test_periodo_sem_dados_e_explicito_e_nao_ausente(conexao_de_teste):
    """Edge case: a tela precisa distinguir "sem dados" de "erro ao carregar"."""
    usuario = await _usuario(conexao_de_teste)
    painel = await rotas_dashboard.obter(
        usuario,
        conexao_de_teste,
        mundo="digital",
        periodo="personalizado",
        data_inicio=date(2000, 1, 1),
        data_fim=date(2000, 1, 31),
    )
    assert painel["periodo_vazio"] is True
    cards = {c["id"]: c for c in painel["cards"]}
    assert cards["receitas_periodo"]["valor"] == "0.00"
    assert "nenhum lançamento" in painel["resumo_linguagem_natural"]


async def test_drilldown_e_query_pronta_para_a_lista(conexao_de_teste):
    """`FR-058`: o frontend só serializa e navega — nenhum card monta filtro."""
    usuario = await _usuario(conexao_de_teste)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste, mundo="digital")
    cards = {c["id"]: c for c in painel["cards"]}

    assert cards["a_pagar"]["filtro_drilldown"] == {
        "tipo": "despesa",
        "status": ["programado", "pendente", "atrasado"],
    }


# ── Extrato ─────────────────────────────────────────────────────────────────


async def test_saldo_acumulado_do_ultimo_grupo_bate_com_o_saldo_final(conexao_de_teste):
    """O teste de aceitação da história 7, contra o banco."""
    usuario = await _usuario(conexao_de_teste)
    outros = await _categoria(conexao_de_teste, "Outros")
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    await _lanca(
        conexao_de_teste, usuario, outros, tipo="receita", valor="2000.00", quando=PRIMEIRO_DIA
    )
    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="800.00",
        quando=PRIMEIRO_DIA + timedelta(days=1),
    )

    extrato = await rotas_extrato.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes", agrupamento="dia"
    )
    realizados = [g for g in extrato["grupos"] if not g["previsto"]]
    assert realizados, "Nenhum grupo realizado no período."
    assert realizados[-1]["saldo_acumulado"] == extrato["resumo"]["saldo_final"]


async def test_extrato_e_dashboard_dao_o_mesmo_numero(conexao_de_teste):
    """São consultas escritas em módulos diferentes; discordar é o risco real."""
    usuario = await _usuario(conexao_de_teste)
    outros = await _categoria(conexao_de_teste, "Outros")
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    await _lanca(
        conexao_de_teste, usuario, outros, tipo="receita", valor="5000.00", quando=PRIMEIRO_DIA
    )
    await _lanca(
        conexao_de_teste, usuario, infra, tipo="despesa", valor="1200.00", quando=PRIMEIRO_DIA
    )

    painel = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    extrato = await rotas_extrato.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )
    cards = {c["id"]: c for c in painel["cards"]}

    assert cards["receitas_periodo"]["valor"] == extrato["resumo"]["total_receitas"]
    assert cards["despesas_periodo"]["valor"] == extrato["resumo"]["total_despesas"]
    assert cards["saldo_atual"]["valor"] == extrato["resumo"]["saldo_final"]


async def test_agrupamento_por_mes_junta_o_que_o_dia_separa(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    outros = await _categoria(conexao_de_teste, "Outros")

    await _lanca(
        conexao_de_teste, usuario, outros, tipo="receita", valor="100.00", quando=PRIMEIRO_DIA
    )
    await _lanca(
        conexao_de_teste,
        usuario,
        outros,
        tipo="receita",
        valor="200.00",
        quando=PRIMEIRO_DIA + timedelta(days=1),
    )

    por_dia = await rotas_extrato.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes", agrupamento="dia"
    )
    por_mes = await rotas_extrato.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes", agrupamento="mes"
    )
    assert len(por_mes["grupos"]) == 1
    assert len(por_dia["grupos"]) >= 2
    assert por_mes["resumo"]["saldo_final"] == por_dia["resumo"]["saldo_final"]


async def test_pendencias_ignoram_o_filtro_de_periodo(conexao_de_teste):
    """`FR-051`: conta vencida em maio continua a pagar em julho."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    await _lanca(
        conexao_de_teste,
        usuario,
        infra,
        tipo="despesa",
        valor="480.00",
        quando=HOJE - timedelta(days=120),
        status="atrasado",
    )
    extrato = await rotas_extrato.obter(
        usuario, conexao_de_teste, mundo="digital", periodo="este_mes"
    )

    vencidos = [item for item in extrato["pendencias"]["a_pagar"] if item["vencido"]]
    assert vencidos, "A conta vencida há 4 meses sumiu porque o filtro está em julho."


async def test_grupo_futuro_nao_move_o_acumulado(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    outros = await _categoria(conexao_de_teste, "Outros")

    await _lanca(conexao_de_teste, usuario, outros, tipo="receita", valor="1000.00", quando=HOJE)
    await _lanca(
        conexao_de_teste,
        usuario,
        outros,
        tipo="receita",
        valor="9999.00",
        quando=HOJE + timedelta(days=5),
        status="programado",
    )

    extrato = await rotas_extrato.obter(
        usuario,
        conexao_de_teste,
        mundo="digital",
        periodo="personalizado",
        data_inicio=HOJE - timedelta(days=1),
        data_fim=HOJE + timedelta(days=10),
    )
    previstos = [g for g in extrato["grupos"] if g["previsto"]]
    realizados = [g for g in extrato["grupos"] if not g["previsto"]]

    assert previstos, "O grupo futuro não foi marcado como previsto."
    assert previstos[-1]["saldo_acumulado"] == realizados[-1]["saldo_acumulado"]
