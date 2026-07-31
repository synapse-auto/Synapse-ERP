"""`RN-07` — escopo de edição de série. `esta_e_futuras` nunca alcança o passado.

O caso concreto: a mensalidade sobe de R$ 1.800 para R$ 2.000 em agosto. Editar com
`esta_e_futuras` tem que mudar agosto em diante e **deixar março a julho como estão** —
senão o faturamento dos meses fechados muda sozinho, e o número que alguém já conferiu
deixa de bater sem nenhum registro do porquê.

Tarefa: T074
"""

from datetime import date

import pytest

from app.comum.erros import ErroConfirmacaoNecessaria
from app.dominio import recorrencia as mod_recorrencia
from app.dominio import status as mod_status

HOJE = date(2026, 7, 30)

SERIE = [
    date(2026, 3, 10),
    date(2026, 4, 10),
    date(2026, 5, 10),
    date(2026, 6, 10),
    date(2026, 7, 10),  # passada, mas do mês corrente
    date(2026, 8, 10),
    date(2026, 9, 10),
]


def test_esta_e_futuras_nao_toca_em_nenhuma_ocorrencia_passada():
    alcancadas = mod_recorrencia.datas_que_o_escopo_alcanca(
        SERIE, escopo="esta_e_futuras", hoje=HOJE
    )
    assert alcancadas == [date(2026, 8, 10), date(2026, 9, 10)]
    assert all(quando >= HOJE for quando in alcancadas)


def test_ocorrencia_do_mes_corrente_ja_vencida_conta_como_passado():
    """10/07 é anterior a 30/07: já foi paga, não é "futura" só por ser deste mês."""
    alcancadas = mod_recorrencia.datas_que_o_escopo_alcanca(
        SERIE, escopo="esta_e_futuras", hoje=HOJE
    )
    assert date(2026, 7, 10) not in alcancadas


def test_ocorrencia_de_hoje_e_alcancada():
    """A fronteira é `>= hoje`: o que vence hoje ainda não passou."""
    serie = [HOJE, date(2026, 8, 30)]
    alcancadas = mod_recorrencia.datas_que_o_escopo_alcanca(
        serie, escopo="esta_e_futuras", hoje=HOJE
    )
    assert alcancadas == serie


def test_apenas_esta_nao_filtra_nada():
    """O escopo "só esta" é uma edição de ocorrência, não de série.

    A ocorrência escolhida pode ser passada — e aí quem protege é a confirmação de
    alteração histórica (data-model §5.8), não este filtro.
    """
    alcancadas = mod_recorrencia.datas_que_o_escopo_alcanca(SERIE, escopo="apenas_esta", hoje=HOJE)
    assert alcancadas == SERIE


def test_editar_ocorrencia_passada_efetivada_ainda_pede_confirmacao():
    """As duas proteções são complementares, não alternativas.

    `RN-07` impede o escopo de série de alcançar o passado. A confirmação histórica
    cobre o outro caminho: mexer numa ocorrência passada **de propósito**, uma por vez.
    """
    with pytest.raises(ErroConfirmacaoNecessaria):
        mod_status.exige_confirmacao_de_alteracao_historica(
            status_atual="efetivado",
            data_do_lancamento=date(2026, 5, 10),
            confirmado=False,
            hoje=HOJE,
        )


def test_serie_inteira_no_futuro_e_toda_alcancada():
    futura = [date(2026, 9, 10), date(2026, 10, 10)]
    assert (
        mod_recorrencia.datas_que_o_escopo_alcanca(futura, escopo="esta_e_futuras", hoje=HOJE)
        == futura
    )


def test_serie_inteira_no_passado_nao_alcanca_nada():
    """Editar "este e os futuros" numa série encerrada não muda coisa alguma.

    Vazio é a resposta certa: a alternativa seria alterar o passado em silêncio.
    """
    passada = [date(2025, 1, 10), date(2025, 2, 10)]
    assert (
        mod_recorrencia.datas_que_o_escopo_alcanca(passada, escopo="esta_e_futuras", hoje=HOJE)
        == []
    )
