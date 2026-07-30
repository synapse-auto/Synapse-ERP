"""`RN-11` — integridade do split. Alvo obrigatório da constituição (Princípio VI).

O que a regra protege: um lançamento dividido em partes tem que ter
`Σ(partes) = valor(pai)`. Salvar em estado inconsistente é recusado, com a diferença
explicitada — e **o pai deixa de contar nos totais** quando tem partes, senão o valor
entra em dobro no saldo.

Comparação em `Decimal`, nunca float: `0.1 + 0.2 != 0.3` em ponto flutuante, e um
sistema financeiro que recusa um split correto por causa disso é pior que inútil.

Tarefa: T039
"""

from decimal import Decimal

import pytest

from app.comum.erros import ErroRegraViolada
from app.dominio import split


def test_partes_que_fecham_sao_aceitas():
    split.valida_soma(Decimal("500.00"), [Decimal("300.00"), Decimal("200.00")])


def test_partes_que_nao_fecham_sao_recusadas_com_a_diferenca():
    """O exemplo do contrato: 480 de partes contra 500 do pai, faltam 20."""
    with pytest.raises(ErroRegraViolada) as capturado:
        split.valida_soma(Decimal("500.00"), [Decimal("300.00"), Decimal("180.00")])

    erro = capturado.value
    assert erro.status == 409
    assert erro.codigo == "regra_violada"
    assert erro.requisito == "RN-11"
    assert "R$ 480,00" in erro.mensagem
    assert "R$ 500,00" in erro.mensagem
    assert "R$ 20,00" in erro.campos["partes"]


def test_partes_que_passam_do_valor_dizem_quanto_sobra():
    with pytest.raises(ErroRegraViolada) as capturado:
        split.valida_soma(Decimal("500.00"), [Decimal("300.00"), Decimal("250.00")])
    assert "R$ 50,00" in capturado.value.campos["partes"]


def test_centavos_fecham_exatamente_sem_erro_de_ponto_flutuante():
    """0.1 + 0.2 != 0.3 em float. Em Decimal fecha, e é isso que o banco guarda."""
    split.valida_soma(Decimal("0.30"), [Decimal("0.10"), Decimal("0.20")])


def test_diferenca_de_um_centavo_e_recusada():
    """Arredondamento silencioso é o que faz o fechamento não bater no fim do mês."""
    with pytest.raises(ErroRegraViolada) as capturado:
        split.valida_soma(Decimal("100.00"), [Decimal("33.33"), Decimal("33.33"), Decimal("33.33")])
    assert "R$ 0,01" in capturado.value.campos["partes"]


def test_escala_diferente_nao_e_diferenca():
    """`200.0` e `200.00` são o mesmo dinheiro."""
    split.valida_soma(Decimal("500.0"), [Decimal("300.000"), Decimal("200.00")])


def test_split_exige_ao_menos_duas_partes():
    """Dividir em uma parte só não é dividir — é renomear."""
    with pytest.raises(ErroRegraViolada) as capturado:
        split.valida_soma(Decimal("500.00"), [Decimal("500.00")])
    assert capturado.value.requisito == "RN-11"


def test_parte_com_valor_zero_ou_negativo_e_recusada():
    """`RN-02`: valor é sempre positivo; o sinal vem do tipo."""
    with pytest.raises(ErroRegraViolada):
        split.valida_soma(Decimal("500.00"), [Decimal("500.00"), Decimal("0.00")])
    with pytest.raises(ErroRegraViolada):
        split.valida_soma(Decimal("500.00"), [Decimal("600.00"), Decimal("-100.00")])


# ── O pai sai dos totais quando tem partes ───────────────────────────────────


def test_pai_com_partes_nao_conta_nos_totais():
    """Sem isto o valor entra em dobro: uma vez no pai, outra nas partes."""
    assert split.conta_nos_totais(tem_partes=True) is False
    assert split.conta_nos_totais(tem_partes=False) is True


def test_parte_de_split_nao_pode_ter_partes():
    """Um nível só (data-model §3.10). Regra entre linhas, não alcançável por CHECK."""
    with pytest.raises(ErroRegraViolada) as capturado:
        split.valida_pode_dividir(e_parte_de_split=True, tem_partes=False)
    assert capturado.value.requisito == "RN-11"


def test_lancamento_ja_dividido_nao_divide_de_novo():
    with pytest.raises(ErroRegraViolada):
        split.valida_pode_dividir(e_parte_de_split=False, tem_partes=True)


def test_lancamento_simples_pode_dividir():
    split.valida_pode_dividir(e_parte_de_split=False, tem_partes=False)
