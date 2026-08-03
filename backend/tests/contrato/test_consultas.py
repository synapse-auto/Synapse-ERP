"""Contrato do Dashboard e do Extrato — contracts/consultas.md §1 e §2.

Roda sem banco: confere o OpenAPI e as funções puras de montagem (agrupamento, saldo
acumulado, rótulos). O comportamento com dados reais está nos testes `integracao`.

Tarefa: T098 (parte de contrato)
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.extrato import servico

pytestmark = pytest.mark.contrato

ENDPOINTS_ACORDADOS = [("get", "/api/dashboard"), ("get", "/api/extrato")]


@pytest.fixture
def openapi(cliente) -> dict:
    return cliente.get("/api/openapi.json").json()


@pytest.mark.parametrize(("metodo", "caminho"), ENDPOINTS_ACORDADOS)
def test_endpoint_do_contrato_existe_e_declara_papel(openapi, metodo, caminho):
    assert caminho in openapi["paths"]
    operacao = openapi["paths"][caminho][metodo]
    assert "Papel:" in (operacao.get("description") or "")


def test_dashboard_aceita_mundo_e_periodo(openapi):
    nomes = {p["name"] for p in openapi["paths"]["/api/dashboard"]["get"]["parameters"]}
    assert {"mundo", "periodo", "data_inicio", "data_fim"} <= nomes


def test_extrato_aceita_agrupamento(openapi):
    nomes = {p["name"] for p in openapi["paths"]["/api/extrato"]["get"]["parameters"]}
    assert "agrupamento" in nomes


# ── Agrupamento e saldo acumulado (`FR-047`, `FR-052`) ──────────────────────


def _linha(dia: date, tipo: str, valor: str, status: str = "efetivado", grupo=None):
    grupo = grupo or dia
    return {
        "grupo_inicio": grupo,
        "grupo_fim": grupo,
        "id": uuid4(),
        "mundo": "digital",
        "tipo": tipo,
        "descricao": "linha",
        "valor": Decimal(valor),
        "data": dia,
        "status": status,
        "categoria_nome": "Infraestrutura",
        "categoria_cor": "#4FA8E0",
        "subcategoria_nome": None,
    }


HOJE = date(2026, 7, 30)


def test_saldo_acumulado_parte_do_saldo_anterior_ao_periodo():
    """Começar do zero daria um número que não bate com o saldo real (`FR-114`)."""
    grupos = servico.monta_grupos(
        [_linha(date(2026, 7, 10), "receita", "2000.00")],
        agrupamento="dia",
        saldo_base=Decimal("12300.00"),
        hoje=HOJE,
    )
    assert grupos[0]["saldo_acumulado"] == "14300.00"


def test_acumulado_corre_grupo_a_grupo():
    grupos = servico.monta_grupos(
        [
            _linha(date(2026, 7, 10), "receita", "2000.00"),
            _linha(date(2026, 7, 11), "despesa", "500.00"),
            _linha(date(2026, 7, 12), "receita", "100.00"),
        ],
        agrupamento="dia",
        saldo_base=Decimal("0.00"),
        hoje=HOJE,
    )
    assert [g["saldo_acumulado"] for g in grupos] == ["2000.00", "1500.00", "1600.00"]


def test_so_efetivado_move_o_acumulado():
    """`RN-05`: programado e pendente aparecem no grupo, mas não somam no saldo."""
    grupos = servico.monta_grupos(
        [
            _linha(date(2026, 7, 10), "receita", "2000.00", status="efetivado"),
            _linha(date(2026, 7, 10), "receita", "9999.00", status="pendente"),
        ],
        agrupamento="dia",
        saldo_base=Decimal("0.00"),
        hoje=HOJE,
    )
    assert grupos[0]["saldo_acumulado"] == "2000.00"
    # …mas o total do grupo mostra os dois, porque o extrato lista o que vai acontecer.
    assert grupos[0]["totais"]["receitas"] == "11999.00"
    assert len(grupos[0]["lancamentos"]) == 2


def test_grupo_futuro_e_marcado_previsto_e_nao_entra_no_acumulado():
    """`FR-052`: somar o previsto faria a linha do saldo mostrar dinheiro inexistente."""
    grupos = servico.monta_grupos(
        [
            _linha(date(2026, 7, 10), "receita", "2000.00"),
            _linha(date(2026, 8, 10), "receita", "5000.00", status="programado"),
        ],
        agrupamento="dia",
        saldo_base=Decimal("0.00"),
        hoje=HOJE,
    )
    assert grupos[0]["previsto"] is False
    assert grupos[1]["previsto"] is True
    assert grupos[1]["saldo_acumulado"] == "2000.00"  # repete o último realizado


def test_ultimo_grupo_realizado_bate_com_o_saldo_final():
    """A garantia que o contrato cobra e o teste de aceitação da história 7."""
    saldo_base = Decimal("12300.00")
    linhas = [
        _linha(date(2026, 7, 10), "receita", "2000.00"),
        _linha(date(2026, 7, 20), "despesa", "800.00"),
    ]
    grupos = servico.monta_grupos(linhas, agrupamento="dia", saldo_base=saldo_base, hoje=HOJE)
    resultado = Decimal("2000.00") - Decimal("800.00")
    assert grupos[-1]["saldo_acumulado"] == f"{saldo_base + resultado:.2f}"


def test_rotulo_muda_com_o_agrupamento():
    assert servico.rotulo_do_grupo(date(2026, 7, 10), date(2026, 7, 10), "dia") == "10/07/2026"
    assert (
        servico.rotulo_do_grupo(date(2026, 7, 6), date(2026, 7, 12), "semana")
        == "06/07 a 12/07/2026"
    )
    assert servico.rotulo_do_grupo(date(2026, 7, 1), date(2026, 7, 31), "mes") == "jul/2026"


def test_agrupamento_invalido_e_recusado_em_pt_br():
    from app.comum.erros import ErroValidacao

    with pytest.raises(ErroValidacao) as capturado:
        servico.valida_agrupamento("trimestre")
    assert "agrupamento" in (capturado.value.campos or {})


def test_grafico_espelha_os_grupos():
    """`FR-050`: o gráfico e a lista mostram o mesmo recorte, sempre.

    "Mesmo recorte" é mesma quantidade de pontos, na mesma ordem, com os mesmos
    números — **não** o mesmo texto de rótulo. A versão anterior deste teste afirmava
    `grafico[0]["rotulo"] == grupos[0]["rotulo"]`, e esse atalho é que mantinha em pé o
    bug que derrubava o Extrato: contracts/consultas.md §2 pede data ISO no gráfico
    (`"2026-07-10"`) e texto pronto no cabeçalho do grupo (`"10/07/2026"`), porque a tela
    passa o rótulo do gráfico por um formatador de data. Com o texto pronto ali, o
    formatador recebia `"10/07/2026"` e levantava `RangeError: Invalid time value`.
    """
    grupos = servico.monta_grupos(
        [_linha(date(2026, 7, 10), "receita", "2000.00")],
        agrupamento="dia",
        saldo_base=Decimal("0.00"),
        hoje=HOJE,
    )
    grafico = servico.monta_grafico(grupos)
    assert len(grafico) == len(grupos)
    # O ponto aponta para o mesmo grupo — pelo `inicio`, que é a chave de verdade.
    assert grafico[0]["rotulo"] == grupos[0]["inicio"]
    assert grafico[0]["receitas"] == grupos[0]["totais"]["receitas"]
    assert grafico[0]["despesas"] == grupos[0]["totais"]["despesas"]


def test_rotulo_do_grafico_e_data_iso_e_o_do_grupo_e_brasileiro():
    """Os dois rótulos são diferentes de propósito (contracts/consultas.md §2)."""
    grupos = servico.monta_grupos(
        [_linha(date(2026, 7, 10), "receita", "2000.00")],
        agrupamento="dia",
        saldo_base=Decimal("0.00"),
        hoje=HOJE,
    )
    assert grupos[0]["rotulo"] == "10/07/2026"
    assert servico.monta_grafico(grupos)[0]["rotulo"] == "2026-07-10"
    # Levanta se deixar de ser ISO — é o que a tela precisa poder formatar.
    date.fromisoformat(servico.monta_grafico(grupos)[0]["rotulo"])


def test_extrato_vazio_devolve_lista_vazia_e_nao_erro():
    """Estado vazio explicativo (edge case da spec)."""
    assert servico.monta_grupos([], agrupamento="dia", saldo_base=Decimal("0"), hoje=HOJE) == []
