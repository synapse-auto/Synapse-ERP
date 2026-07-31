"""Contrato de recorrências, parcelamento e rotinas — contracts §3, §4 e plataforma §6.

Roda **sem banco**: confere o OpenAPI publicado e os serializadores, que são funções
puras. O comportamento contra Postgres real está nos testes marcados `integracao`.

Tarefa: T086 (parte de contrato)
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.recorrencias import servico

pytestmark = pytest.mark.contrato

ENDPOINTS_ACORDADOS = [
    ("get", "/api/recorrencias"),
    ("post", "/api/recorrencias"),
    ("post", "/api/recorrencias/previa"),
    ("get", "/api/recorrencias/{recorrencia_id}"),
    ("put", "/api/recorrencias/{recorrencia_id}"),
    ("post", "/api/recorrencias/{recorrencia_id}/desativar"),
    ("delete", "/api/recorrencias/{recorrencia_id}"),
    ("post", "/api/recorrencias/{recorrencia_id}/continuar-geracao"),
    ("post", "/api/parcelamentos"),
    ("get", "/api/parcelamentos/{parcelamento_id}"),
    ("post", "/api/rotinas/diaria"),
    ("get", "/api/rotinas/estado"),
]


@pytest.fixture
def openapi(cliente) -> dict:
    resposta = cliente.get("/api/openapi.json")
    assert resposta.status_code == 200
    return resposta.json()


@pytest.mark.parametrize(("metodo", "caminho"), ENDPOINTS_ACORDADOS)
def test_endpoint_do_contrato_existe_na_api(openapi, metodo, caminho):
    assert caminho in openapi["paths"], f"{caminho} está em contracts/ e não existe na API."
    assert metodo in openapi["paths"][caminho], f"{metodo.upper()} {caminho} não existe na API."


def test_delete_de_recorrencia_e_so_de_gestor(openapi):
    """contracts §3: apagar a regra é ato estrutural; desativar resolve o dia a dia."""
    descricao = openapi["paths"]["/api/recorrencias/{recorrencia_id}"]["delete"]["description"]
    assert "gestor" in descricao.lower()
    assert "operador" not in descricao.lower()


def test_estado_das_rotinas_e_so_de_gestor(openapi):
    descricao = openapi["paths"]["/api/rotinas/estado"]["get"]["description"]
    assert "gestor" in descricao.lower()


def test_rotina_diaria_aceita_get_por_causa_do_vercel_cron(openapi):
    """Divergência declarada: o cron da Vercel só faz `GET` e sem cabeçalho próprio.

    O `GET` **precisa** aparecer no `/api/docs`, senão o contrato executável esconde um
    endpoint que existe — e T208 trata divergência como bug.
    """
    assert "get" in openapi["paths"]["/api/rotinas/diaria"]
    descricao = openapi["paths"]["/api/rotinas/diaria"]["get"]["description"]
    assert "Cron" in descricao


def test_previa_vem_antes_da_rota_com_id(cliente):
    """`/previa` não pode ser lido como um `{recorrencia_id}` (ordem de registro)."""
    resposta = cliente.post("/api/recorrencias/previa", json={})
    assert resposta.json()["erro"]["codigo"] == "nao_autenticado"


def test_rotina_sem_segredo_responde_401_e_nao_500(cliente):
    """Endpoint de máquina: sem segredo, recusa limpa no formato único de erro."""
    resposta = cliente.post("/api/rotinas/diaria")
    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "nao_autenticado"


def test_rotina_com_segredo_errado_tambem_recusa(cliente):
    resposta = cliente.post("/api/rotinas/diaria", headers={"X-Segredo-Rotina": "chute"})
    assert resposta.status_code == 401


# ── Formato da recorrência ──────────────────────────────────────────────────


def _linha_falsa(**sobrescreve):
    base = {
        "id": uuid4(),
        "mundo": "digital",
        "tipo": "receita",
        "descricao": "Mensalidade CRM — Estrutural Vidros",
        "valor": Decimal("2000.00"),
        "frequencia": "mensal",
        "intervalo_dias": None,
        "dia_vencimento": 10,
        "mes_vencimento": None,
        "data_inicio": date(2025, 3, 10),
        "data_fim": None,
        "total_parcelas": None,
        "efetivar_automaticamente": False,
        "gerada_ate": date(2027, 7, 30),
        "ativa": True,
        "categoria_id": uuid4(),
        "categoria_nome": "Clientes",
        "categoria_cor": "#8B6CF0",
        "categoria_icone": "users",
        "categoria_especial": True,
        "categoria_vinculo": "cliente",
        "subcategoria_id": None,
        "subcategoria_nome": None,
        "servico_id": None,
        "servico_nome": None,
        "centro_custo_id": None,
        "centro_custo_nome": None,
        "cliente_id": None,
        "funcionario_id": None,
        "criado_em": None,
        "criado_por": uuid4(),
        "excluido_em": None,
        "ocorrencias_geradas": 17,
        "proxima_ocorrencia": date(2026, 8, 10),
    }
    return base | sobrescreve


def test_dinheiro_e_datas_saem_no_formato_da_fronteira():
    saida = servico.para_json(_linha_falsa(valor=Decimal("2000.5")))
    assert saida["valor"] == "2000.50"
    assert saida["data_inicio"] == "2025-03-10"
    assert saida["data_fim"] is None


def test_rotulo_da_regra_vem_pronto_do_servidor():
    """`RNF-02`: a tela mostra o texto que veio, não monta "Mensal, dia {n}"."""
    assert servico.rotulo_da_regra(_linha_falsa()) == "Mensal, dia 10"
    assert (
        servico.rotulo_da_regra(_linha_falsa(frequencia="dias", intervalo_dias=15))
        == "A cada 15 dias"
    )
    assert (
        servico.rotulo_da_regra(_linha_falsa(frequencia="semanal", dia_vencimento=3))
        == "Semanal, toda quarta"
    )
    assert (
        servico.rotulo_da_regra(
            _linha_falsa(frequencia="anual", dia_vencimento=5, mes_vencimento=3)
        )
        == "Anual, 5 de março"
    )


def test_resultado_da_geracao_tem_os_quatro_campos_do_contrato():
    """contracts §3: `{concluida, cursor, geradas, total}` (D-02a)."""
    resultado = servico.ResultadoDaGeracao(
        geradas=200, total=640, concluida=False, cursor=date(2026, 5, 10)
    )
    assert resultado.como_dicionario() == {
        "concluida": False,
        "cursor": "2026-05-10",
        "geradas": 200,
        "total": 640,
    }
