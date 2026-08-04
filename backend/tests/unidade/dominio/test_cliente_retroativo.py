"""Cliente retroativo ("cliente desde") — `dominio/cliente_retroativo.py`.

O que este arquivo protege é a **borda**: qual mês o cadastro aceita, qual recusa e qual
não é retroativo nenhum. A geração das ocorrências em si já é coberta por
`test_recorrencia_retroativa.py` — de propósito, porque cliente retroativo reaproveita a
recorrência inteira em vez de ter um gerador próprio.

O caso do dia 31 em fevereiro não se testa de novo aqui pelo mesmo motivo:
`test_recorrencia_dia_31_em_fevereiro.py` já o cobre, e ele é a **mesma** regra.

Tarefa: cliente retroativo (2026-08-04)
"""

from datetime import date

import pytest

from app.comum.erros import ErroValidacao
from app.dominio import cliente_retroativo as mod
from app.dominio import recorrencia as mod_recorrencia

HOJE = date(2026, 8, 4)
MAXIMO = 120


def _resolve(mes: str | None, *, tipo="recorrente", maximo=MAXIMO):
    return mod.resolve_inicio(mes, tipo_cobranca=tipo, meses_maximo=maximo, hoje=HOJE)


def test_mes_passado_vira_o_primeiro_dia_daquele_mes():
    assert _resolve("2025-03") == date(2025, 3, 1)


def test_mes_atual_nao_e_retroativo():
    """A regra que impede o mês corrente de duplicar.

    Devolver `None` faz o cadastro cair no `date.today()` de sempre. Não é economia: é
    a garantia de que ligar o checkbox e escolher o mês em que se está dá exatamente o
    mesmo resultado de não ligar nada.
    """
    assert _resolve("2026-08") is None


def test_mes_atual_gera_a_mesma_serie_que_o_comportamento_de_hoje():
    """Prova a afirmação acima onde ela importa: nas datas geradas.

    Se algum dia `_primeira_data` deixar de reposicionar no `dia_vencimento`, este teste
    cai antes de o mês corrente aparecer duplicado no saldo de alguém.
    """
    ate = date(2026, 12, 31)
    de_hoje = mod_recorrencia.Regra(frequencia="mensal", data_inicio=HOJE, dia_vencimento=10)
    do_mes = mod_recorrencia.Regra(
        frequencia="mensal", data_inicio=date(2026, 8, 1), dia_vencimento=10
    )
    assert list(mod_recorrencia.datas_das_ocorrencias(de_hoje, ate=ate)) == list(
        mod_recorrencia.datas_das_ocorrencias(do_mes, ate=ate)
    )


def test_sem_mes_informado_nao_e_retroativo():
    assert _resolve(None) is None


def test_mes_no_futuro_e_recusado():
    with pytest.raises(ErroValidacao) as erro:
        _resolve("2026-09")
    assert "cliente_desde" in erro.value.campos


def test_mes_alem_do_limite_configurado_e_recusado():
    """O limite vem de `configuracoes` (`RNF-02`) — aqui entra como parâmetro."""
    with pytest.raises(ErroValidacao):
        _resolve("2020-01", maximo=12)

    # No limite exato ainda passa.
    assert _resolve("2025-08", maximo=12) == date(2025, 8, 1)


def test_retroativo_so_existe_para_cobranca_recorrente():
    for tipo in ("pontual", "parcelada"):
        with pytest.raises(ErroValidacao) as erro:
            _resolve("2025-03", tipo=tipo)
        assert "recorrente" in erro.value.campos["cliente_desde"]


@pytest.mark.parametrize("ruim", ["2025-3", "03/2025", "2025-13", "2025-00", "abc", "2025"])
def test_formato_invalido_e_recusado_na_borda(ruim: str):
    """Erro de entrada é recusado com campo e mensagem em PT-BR, não vira `500`."""
    with pytest.raises(ErroValidacao):
        _resolve(ruim)


def test_meses_entre_conta_calendario_e_nao_dias():
    assert mod.meses_entre(date(2025, 3, 1), HOJE) == 17
    # Qualquer dia do mês corrente é distância zero — é mês de calendário, não 30 dias.
    assert mod.meses_entre(date(2026, 8, 31), HOJE) == 0
    # Início depois do fim é negativo: é assim que `resolve_inicio` detecta o futuro.
    assert mod.meses_entre(date(2026, 9, 1), HOJE) == -1


def test_dezoito_meses_atras_geram_dezoito_efetivadas():
    """O cenário que o dono do projeto pediu para conferir, em datas.

    18 meses atrás de 08/2026 é 02/2025. Com cobrança no dia 10 e hoje sendo dia 4, a
    ocorrência de 08/2026 ainda **não** venceu: são 18 efetivadas, de 02/2025 a 07/2026,
    e a de agosto nasce `programado`.
    """
    inicio = _resolve("2025-02")
    assert inicio == date(2025, 2, 1)

    regra = mod_recorrencia.Regra(frequencia="mensal", data_inicio=inicio, dia_vencimento=10)
    ate = mod_recorrencia.horizonte(HOJE, meses=12)
    datas = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=ate))
    efetivadas = [d for d in datas if mod_recorrencia.nasce_efetivada(d, hoje=HOJE)]

    assert len(efetivadas) == 18
    assert efetivadas[0] == date(2025, 2, 10)
    assert efetivadas[-1] == date(2026, 7, 10)


def test_resumo_traz_texto_pronto_para_a_tela():
    """`RNF-02`: a contagem em português é montada no servidor, não em TypeScript."""
    um = mod.resumo(desde=date(2025, 3, 1), ocorrencias=1, valor_unitario="2000.00")
    varios = mod.resumo(desde=date(2025, 3, 1), ocorrencias=18, valor_unitario="36000.00")

    assert um["desde"] == "2025-03-01"
    assert "1 cobrança do histórico foi lançada como efetivada" in um["mensagem"]
    assert "18 cobranças do histórico foram lançadas como efetivadas" in varios["mensagem"]
    assert varios["valor_total"] == "36000.00"
