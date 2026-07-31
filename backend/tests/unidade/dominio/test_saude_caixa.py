"""`RF-46b` / `FR-069` — semáforo de saúde do caixa.

O que precisa continuar valendo: os multiplicadores e o horizonte vêm de
`configuracoes`, não do código (`RNF-02`, Princípio VII). Se alguém fixar 1,5 aqui
dentro, estes testes continuam passando — por isso há um teste que **muda** os
multiplicadores e exige que a classificação mude junto.

Tarefa: T088
"""

from decimal import Decimal

from app.dominio import saude_caixa as mod_saude


def _avalia(saldo: str, fixas: str, **extra):
    return mod_saude.avalia(saldo=Decimal(saldo), despesas_fixas_horizonte=Decimal(fixas), **extra)


def test_cobertura_acima_da_folga_e_verde():
    resultado = _avalia("18450.00", "10080.00")
    assert resultado.semaforo == "verde"
    assert resultado.cobertura == Decimal("1.83")


def test_cobertura_entre_o_minimo_e_a_folga_e_amarelo():
    resultado = _avalia("12000.00", "10000.00")  # 1,2×
    assert resultado.semaforo == "amarelo"
    assert "sem folga" in resultado.explicacao


def test_cobertura_abaixo_do_minimo_e_vermelho():
    resultado = _avalia("5000.00", "10000.00")  # 0,5×
    assert resultado.semaforo == "vermelho"
    assert "Falta caixa" in resultado.explicacao


def test_exatamente_na_folga_ainda_e_verde():
    """A fronteira é `>=`: 1,5× é o que a configuração chama de folga."""
    assert _avalia("15000.00", "10000.00").semaforo == "verde"


def test_exatamente_no_minimo_e_amarelo():
    assert _avalia("10000.00", "10000.00").semaforo == "amarelo"


def test_multiplicadores_vem_da_configuracao_e_mudam_a_classificacao():
    """O teste que pega o número fixado no código.

    A mesma cobertura de 1,2× é amarela com os multiplicadores padrão e **vermelha**
    com uma exigência maior. Se alguém escrever `1.5` dentro do módulo, este teste
    quebra — que é o ponto.
    """
    padrao = _avalia("12000.00", "10000.00")
    exigente = _avalia("12000.00", "10000.00", multiplicadores={"minimo": 1.5, "folga": 2.0})

    assert padrao.semaforo == "amarelo"
    assert exigente.semaforo == "vermelho"


def test_horizonte_aparece_na_explicacao_e_vem_de_fora():
    resultado = _avalia("18450.00", "10080.00", horizonte_dias=45)
    assert "45 dias" in resultado.explicacao
    assert resultado.horizonte_dias == 45


def test_sem_despesa_fixa_a_cobertura_e_indefinida_e_nao_infinita():
    """Dividir por zero e mostrar "∞×" seria cômodo e enganoso.

    Não há cobertura sendo demonstrada — há ausência de contas cadastradas, e a
    explicação diz exatamente isso.
    """
    resultado = _avalia("18450.00", "0.00")
    assert resultado.semaforo == "verde"
    assert resultado.cobertura is None
    assert resultado.como_dicionario()["cobertura"] is None
    assert "Não há despesa fixa" in resultado.explicacao


def test_saldo_negativo_e_vermelho_sem_calcular_cobertura():
    resultado = _avalia("-500.00", "10000.00")
    assert resultado.semaforo == "vermelho"
    assert resultado.cobertura == Decimal("0.00")


def test_explicacao_usa_virgula_decimal_como_a_tela_espera():
    """`RNF-03`: a frase é texto de tela, então `1,8` e não `1.8`."""
    resultado = _avalia("18450.00", "10080.00")
    assert "1,8×" in resultado.explicacao


def test_dicionario_traz_dinheiro_como_string_com_duas_casas():
    saida = _avalia("18450.00", "10080.00").como_dicionario()
    assert saida["saldo"] == "18450.00"
    assert saida["despesas_fixas_horizonte"] == "10080.00"
    assert saida["cobertura"] == "1.83"
