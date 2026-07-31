"""`RN-03` / `RN-04` — ciclo de status. **Alvo obrigatório da constituição.**

O que está sendo protegido: `atrasado` só é alcançável com efetivação manual (D-05), e
`cancelado` preserva o histórico em vez de apagar. As duas coisas parecem detalhe e não
são — a primeira é o que faz o alerta de inadimplência existir (`RN-10`), a segunda é a
diferença entre cancelar e excluir.

Tarefa: T071
"""

from datetime import date, timedelta

import pytest

from app.comum.erros import ErroConfirmacaoNecessaria, ErroRegraViolada
from app.dominio import status as mod_status

HOJE = date(2026, 7, 30)
ONTEM = HOJE - timedelta(days=1)
AMANHA = HOJE + timedelta(days=1)


# ── Status inicial (`FR-024`) ───────────────────────────────────────────────


def test_data_futura_nasce_programado():
    assert mod_status.status_inicial(data_do_lancamento=AMANHA, hoje=HOJE) == "programado"


def test_hoje_e_passado_nascem_efetivados():
    assert mod_status.status_inicial(data_do_lancamento=HOJE, hoje=HOJE) == "efetivado"
    assert mod_status.status_inicial(data_do_lancamento=ONTEM, hoje=HOJE) == "efetivado"


# ── `RN-04` — o que a rotina faz na data ────────────────────────────────────


def test_programado_automatico_vira_efetivado_na_data():
    novo = mod_status.status_na_data(
        status_atual="programado",
        data_do_lancamento=HOJE,
        efetivar_automaticamente=True,
        hoje=HOJE,
    )
    assert novo == "efetivado"


def test_programado_manual_vira_pendente_na_data():
    novo = mod_status.status_na_data(
        status_atual="programado",
        data_do_lancamento=HOJE,
        efetivar_automaticamente=False,
        hoje=HOJE,
    )
    assert novo == "pendente"


def test_pendente_vencido_vira_atrasado():
    novo = mod_status.status_na_data(
        status_atual="pendente",
        data_do_lancamento=ONTEM,
        efetivar_automaticamente=False,
        hoje=HOJE,
    )
    assert novo == "atrasado"


def test_pendente_que_vence_hoje_ainda_nao_esta_atrasado():
    """Vencer hoje não é atrasar — o dia ainda não acabou."""
    novo = mod_status.status_na_data(
        status_atual="pendente",
        data_do_lancamento=HOJE,
        efetivar_automaticamente=False,
        hoje=HOJE,
    )
    assert novo is None


def test_lancamento_automatico_nunca_chega_a_atrasado():
    """D-05, e é o ponto da regra: o automático se efetiva na data e não vence.

    Consequência que precisa continuar valendo: o alerta de inadimplência (`RN-10`)
    depende de o lançamento **poder** ficar atrasado. Se este teste quebrar, a
    cobrança de cliente para de funcionar junto.
    """
    assert mod_status.pode_atrasar(efetivar_automaticamente=False) is True
    assert mod_status.pode_atrasar(efetivar_automaticamente=True) is False

    # O automático passa direto de programado a efetivado. Nunca existe um estado
    # intermediário de onde `atrasado` seria alcançável.
    caminho = mod_status.status_na_data(
        status_atual="programado",
        data_do_lancamento=ONTEM,
        efetivar_automaticamente=True,
        hoje=HOJE,
    )
    assert caminho == "efetivado"
    assert (
        mod_status.status_na_data(
            status_atual=caminho, data_do_lancamento=ONTEM, efetivar_automaticamente=True, hoje=HOJE
        )
        is None
    )


@pytest.mark.parametrize("estado_final", ["efetivado", "cancelado"])
def test_rotina_nao_mexe_em_estado_final(estado_final):
    assert (
        mod_status.status_na_data(
            status_atual=estado_final,
            data_do_lancamento=ONTEM,
            efetivar_automaticamente=False,
            hoje=HOJE,
        )
        is None
    )


def test_rodar_a_rotina_de_novo_no_mesmo_dia_nao_encontra_nada():
    """Idempotência (D-08): a segunda passada devolve `None` para tudo."""
    primeiro = mod_status.status_na_data(
        status_atual="programado",
        data_do_lancamento=HOJE,
        efetivar_automaticamente=False,
        hoje=HOJE,
    )
    segundo = mod_status.status_na_data(
        status_atual=primeiro,
        data_do_lancamento=HOJE,
        efetivar_automaticamente=False,
        hoje=HOJE,
    )
    assert primeiro == "pendente"
    assert segundo is None


# ── Transições manuais ──────────────────────────────────────────────────────


@pytest.mark.parametrize("de", ["programado", "pendente", "atrasado"])
def test_confirmar_efetivacao_vale_de_qualquer_estado_aberto(de):
    mod_status.exige_transicao_manual(de=de, para="efetivado")  # não levanta


def test_cancelado_e_estado_final():
    with pytest.raises(ErroRegraViolada) as capturado:
        mod_status.exige_transicao_manual(de="cancelado", para="efetivado")
    assert capturado.value.requisito == "RN-03"


def test_usuario_nao_declara_atrasado_nem_pendente():
    """São estados que o sistema descobre na data, não que alguém marca."""
    with pytest.raises(ErroRegraViolada) as capturado:
        mod_status.exige_transicao_manual(de="programado", para="atrasado")
    assert "sozinho" in capturado.value.mensagem


def test_cancelar_preserva_o_historico_e_nao_e_excluir():
    """`RN-03`: sai dos totais, a linha continua. Excluir é `RN-08`, outra coisa."""
    mod_status.exige_transicao_manual(de="efetivado", para="cancelado")
    assert "cancelado" not in mod_status.CONTA_NO_REALIZADO
    assert "cancelado" not in mod_status.CONTA_NA_PROJECAO


def test_so_efetivado_conta_no_realizado():
    """`RN-05`, dito na forma de conjunto para o resto do código consultar."""
    assert mod_status.CONTA_NO_REALIZADO == {"efetivado"}
    assert mod_status.CONTA_NA_PROJECAO == {"programado", "pendente", "atrasado"}


# ── Edição histórica (data-model §5.8) ──────────────────────────────────────


def test_editar_efetivado_do_passado_exige_confirmacao():
    with pytest.raises(ErroConfirmacaoNecessaria) as capturado:
        mod_status.exige_confirmacao_de_alteracao_historica(
            status_atual="efetivado", data_do_lancamento=ONTEM, confirmado=False, hoje=HOJE
        )
    assert capturado.value.status == 422
    assert capturado.value.extra["campo_confirmacao"] == "confirmar_alteracao_historica"


def test_com_confirmacao_passa_e_marca_como_historica():
    historica = mod_status.exige_confirmacao_de_alteracao_historica(
        status_atual="efetivado", data_do_lancamento=ONTEM, confirmado=True, hoje=HOJE
    )
    assert historica is True


def test_editar_lancamento_futuro_nao_pede_nada():
    historica = mod_status.exige_confirmacao_de_alteracao_historica(
        status_atual="programado", data_do_lancamento=AMANHA, confirmado=False, hoje=HOJE
    )
    assert historica is False
