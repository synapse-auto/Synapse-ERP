"""Dia 31 em fevereiro — caso de borda nomeado em quickstart.md §6.

"Todo dia 31" precisa cair no **último dia** do mês quando 31 não existe, e voltar para
31 no mês seguinte. O erro clássico é encadear a partir da ocorrência anterior: depois
de cair em 28/02, março viraria 28, abril 28, e a série inteira escorregaria para
sempre. O combinado era o dia 31.

Tarefa: T073
"""

from datetime import date

import pytest

from app.dominio import recorrencia as mod_recorrencia


def _todo_dia(dia: int, inicio: date) -> mod_recorrencia.Regra:
    return mod_recorrencia.Regra(frequencia="mensal", data_inicio=inicio, dia_vencimento=dia)


def test_dia_31_cai_no_ultimo_dia_de_fevereiro():
    regra = _todo_dia(31, date(2026, 1, 31))
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 4, 30)))

    assert datas[0] == date(2026, 1, 31)
    assert datas[1] == date(2026, 2, 28)  # 2026 não é bissexto
    assert datas[2] == date(2026, 3, 31)
    assert datas[3] == date(2026, 4, 30)


def test_em_ano_bissexto_cai_no_dia_29():
    regra = _todo_dia(31, date(2028, 1, 31))
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2028, 3, 31)))
    assert datas[1] == date(2028, 2, 29)


def test_marco_volta_para_31_e_a_serie_nao_escorrega():
    """O teste que pega o encadeamento errado.

    Se a próxima data fosse calculada a partir da anterior (28/02 + 1 mês = 28/03), a
    série toda passaria a ser dia 28 depois do primeiro fevereiro. Aqui isso apareceria
    como `date(2026, 3, 28)`.
    """
    regra = _todo_dia(31, date(2025, 12, 31))
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 12, 31)))

    dias = [quando.day for quando in datas]
    # Meses de 31 dias voltam a 31; só fevereiro, abril, junho, setembro e novembro
    # ficam abaixo — que é o número de dias que esses meses têm.
    assert dias == [31, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def test_dia_30_tambem_encolhe_so_em_fevereiro():
    regra = _todo_dia(30, date(2026, 1, 30))
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 4, 30)))
    assert [d.day for d in datas] == [30, 28, 30, 30]


def test_dia_28_nunca_encolhe():
    regra = _todo_dia(28, date(2026, 1, 28))
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 6, 30)))
    assert all(quando.day == 28 for quando in datas)


def test_inicio_no_dia_3_com_vencimento_no_dia_10_comeca_no_mesmo_mes():
    """Não empurra a série um mês para frente sem ninguém pedir."""
    regra = _todo_dia(10, date(2026, 3, 3))
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 5, 31)))
    assert datas[0] == date(2026, 3, 10)


# ── As outras frequências, para o clamp não virar um caso isolado ───────────


def test_semanal_usa_o_dia_da_semana_1_a_7():
    """1 = segunda … 7 = domingo (ISO), a mesma convenção do resto do sistema."""
    # 30/07/2026 é uma quinta-feira (isoweekday 4).
    regra = mod_recorrencia.Regra(
        frequencia="semanal", data_inicio=date(2026, 7, 30), dia_vencimento=1
    )
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 8, 31)))
    assert datas[0] == date(2026, 8, 3)  # a segunda seguinte
    assert all(quando.isoweekday() == 1 for quando in datas)


def test_a_cada_n_dias():
    regra = mod_recorrencia.Regra(
        frequencia="dias", data_inicio=date(2026, 7, 1), intervalo_dias=10
    )
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 8, 1)))
    assert datas == [date(2026, 7, 1), date(2026, 7, 11), date(2026, 7, 21), date(2026, 7, 31)]


def test_anual_no_dia_29_de_fevereiro_cai_no_28_nos_anos_comuns():
    regra = mod_recorrencia.Regra(
        frequencia="anual",
        data_inicio=date(2028, 2, 29),
        dia_vencimento=29,
        mes_vencimento=2,
    )
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2031, 12, 31)))
    assert datas[0] == date(2028, 2, 29)
    assert datas[1] == date(2029, 2, 28)


# ── Validação da regra ──────────────────────────────────────────────────────


def test_data_fim_e_total_parcelas_juntos_sao_recusados():
    from app.comum.erros import ErroValidacao

    regra = mod_recorrencia.Regra(
        frequencia="mensal",
        data_inicio=date(2026, 1, 10),
        dia_vencimento=10,
        data_fim=date(2026, 12, 31),
        total_parcelas=6,
    )
    with pytest.raises(ErroValidacao) as capturado:
        list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2027, 1, 1)))
    assert "data_fim" in (capturado.value.campos or {})


def test_frequencia_dias_sem_intervalo_e_recusada():
    from app.comum.erros import ErroValidacao

    regra = mod_recorrencia.Regra(frequencia="dias", data_inicio=date(2026, 1, 10))
    with pytest.raises(ErroValidacao):
        list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2026, 3, 1)))
