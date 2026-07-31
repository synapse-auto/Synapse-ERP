"""`RN-06` — arquivar sem deixar lançamento órfão.

O que está protegido: arquivar categoria com movimento **exige uma escolha**, e a escolha
"manter somente-leitura" existe porque a alternativa (obrigar a mover tudo) reescreveria o
histórico — o DRE de 2025 mudaria sozinho.

Tarefa: T101
"""

from decimal import Decimal

import pytest

from app.comum.erros import ErroConfirmacaoNecessaria, ErroRegraViolada
from app.dominio import arquivamento as mod


def test_categoria_sem_lancamento_arquiva_direto():
    destino = mod.exige_destino(
        nome="Marketing",
        quantidade_lancamentos=0,
        valor_total=Decimal("0.00"),
        destino_lancamentos=None,
        manter_somente_leitura=False,
    )
    assert destino.move is False


def test_com_lancamentos_e_sem_escolha_pede_confirmacao_com_a_contagem():
    with pytest.raises(ErroConfirmacaoNecessaria) as capturado:
        mod.exige_destino(
            nome="Marketing",
            quantidade_lancamentos=42,
            valor_total=Decimal("14000.00"),
            destino_lancamentos=None,
            manter_somente_leitura=False,
        )
    erro = capturado.value
    assert erro.status == 422
    assert erro.requisito == "RN-06"
    assert erro.extra["previa"]["quantidade_lancamentos"] == 42
    assert erro.extra["previa"]["valor_total"] == "14000.00"
    # A prévia explica as duas saídas, em vez de só recusar.
    assert "opcoes" in erro.extra["previa"]


def test_as_duas_escolhas_juntas_sao_recusadas():
    with pytest.raises(ErroRegraViolada):
        mod.exige_destino(
            nome="Marketing",
            quantidade_lancamentos=42,
            valor_total=Decimal("14000.00"),
            destino_lancamentos="outra-categoria",
            manter_somente_leitura=True,
        )


def test_mover_resolve():
    destino = mod.exige_destino(
        nome="Marketing",
        quantidade_lancamentos=42,
        valor_total=Decimal("14000.00"),
        destino_lancamentos="outra",
        manter_somente_leitura=False,
    )
    assert destino.move is True
    assert destino.mover_para == "outra"


def test_somente_leitura_resolve_sem_mover_nada():
    """Preserva o fechamento dos meses passados."""
    destino = mod.exige_destino(
        nome="Marketing",
        quantidade_lancamentos=42,
        valor_total=Decimal("14000.00"),
        destino_lancamentos=None,
        manter_somente_leitura=True,
    )
    assert destino.move is False
    assert destino.manter_somente_leitura is True


def test_mover_para_si_mesma_e_recusado():
    with pytest.raises(ErroRegraViolada):
        mod.recusa_mover_para_si_mesma(origem="abc", destino="abc")

    mod.recusa_mover_para_si_mesma(origem="abc", destino="def")  # não levanta
    mod.recusa_mover_para_si_mesma(origem="abc", destino=None)


def test_categoria_especial_nao_se_arquiva_e_a_mensagem_diz_o_caminho():
    with pytest.raises(ErroRegraViolada) as capturado:
        mod.recusa_arquivar_especial(nome="Clientes", especial=True, vinculo="cliente")
    assert "Arquive os clientes" in capturado.value.mensagem

    # Categoria comum passa.
    mod.recusa_arquivar_especial(nome="Marketing", especial=False, vinculo=None)


def test_cliente_e_funcionario_nao_sao_excluidos():
    """Constituição, "Padrões Técnicos Obrigatórios"."""
    for recurso in ("cliente", "funcionario"):
        with pytest.raises(ErroRegraViolada) as capturado:
            mod.exige_arquivamento_em_vez_de_exclusao(recurso)
        assert capturado.value.requisito == "RN-06"


def test_resumo_conta_o_que_saiu_da_projecao():
    """Sem esse número o usuário arquiva um cliente e não sabe que a projeção mudou."""
    assert mod.resumo_do_arquivamento(ocorrencias_removidas=6, lancamentos_movidos=42) == {
        "ocorrencias_futuras_removidas": 6,
        "lancamentos_movidos": 42,
    }
