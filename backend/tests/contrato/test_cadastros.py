"""Contrato dos cadastros — contracts/cadastros.md §1 a §7.

Roda sem banco: confere que todo endpoint acordado existe no `/api/docs` e declara o
papel. O que muda dado está nos testes `integracao`.

Tarefa: T112 (parte de contrato)
"""

import pytest

pytestmark = pytest.mark.contrato

ENDPOINTS_ACORDADOS = [
    # §1 categorias
    ("get", "/api/categorias"),
    ("post", "/api/categorias"),
    ("get", "/api/categorias/{categoria_id}"),
    ("put", "/api/categorias/{categoria_id}"),
    ("post", "/api/categorias/{categoria_id}/arquivar"),
    ("post", "/api/categorias/{categoria_id}/desarquivar"),
    # §2 subcategorias
    ("post", "/api/categorias/{categoria_id}/subcategorias"),
    ("put", "/api/subcategorias/{subcategoria_id}"),
    ("post", "/api/subcategorias/{subcategoria_id}/arquivar"),
    # §3 clientes
    ("get", "/api/clientes"),
    ("post", "/api/clientes"),
    ("get", "/api/clientes/{cliente_id}"),
    ("put", "/api/clientes/{cliente_id}"),
    ("post", "/api/clientes/{cliente_id}/arquivar"),
    ("post", "/api/clientes/{cliente_id}/desarquivar"),
    # §4 funcionários
    ("get", "/api/funcionarios"),
    ("post", "/api/funcionarios"),
    ("get", "/api/funcionarios/{funcionario_id}"),
    ("put", "/api/funcionarios/{funcionario_id}"),
    ("post", "/api/funcionarios/{funcionario_id}/arquivar"),
    # §5 serviços
    ("get", "/api/servicos"),
    ("post", "/api/servicos"),
    ("put", "/api/servicos/{servico_id}"),
    ("post", "/api/servicos/{servico_id}/arquivar"),
    # §6 centros de custo
    ("get", "/api/centros-custo"),
    ("post", "/api/centros-custo"),
    ("put", "/api/centros-custo/{centro_id}"),
    ("post", "/api/centros-custo/{centro_id}/arquivar"),
    # §7 tags
    ("get", "/api/tags"),
    ("post", "/api/tags"),
    ("put", "/api/tags/{tag_id}"),
    ("delete", "/api/tags/{tag_id}"),
]

# Escrita de cadastro estrutural é de gestor (contracts/README.md §Papel exigido).
SO_DE_GESTOR = [
    ("post", "/api/categorias"),
    ("put", "/api/categorias/{categoria_id}"),
    ("post", "/api/categorias/{categoria_id}/arquivar"),
    ("post", "/api/clientes"),
    ("put", "/api/clientes/{cliente_id}"),
    ("post", "/api/clientes/{cliente_id}/arquivar"),
    ("post", "/api/funcionarios"),
    ("put", "/api/funcionarios/{funcionario_id}"),
    ("post", "/api/funcionarios/{funcionario_id}/arquivar"),
    ("post", "/api/servicos"),
    ("put", "/api/servicos/{servico_id}"),
]


@pytest.fixture
def openapi(cliente) -> dict:
    return cliente.get("/api/openapi.json").json()


@pytest.mark.parametrize(("metodo", "caminho"), ENDPOINTS_ACORDADOS)
def test_endpoint_do_contrato_existe_na_api(openapi, metodo, caminho):
    assert caminho in openapi["paths"], f"{caminho} está em contracts/ e não existe na API."
    assert metodo in openapi["paths"][caminho], f"{metodo.upper()} {caminho} não existe na API."


@pytest.mark.parametrize(("metodo", "caminho"), ENDPOINTS_ACORDADOS)
def test_todo_endpoint_declara_o_papel(openapi, metodo, caminho):
    operacao = openapi["paths"][caminho][metodo]
    texto = (operacao.get("description") or "") + (operacao.get("summary") or "")
    assert "Papel" in texto, f"{metodo.upper()} {caminho} não declara o papel."


@pytest.mark.parametrize(("metodo", "caminho"), SO_DE_GESTOR)
def test_escrita_de_cadastro_estrutural_e_so_de_gestor(openapi, metodo, caminho):
    descricao = openapi["paths"][caminho][metodo]["description"].lower()
    assert "gestor" in descricao
    assert "operador" not in descricao, (
        f"{metodo.upper()} {caminho} aparece como aberto a operador — a regra geral é que "
        "cadastro estrutural é de gestor (contracts/README.md)."
    )


def test_operador_pode_criar_tag(openapi):
    """`RN-14`: tags são livres, e criá-las no fluxo de lançamento é o uso esperado."""
    descricao = openapi["paths"]["/api/tags"]["post"]["description"].lower()
    assert "operador" in descricao


def test_cliente_nao_tem_campo_mundo_no_corpo(openapi):
    """D-04, a 2ª exceção a `RN-15`. `mundo_cobranca` é outra coisa."""
    esquemas = openapi["components"]["schemas"]
    corpo = esquemas["ClienteEntrada"]["properties"]
    assert "mundo" not in corpo
    assert "mundo_cobranca" in corpo


def test_funcionario_tem_mundo_obrigatorio(openapi):
    """A diferença de modelagem em relação a cliente (`RN-15`)."""
    esquema = openapi["components"]["schemas"]["FuncionarioEntrada"]
    assert "mundo" in esquema["properties"]
    assert "mundo" in esquema["required"]
