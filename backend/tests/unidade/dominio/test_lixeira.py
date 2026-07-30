"""`RN-08` — soft delete e lixeira (T047).

A parte que costuma ser implementada errada: passado o prazo, a restauração é
recusada, mas **a linha não é apagada**. Não existe exclusão definitiva pela API.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.comum.erros import ErroRegraViolada
from app.dominio import lixeira

AGORA = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def excluido_ha(dias: int) -> datetime:
    return AGORA - timedelta(days=dias)


def test_dentro_do_prazo_pode_restaurar():
    assert lixeira.pode_restaurar(excluido_ha(10), retencao_dias=90, agora=AGORA) is True
    lixeira.exige_pode_restaurar(excluido_ha(10), retencao_dias=90, agora=AGORA)


def test_fora_do_prazo_e_recusado_dizendo_que_o_dado_continua_la():
    with pytest.raises(ErroRegraViolada) as capturado:
        lixeira.exige_pode_restaurar(excluido_ha(91), retencao_dias=90, agora=AGORA)

    erro = capturado.value
    assert erro.requisito == "RN-08"
    assert "não foi apagado" in erro.mensagem


def test_prazo_vem_de_configuracao_nao_do_codigo():
    """Princípio VII: `lixeira_retencao_dias` é dado."""
    assert lixeira.pode_restaurar(excluido_ha(30), retencao_dias=90, agora=AGORA) is True
    assert lixeira.pode_restaurar(excluido_ha(30), retencao_dias=7, agora=AGORA) is False


def test_dias_restantes_para_a_tela():
    assert lixeira.dias_restantes(excluido_ha(10), retencao_dias=90, agora=AGORA) == 80
    assert lixeira.dias_restantes(excluido_ha(89), retencao_dias=90, agora=AGORA) == 1


def test_dias_restantes_nunca_e_negativo():
    assert lixeira.dias_restantes(excluido_ha(200), retencao_dias=90, agora=AGORA) == 0


def test_lancamento_na_lixeira_nao_aceita_operacao():
    """Sem isto daria para efetivar um excluído, e ele voltaria aos totais sem ser
    restaurado."""
    lixeira.exige_nao_excluido(None)
    with pytest.raises(ErroRegraViolada) as capturado:
        lixeira.exige_nao_excluido(excluido_ha(1))
    assert capturado.value.requisito == "RN-08"
