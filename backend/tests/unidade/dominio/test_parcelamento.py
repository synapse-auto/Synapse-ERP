"""`FR-028` — parcelamento. A soma das parcelas tem que fechar no centavo.

R$ 1.000,00 em 3 não é 333,33 três vezes: isso perde um centavo e o cliente pagaria
999,99. A última parcela absorve a diferença.

Tarefa: T077
"""

from datetime import date
from decimal import Decimal

import pytest

from app.comum.erros import ErroValidacao
from app.dominio import parcelamento as mod_parcelamento

PRIMEIRA = date(2026, 8, 5)


def test_divisao_exata_reparte_igual():
    parcelas = mod_parcelamento.divide(
        valor_total=Decimal("12000.00"), total_parcelas=3, data_primeira=PRIMEIRA
    )
    assert [p.valor for p in parcelas] == [Decimal("4000.00")] * 3


def test_ultima_parcela_absorve_a_sobra():
    parcelas = mod_parcelamento.divide(
        valor_total=Decimal("1000.00"), total_parcelas=3, data_primeira=PRIMEIRA
    )
    assert [p.valor for p in parcelas] == [
        Decimal("333.33"),
        Decimal("333.33"),
        Decimal("333.34"),
    ]
    assert sum(p.valor for p in parcelas) == Decimal("1000.00")


@pytest.mark.parametrize(
    ("total", "parcelas"),
    [
        ("100.00", 3),
        ("0.05", 3),
        ("9999.99", 7),
        ("1234.56", 11),
        ("50000.00", 360),
    ],
)
def test_a_soma_sempre_bate_com_o_total(total, parcelas):
    resultado = mod_parcelamento.divide(
        valor_total=Decimal(total), total_parcelas=parcelas, data_primeira=PRIMEIRA
    )
    assert sum(p.valor for p in resultado) == Decimal(total)


def test_a_primeira_parcela_e_a_anunciada_e_nao_a_ajustada():
    """A diferença vai para a última porque a primeira é a que vai na proposta."""
    parcelas = mod_parcelamento.divide(
        valor_total=Decimal("100.00"), total_parcelas=3, data_primeira=PRIMEIRA
    )
    assert parcelas[0].valor == Decimal("33.33")
    assert parcelas[-1].valor == Decimal("33.34")


def test_datas_mensais_nao_escorregam_por_causa_de_fevereiro():
    parcelas = mod_parcelamento.divide(
        valor_total=Decimal("300.00"),
        total_parcelas=4,
        data_primeira=date(2026, 1, 31),
    )
    assert [p.data for p in parcelas] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
    ]


def test_rotulo_mostra_a_posicao():
    parcelas = mod_parcelamento.divide(
        valor_total=Decimal("300.00"), total_parcelas=3, data_primeira=PRIMEIRA
    )
    assert parcelas[1].rotulo == "2/3"
    assert (
        mod_parcelamento.descricao_da_parcela("Projeto site institucional", parcelas[1])
        == "Projeto site institucional (2/3)"
    )


def test_uma_parcela_nao_e_parcelamento():
    with pytest.raises(ErroValidacao) as capturado:
        mod_parcelamento.divide(
            valor_total=Decimal("100.00"), total_parcelas=1, data_primeira=PRIMEIRA
        )
    assert "total_parcelas" in (capturado.value.campos or {})


def test_parcelas_abaixo_de_um_centavo_sao_recusadas_com_explicacao():
    """Recusar dizendo o que fazer, em vez de gravar parcelas de R$ 0,00."""
    with pytest.raises(ErroValidacao) as capturado:
        mod_parcelamento.divide(
            valor_total=Decimal("0.02"), total_parcelas=5, data_primeira=PRIMEIRA
        )
    assert "centavo" in capturado.value.mensagem


def test_intervalos_semanal_e_quinzenal():
    semanal = mod_parcelamento.divide(
        valor_total=Decimal("300.00"),
        total_parcelas=3,
        data_primeira=PRIMEIRA,
        intervalo="semanal",
    )
    assert [p.data for p in semanal] == [date(2026, 8, 5), date(2026, 8, 12), date(2026, 8, 19)]

    quinzenal = mod_parcelamento.divide(
        valor_total=Decimal("300.00"),
        total_parcelas=3,
        data_primeira=PRIMEIRA,
        intervalo="quinzenal",
    )
    assert [p.data for p in quinzenal] == [date(2026, 8, 5), date(2026, 8, 20), date(2026, 9, 4)]
