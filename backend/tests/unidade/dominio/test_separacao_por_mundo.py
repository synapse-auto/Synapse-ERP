"""`RN-15` — mundo obrigatório e imutável. Alvo obrigatório (Princípio VI), `SC-005`.

Duas garantias distintas:

1. **Nenhum dado de um mundo aparece no outro.** É `SC-005`: alternar Digital / Infra /
   Ambos em todas as telas, zero dado do mundo errado.
2. **`mundo` não muda depois de criado.** O banco garante por gatilho
   (`recusa_alteracao_de_mundo`, SQLSTATE `RN015`); este módulo recusa antes de chegar
   lá, para a mensagem sair em PT-BR com o requisito citado.

As exceções documentadas — `categorias`, `subcategorias`, `tags` e `clientes` (D-04) —
também são testadas, porque tratá-las como se tivessem mundo esconderia cliente da
lista sem motivo.

Tarefa: T042
"""

import pytest

from app.comum.erros import ErroRegraViolada, ErroValidacao
from app.dominio import mundo as mod_mundo

# ── Filtro: o que "ambos" significa ──────────────────────────────────────────


def test_filtro_por_um_mundo_devolve_so_ele():
    assert mod_mundo.resolve_filtro("digital") == ["digital"]
    assert mod_mundo.resolve_filtro("infra") == ["infra"]


def test_ambos_devolve_os_dois():
    assert sorted(mod_mundo.resolve_filtro("ambos")) == ["digital", "infra"]


def test_ausente_significa_ambos():
    """contracts/README.md: ausente = ambos. Nunca inferido do último uso no servidor."""
    assert sorted(mod_mundo.resolve_filtro(None)) == ["digital", "infra"]


def test_mundo_inventado_e_recusado():
    with pytest.raises(ErroValidacao) as capturado:
        mod_mundo.resolve_filtro("lumina")
    assert "digital" in capturado.value.campos["mundo"]


def test_deve_mostrar_quebra_so_no_modo_ambos():
    """FR-003 / RF-102: consolidado vem com a quebra por mundo."""
    assert mod_mundo.deve_quebrar_por_mundo("ambos") is True
    assert mod_mundo.deve_quebrar_por_mundo(None) is True
    assert mod_mundo.deve_quebrar_por_mundo("digital") is False


# ── Separação: zero vazamento (SC-005) ───────────────────────────────────────


def test_nenhum_dado_de_um_mundo_aparece_no_outro():
    linhas = [
        {"id": 1, "mundo": "digital"},
        {"id": 2, "mundo": "infra"},
        {"id": 3, "mundo": "digital"},
        {"id": 4, "mundo": "infra"},
    ]
    assert [x["id"] for x in mod_mundo.filtra(linhas, "digital")] == [1, 3]
    assert [x["id"] for x in mod_mundo.filtra(linhas, "infra")] == [2, 4]
    assert [x["id"] for x in mod_mundo.filtra(linhas, "ambos")] == [1, 2, 3, 4]


def test_filtro_nao_deixa_passar_linha_sem_mundo():
    """Linha sem mundo em contexto financeiro é dado corrompido, não "de ambos"."""
    linhas = [{"id": 1, "mundo": "digital"}, {"id": 2, "mundo": None}]
    assert [x["id"] for x in mod_mundo.filtra(linhas, "digital")] == [1]
    assert [x["id"] for x in mod_mundo.filtra(linhas, "ambos")] == [1]


# ── Obrigatoriedade na criação ───────────────────────────────────────────────


def test_mundo_e_obrigatorio_ao_criar():
    with pytest.raises(ErroValidacao) as capturado:
        mod_mundo.exige("lancamentos", None)
    assert capturado.value.campos["mundo"]


def test_mundo_valido_passa():
    assert mod_mundo.exige("lancamentos", "digital") == "digital"


def test_entidade_sem_mundo_nao_exige():
    """As quatro exceções documentadas — RN-15 atualizado, D-04."""
    for entidade in ("categorias", "subcategorias", "tags", "clientes"):
        assert mod_mundo.tem_mundo(entidade) is False
        assert mod_mundo.exige(entidade, None) is None


def test_entidades_financeiras_tem_mundo():
    for entidade in (
        "lancamentos",
        "recorrencias",
        "parcelamentos",
        "funcionarios",
        "servicos",
        "centros_custo",
    ):
        assert mod_mundo.tem_mundo(entidade) is True


# ── Imutabilidade (FR-005) ───────────────────────────────────────────────────


def test_alterar_mundo_e_recusado_com_rn_15():
    with pytest.raises(ErroRegraViolada) as capturado:
        mod_mundo.recusa_alteracao("digital", "infra")

    erro = capturado.value
    assert erro.status == 409
    assert erro.codigo == "regra_violada"
    assert erro.requisito == "RN-15"
    assert "não pode ser alterado" in erro.mensagem.lower()


def test_mandar_o_mesmo_mundo_nao_e_alteracao():
    """O PUT reenvia o corpo inteiro; mundo igual não pode virar erro."""
    mod_mundo.recusa_alteracao("digital", "digital")


def test_mundo_ausente_no_corpo_nao_e_alteracao():
    mod_mundo.recusa_alteracao("digital", None)


def test_erro_do_gatilho_do_banco_vira_erro_de_negocio_em_pt_br():
    """O banco levanta SQLSTATE RN015; o usuário não pode ver isso cru.

    É a rede de segurança: se algum caminho de código esquecer de chamar
    `recusa_alteracao`, o gatilho recusa e a tradução mantém a mensagem em PT-BR
    com o requisito citado, em vez de um 500 com texto de Postgres.
    """

    class ErroFalsoDoBanco(Exception):
        sqlstate = "RN015"

    traduzido = mod_mundo.traduz_erro_do_banco(ErroFalsoDoBanco())
    assert isinstance(traduzido, ErroRegraViolada)
    assert traduzido.requisito == "RN-15"


def test_outro_erro_de_banco_nao_e_confundido_com_rn_15():
    class OutroErro(Exception):
        sqlstate = "23505"

    assert mod_mundo.traduz_erro_do_banco(OutroErro()) is None
