"""`RN-05` / `RN-16` — só `efetivado` conta no realizado. Alvo obrigatório (Princípio VI).

`programado` e `pendente` entram em **projeção** e nos cards "A pagar / A receber",
nunca no saldo. `cancelado` e excluído não entram em nada.

E **não existe saldo inicial** (`FR-114`, research.md D-06): o caixa é exclusivamente o
resultado dos lançamentos efetivados. Enquanto o histórico não estiver carregado, o
número fica menor que a realidade — isso é conhecido e aceito, não um defeito.

Tarefa: T041
"""

from decimal import Decimal

from app.dominio import saldo


def linha(valor, tipo="receita", status="efetivado", mundo="digital", **extra):
    base = {
        "valor": Decimal(valor),
        "tipo": tipo,
        "status": status,
        "mundo": mundo,
        "excluido": False,
        "tem_partes": False,
    }
    base.update(extra)
    return base


# ── O que conta e o que não conta ────────────────────────────────────────────


def test_so_efetivado_conta_no_realizado():
    assert saldo.conta_no_realizado(status="efetivado", excluido=False, tem_partes=False) is True
    for nao_conta in ("programado", "pendente", "atrasado", "cancelado"):
        assert (
            saldo.conta_no_realizado(status=nao_conta, excluido=False, tem_partes=False) is False
        ), nao_conta


def test_excluido_nao_conta_mesmo_efetivado():
    assert saldo.conta_no_realizado(status="efetivado", excluido=True, tem_partes=False) is False


def test_pai_de_split_nao_conta_mesmo_efetivado():
    """RN-11: só as partes contam, senão o valor entra duas vezes."""
    assert saldo.conta_no_realizado(status="efetivado", excluido=False, tem_partes=True) is False


# ── Saldo ────────────────────────────────────────────────────────────────────


def test_saldo_e_receita_efetivada_menos_despesa_efetivada():
    linhas = [
        linha("2000.00", "receita"),
        linha("1200.00", "despesa"),
        linha("300.00", "despesa"),
    ]
    assert saldo.calcula(linhas) == Decimal("500.00")


def test_programado_nao_muda_o_saldo():
    """O caso que a regra existe para evitar: contar dinheiro que ainda não entrou."""
    so_efetivado = [linha("2000.00", "receita")]
    com_futuro = [
        linha("2000.00", "receita"),
        linha("50000.00", "receita", status="programado"),
        linha("9000.00", "despesa", status="pendente"),
        linha("1000.00", "despesa", status="atrasado"),
    ]
    assert saldo.calcula(so_efetivado) == saldo.calcula(com_futuro) == Decimal("2000.00")


def test_cancelado_preserva_historico_mas_sai_dos_totais():
    linhas = [linha("2000.00", "receita"), linha("500.00", "receita", status="cancelado")]
    assert saldo.calcula(linhas) == Decimal("2000.00")


def test_sem_lancamento_o_saldo_e_zero_nao_um_valor_inicial():
    """FR-114: não existe saldo de abertura a informar."""
    assert saldo.calcula([]) == Decimal("0.00")


def test_saldo_pode_ficar_negativo():
    assert saldo.calcula([linha("100.00", "despesa")]) == Decimal("-100.00")


def test_centavos_nao_se_perdem():
    linhas = [linha("0.10", "receita"), linha("0.20", "receita")]
    assert saldo.calcula(linhas) == Decimal("0.30")


# ── RN-16: saldo por mundo, e a quebra no modo "Ambos" ───────────────────────


def test_saldo_e_calculado_separadamente_por_mundo():
    linhas = [
        linha("2000.00", "receita", mundo="digital"),
        linha("500.00", "despesa", mundo="digital"),
        linha("800.00", "receita", mundo="infra"),
    ]
    assert saldo.calcula(linhas, mundo="digital") == Decimal("1500.00")
    assert saldo.calcula(linhas, mundo="infra") == Decimal("800.00")


def test_ambos_e_a_soma_com_a_quebra():
    linhas = [
        linha("2000.00", "receita", mundo="digital"),
        linha("500.00", "despesa", mundo="digital"),
        linha("800.00", "receita", mundo="infra"),
    ]
    consolidado = saldo.consolidado(linhas)
    assert consolidado["total"] == Decimal("2300.00")
    assert consolidado["por_mundo"] == {
        "digital": Decimal("1500.00"),
        "infra": Decimal("800.00"),
    }


def test_mundo_sem_movimento_aparece_com_zero_na_quebra():
    """Edge case da spec: o mundo vazio no modo "Ambos" mostra zero, não some."""
    consolidado = saldo.consolidado([linha("100.00", "receita", mundo="digital")])
    assert consolidado["por_mundo"]["infra"] == Decimal("0.00")


# ── Projeção: o que NÃO entra no saldo entra aqui ────────────────────────────


def test_a_receber_soma_receitas_nao_efetivadas():
    linhas = [
        linha("2000.00", "receita", status="efetivado"),
        linha("500.00", "receita", status="programado"),
        linha("300.00", "receita", status="pendente"),
        linha("200.00", "receita", status="atrasado"),
        linha("900.00", "receita", status="cancelado"),
        linha("700.00", "despesa", status="programado"),
    ]
    a_receber = saldo.a_receber(linhas)
    assert a_receber["total"] == Decimal("1000.00")
    assert a_receber["por_situacao"] == {
        "programado": Decimal("500.00"),
        "pendente": Decimal("300.00"),
        "atrasado": Decimal("200.00"),
    }


def test_a_pagar_soma_despesas_nao_efetivadas():
    linhas = [
        linha("1200.00", "despesa", status="programado"),
        linha("800.00", "despesa", status="atrasado"),
        linha("5000.00", "despesa", status="efetivado"),
    ]
    assert saldo.a_pagar(linhas)["total"] == Decimal("2000.00")


def test_projecao_e_saldo_mais_o_que_esta_previsto():
    linhas = [
        linha("2000.00", "receita", status="efetivado"),
        linha("1000.00", "receita", status="programado"),
        linha("400.00", "despesa", status="programado"),
    ]
    assert saldo.calcula(linhas) == Decimal("2000.00")
    assert saldo.projetado(linhas) == Decimal("2600.00")
