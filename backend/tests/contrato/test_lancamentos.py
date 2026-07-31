"""Contrato dos lançamentos — resposta × `contracts/lancamentos.md`.

O que estes testes protegem: `contracts/` é o contrato **acordado** e `/api/docs` é o
contrato **executável**; a constituição diz que divergência entre os dois é bug, não
detalhe (contracts/README.md, T208). Sem teste, essa conferência acontece só quando
alguém abre os dois arquivos lado a lado — ou seja, nunca.

Rodam **sem banco**: conferem o OpenAPI que o app publica e o formato dos
serializadores, que são funções puras. O comportamento contra Postgres real é dos
testes marcados `integracao`.

Tarefas: T069 (contrato de lançamentos), T062, T063, T065
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.lancamentos import exportacao_csv, servico

pytestmark = pytest.mark.contrato


# ── Os endpoints que o contrato declara existem, com o método certo ──────────

# contracts/lancamentos.md §1, §2, §5 e §6 (a parte de exportação; a importação é B6).
ENDPOINTS_ACORDADOS = [
    ("get", "/api/lancamentos"),
    ("post", "/api/lancamentos"),
    ("get", "/api/lancamentos/{lancamento_id}"),
    ("put", "/api/lancamentos/{lancamento_id}"),
    ("delete", "/api/lancamentos/{lancamento_id}"),
    ("post", "/api/lancamentos/{lancamento_id}/efetivar"),
    ("post", "/api/lancamentos/{lancamento_id}/cancelar"),
    ("post", "/api/lancamentos/{lancamento_id}/duplicar"),
    ("post", "/api/lancamentos/{lancamento_id}/dividir"),
    ("post", "/api/lancamentos/lote"),
    ("post", "/api/lancamentos/acoes-em-massa"),
    ("get", "/api/lixeira"),
    ("post", "/api/lixeira/{lancamento_id}/restaurar"),
    ("post", "/api/lancamentos/{lancamento_id}/anexos"),
    ("get", "/api/anexos/{anexo_id}"),
    ("delete", "/api/anexos/{anexo_id}"),
    ("get", "/api/lancamentos/exportacao"),
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


def test_todo_endpoint_de_lancamento_declara_o_papel(openapi):
    """Constituição: "endpoint novo sem papel declarado não passa"."""
    sem_papel = []
    for metodo, caminho in ENDPOINTS_ACORDADOS:
        operacao = openapi["paths"][caminho][metodo]
        texto = (operacao.get("description") or "") + (operacao.get("summary") or "")
        if "Papel:" not in texto:
            sem_papel.append(f"{metodo.upper()} {caminho}")
    assert not sem_papel, f"Endpoints sem papel declarado: {sem_papel}"


def test_exportacao_e_lote_vem_antes_da_rota_com_id(cliente):
    """`/exportacao` e `/lote` não podem ser lidos como um `{lancamento_id}`.

    O FastAPI casa a rota na ordem de registro. Com `/{lancamento_id}` na frente,
    `GET /api/lancamentos/exportacao` tentaria converter "exportacao" em UUID e
    responderia `400 validacao` — um bug que só aparece em produção, porque o
    OpenAPI continua listando as duas rotas normalmente.
    """
    # Sem token: quem responde é a autenticação, o que prova que a rota casou. Se
    # tivesse caído na rota de `{lancamento_id}`, o erro seria de validação de UUID.
    for caminho in ("/api/lancamentos/exportacao",):
        resposta = cliente.get(caminho)
        assert resposta.json()["erro"]["codigo"] == "nao_autenticado"

    for caminho in ("/api/lancamentos/lote", "/api/lancamentos/acoes-em-massa"):
        resposta = cliente.post(caminho, json={})
        assert resposta.json()["erro"]["codigo"] == "nao_autenticado"


# ── Formato do lançamento na resposta (contracts/lancamentos.md §1) ──────────


def _linha_falsa(**sobrescreve):
    """Uma linha como o repositório devolve, para exercitar o serializador sem banco."""
    base = {
        "id": uuid4(),
        "mundo": "digital",
        "tipo": "receita",
        "descricao": "Mensalidade CRM — Estrutural Vidros",
        "valor": Decimal("2000.00"),
        "data": date(2026, 7, 10),
        "status": "efetivado",
        "efetivar_automaticamente": False,
        "observacoes": None,
        "moeda_origem": "BRL",
        "valor_origem": None,
        "cotacao": None,
        "cotacao_manual": False,
        "recorrencia_id": None,
        "parcelamento_id": None,
        "parcela_numero": None,
        "parcela_total": None,
        "lancamento_pai_id": None,
        "versao": 1,
        "quantidade_anexos": 0,
        "tem_partes": False,
        "categoria_id": uuid4(),
        "categoria_nome": "Clientes",
        "categoria_cor": "#8B6CF0",
        "categoria_icone": "users",
        "categoria_especial": True,
        "categoria_vinculo": "cliente",
        "subcategoria_id": None,
        "subcategoria_nome": None,
        "subcategoria_cor": None,
        "subcategoria_cliente_id": None,
        "servico_id": None,
        "servico_nome": None,
        "servico_mundo": None,
        "centro_custo_id": None,
        "centro_custo_nome": None,
        "centro_custo_mundo": None,
    }
    return base | sobrescreve


CAMPOS_DO_LANCAMENTO = {
    "id",
    "mundo",
    "tipo",
    "descricao",
    "valor",
    "data",
    "status",
    "efetivar_automaticamente",
    "categoria",
    "subcategoria",
    "servico",
    "centro_custo",
    "tags",
    "moeda_origem",
    "valor_origem",
    "cotacao",
    "cotacao_manual",
    "observacoes",
    "origem",
    "tem_anexos",
    "quantidade_anexos",
    "tem_partes",
    "versao",
}


def test_lancamento_tem_exatamente_os_campos_do_contrato():
    saida = servico.para_json(_linha_falsa())
    assert set(saida) == CAMPOS_DO_LANCAMENTO


def test_dinheiro_sai_como_string_decimal_com_duas_casas():
    """contracts/README.md: `"1234.56"`, nunca float. `1.234,56` é do frontend."""
    saida = servico.para_json(_linha_falsa(valor=Decimal("1234.5")))
    assert saida["valor"] == "1234.50"
    assert isinstance(saida["valor"], str)


def test_data_sai_em_iso_nao_em_dd_mm_aaaa():
    saida = servico.para_json(_linha_falsa(data=date(2026, 3, 9)))
    assert saida["data"] == "2026-03-09"


def test_ausencia_e_null_explicito():
    """contracts/README.md §Ausência: `null`, não campo omitido."""
    saida = servico.para_json(_linha_falsa())
    assert saida["subcategoria"] is None
    assert saida["servico"] is None
    assert saida["centro_custo"] is None
    assert saida["valor_origem"] is None


def test_origem_identifica_parcela_com_a_posicao():
    """`FR-043`: "Parcela 2/3" com link para a série."""
    saida = servico.para_json(
        _linha_falsa(parcelamento_id=uuid4(), parcela_numero=2, parcela_total=3)
    )
    assert saida["origem"]["tipo"] == "parcelamento"
    assert saida["origem"]["rotulo"] == "Parcela 2/3"


def test_acoes_disponiveis_vem_do_servidor_e_dependem_do_status():
    """`FR-042`: quem decide se aparece "confirmar recebimento" é o servidor."""
    programado = servico.acoes_disponiveis(_linha_falsa(status="programado"))
    assert "confirmar_efetivacao" in programado

    efetivado = servico.acoes_disponiveis(_linha_falsa(status="efetivado"))
    assert "confirmar_efetivacao" not in efetivado

    cancelado = servico.acoes_disponiveis(_linha_falsa(status="cancelado"))
    assert cancelado == ["duplicar"]


def test_lancamento_com_partes_nao_oferece_dividir_de_novo():
    """`RN-11`: dividir o que já está dividido quebraria a soma."""
    assert "dividir" not in servico.acoes_disponiveis(_linha_falsa(tem_partes=True))


# ── CSV da exportação (T065, `FR-045`) ──────────────────────────────────────


def _linha_de_exportacao(**sobrescreve):
    base = {
        "data": date(2026, 7, 10),
        "mundo": "digital",
        "tipo": "despesa",
        "descricao": "Servidor de produção",
        "valor": Decimal("1234.50"),
        "status": "efetivado",
        "categoria": "Infraestrutura",
        "subcategoria": None,
        "servico": None,
        "centro_custo": None,
        "tags": "recorrente, nuvem",
        "moeda_origem": "BRL",
        "valor_origem": None,
        "cotacao": None,
        "observacoes": None,
    }
    return base | sobrescreve


def test_csv_comeca_com_bom_para_o_excel_nao_quebrar_acento():
    arquivo = exportacao_csv.monta([_linha_de_exportacao()])
    assert arquivo.startswith(b"\xef\xbb\xbf")
    assert "Observações" in arquivo.decode("utf-8")


def test_csv_usa_ponto_e_virgula_e_decimal_brasileiro():
    """`RNF-03`: o arquivo é lido por pessoa no Excel, então vale `1.234,50`."""
    texto = exportacao_csv.monta([_linha_de_exportacao()]).decode("utf-8-sig")
    cabecalho, primeira, *_ = texto.splitlines()

    assert cabecalho.split(";")[0] == "Data"
    colunas = primeira.split(";")
    assert colunas[0] == "10/07/2026"
    assert colunas[4] == "1.234,50"


def test_csv_traduz_mundo_tipo_e_status_para_a_lingua_da_tela():
    texto = exportacao_csv.monta([_linha_de_exportacao()]).decode("utf-8-sig")
    linha = texto.splitlines()[1]
    assert "Synapse Digital" in linha
    assert "Despesa" in linha
    assert "Efetivado" in linha


def test_csv_de_lista_vazia_ainda_traz_o_cabecalho():
    """Estado vazio explicativo também vale para arquivo (edge cases da spec)."""
    texto = exportacao_csv.monta([]).decode("utf-8-sig")
    assert texto.strip().splitlines() == [";".join(exportacao_csv.CABECALHO)]


def test_nome_do_arquivo_descreve_o_filtro_usado():
    nome = exportacao_csv.nome_do_arquivo(date(2026, 7, 1), date(2026, 7, 31), "digital")
    assert nome == "lancamentos-digital-2026-07-01-a-2026-07-31.csv"

    assert (
        exportacao_csv.nome_do_arquivo(date(2026, 7, 1), date(2026, 7, 31), "ambos")
        == "lancamentos-2026-07-01-a-2026-07-31.csv"
    )
