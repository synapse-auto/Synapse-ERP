"""`RN-05a` / `SC-004` — recorrência retroativa. **Alvo obrigatório da constituição.**

O caso que a spec descreve: a pessoa cadastra em julho uma mensalidade que começou em
março. O sistema tem que gerar as ocorrências passadas **já efetivadas**, para que o
saldo bata com o histórico real sem ninguém clicar em cada linha — e para que o cliente
não apareça como inadimplente de meses que ele pagou.

Tarefa: T072
"""

from datetime import date

from app.dominio import recorrencia as mod_recorrencia

HOJE = date(2026, 7, 30)


def _mensal(inicio: date, dia: int | None = None) -> mod_recorrencia.Regra:
    return mod_recorrencia.Regra(
        frequencia="mensal", data_inicio=inicio, dia_vencimento=dia or inicio.day
    )


def test_inicio_12_meses_atras_gera_exatamente_12_efetivadas():
    """`SC-004`: 12 meses para trás → 12 ocorrências passadas, todas efetivadas."""
    regra = _mensal(date(2025, 8, 10), dia=10)
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=HOJE))

    retroativas = [quando for quando in datas if mod_recorrencia.nasce_efetivada(quando, hoje=HOJE)]
    assert len(retroativas) == 12
    assert retroativas[0] == date(2025, 8, 10)
    assert retroativas[-1] == date(2026, 7, 10)


def test_retroativa_nasce_efetivada_mesmo_com_efetivacao_manual():
    """O ponto de `RN-05a`: o passado já aconteceu, o checkbox não muda isso.

    O checkbox decide o que acontece quando uma data **futura** chega (`RN-04`). Se
    esta regra cair, uma mensalidade recuperada de março apareceria como pendente e o
    cliente entraria na lista de inadimplentes por dinheiro que ele já pagou.
    """
    assert mod_recorrencia.nasce_efetivada(date(2026, 3, 10), hoje=HOJE) is True
    assert mod_recorrencia.nasce_efetivada(HOJE, hoje=HOJE) is True
    assert mod_recorrencia.nasce_efetivada(date(2026, 8, 10), hoje=HOJE) is False


def test_serie_retroativa_continua_no_futuro_ate_o_horizonte():
    """As passadas viram efetivadas; as futuras continuam programadas."""
    regra = _mensal(date(2026, 3, 10), dia=10)
    ate = mod_recorrencia.horizonte(HOJE, meses=12)
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=ate))

    passadas = [d for d in datas if d <= HOJE]
    futuras = [d for d in datas if d > HOJE]

    assert passadas == [date(2026, m, 10) for m in (3, 4, 5, 6, 7)]
    assert futuras[0] == date(2026, 8, 10)
    assert futuras[-1] <= ate


def test_previa_conta_sem_gerar():
    """`FR-027`: o `422` mostra quantas e o intervalo, antes de gravar qualquer coisa."""
    regra = _mensal(date(2025, 3, 1), dia=1)
    previa = mod_recorrencia.monta_previa(
        regra, ate=mod_recorrencia.horizonte(HOJE, meses=12), hoje=HOJE
    )

    assert previa.primeira == date(2025, 3, 1)
    assert previa.retroativas_efetivadas == 17  # de 03/2025 a 07/2026
    assert previa.total_ocorrencias > previa.retroativas_efetivadas
    assert previa.como_dicionario()["primeira"] == "2025-03-01"


def test_geracao_incremental_nao_repete_o_que_ja_existe():
    """`gerada_ate` é o que torna a rotina diária idempotente (D-08).

    Sem o `desde`, cada execução da rotina recriaria a série inteira desde o início —
    e o saldo dobraria a cada dia.
    """
    regra = _mensal(date(2026, 1, 10), dia=10)
    ate = date(2026, 9, 10)

    tudo = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=ate))
    faltando = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=ate, desde=date(2026, 7, 11)))

    assert tudo[0] == date(2026, 1, 10)
    assert faltando == [date(2026, 8, 10), date(2026, 9, 10)]


def test_total_de_parcelas_conta_desde_o_comeco_mesmo_gerando_em_partes():
    """Contar só o pedaço geraria 12 parcelas **por execução** da rotina."""
    regra = mod_recorrencia.Regra(
        frequencia="mensal", data_inicio=date(2026, 1, 10), dia_vencimento=10, total_parcelas=6
    )
    tudo = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2027, 12, 31)))
    assert len(tudo) == 6
    assert tudo[-1] == date(2026, 6, 10)

    incremental = list(
        mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2027, 12, 31), desde=date(2026, 4, 1))
    )
    assert incremental == [date(2026, 4, 10), date(2026, 5, 10), date(2026, 6, 10)]


def test_data_fim_encerra_a_serie():
    regra = mod_recorrencia.Regra(
        frequencia="mensal",
        data_inicio=date(2026, 1, 10),
        dia_vencimento=10,
        data_fim=date(2026, 4, 30),
    )
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=date(2027, 1, 1)))
    assert datas == [date(2026, m, 10) for m in (1, 2, 3, 4)]


def test_horizonte_impede_serie_sem_fim_de_gerar_infinito():
    regra = _mensal(date(2026, 1, 10), dia=10)  # sem data_fim, sem total_parcelas
    ate = mod_recorrencia.horizonte(HOJE, meses=12)
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=ate))
    assert datas[-1] <= ate
    assert len(datas) < 40
