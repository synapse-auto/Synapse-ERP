"""`RN-10` / `FR-115` — inadimplência derivada.

Dois comportamentos que precisam continuar valendo, e que são fáceis de quebrar sem
perceber:

1. **Mudar a tolerância reavalia na hora.** É a razão de a situação não ser coluna.
2. **Lançamento automático nunca conta como atraso** (D-05). É a razão de a mensalidade
   de cliente nascer com efetivação manual.

Tarefa: T100
"""

from datetime import date, timedelta
from decimal import Decimal

from app.dominio import inadimplencia as mod

HOJE = date(2026, 7, 30)


def _lancamento(dias_atras: int, valor: str = "2000.00", *, status="pendente", automatico=False):
    return {
        "data": HOJE - timedelta(days=dias_atras),
        "valor": Decimal(valor),
        "status": status,
        "efetivar_automaticamente": automatico,
    }


def test_sem_lancamento_em_aberto_o_cliente_esta_em_dia():
    resultado = mod.avalia([], hoje=HOJE)
    assert resultado.situacao == "em_dia"
    assert resultado.como_dicionario()["dias_atraso"] is None


def test_dentro_da_tolerancia_ainda_e_em_dia():
    resultado = mod.avalia([_lancamento(3)], tolerancia_dias=3, hoje=HOJE)
    assert resultado.situacao == "em_dia"


def test_um_dia_alem_da_tolerancia_ja_e_atraso():
    resultado = mod.avalia([_lancamento(4)], tolerancia_dias=3, hoje=HOJE)
    assert resultado.situacao == "atrasado"
    assert resultado.dias_atraso == 4
    assert resultado.valor_atrasado == Decimal("2000.00")


def test_mudar_a_tolerancia_muda_a_situacao_do_mesmo_cliente():
    """O motivo de a situação ser derivada e não gravada (`FR-105`).

    Se alguém transformar isto numa coluna, este teste continua passando — mas o
    sistema deixa de reavaliar ao mudar a configuração. Por isso o teste existe **e**
    o módulo diz, no cabeçalho, por que não há coluna.
    """
    aberto = [_lancamento(5)]
    assert mod.avalia(aberto, tolerancia_dias=3, hoje=HOJE).situacao == "atrasado"
    assert mod.avalia(aberto, tolerancia_dias=10, hoje=HOJE).situacao == "em_dia"


def test_lancamento_automatico_nunca_conta_como_atraso():
    """D-05 — e é a pergunta que alguém vai fazer olhando um devedor fora da lista."""
    automatico = [_lancamento(90, automatico=True)]
    assert mod.avalia(automatico, tolerancia_dias=3, hoje=HOJE).situacao == "em_dia"

    manual = [_lancamento(90, automatico=False)]
    assert mod.avalia(manual, tolerancia_dias=3, hoje=HOJE).situacao == "atrasado"

    assert mod.pode_ficar_inadimplente(efetivar_automaticamente=True) is False
    assert mod.pode_ficar_inadimplente(efetivar_automaticamente=False) is True


def test_programado_nao_conta_porque_ainda_nao_venceu():
    resultado = mod.avalia([_lancamento(30, status="programado")], hoje=HOJE)
    assert resultado.situacao == "em_dia"


def test_valor_atrasado_soma_todos_os_vencidos():
    resultado = mod.avalia(
        [_lancamento(10, "2000.00"), _lancamento(40, "1500.00"), _lancamento(1, "999.00")],
        tolerancia_dias=3,
        hoje=HOJE,
    )
    assert resultado.valor_atrasado == Decimal("3500.00")
    assert resultado.quantidade == 2


def test_dias_de_atraso_e_o_do_mais_antigo():
    """A média suavizaria justamente o caso que importa."""
    resultado = mod.avalia([_lancamento(10), _lancamento(60)], tolerancia_dias=3, hoje=HOJE)
    assert resultado.dias_atraso == 60


def test_dicionario_traz_a_tolerancia_usada():
    """A tela precisa poder explicar o critério, não só mostrar o rótulo."""
    saida = mod.avalia([_lancamento(10)], tolerancia_dias=7, hoje=HOJE).como_dicionario()
    assert saida["tolerancia_dias"] == 7
    assert saida["valor_atrasado"] == "2000.00"
    assert saida["quantidade_em_atraso"] == 1
