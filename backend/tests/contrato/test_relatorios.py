"""Contrato dos relatórios — contracts/consultas.md §3.

O que estes testes protegem, além da existência dos endpoints: que `csv` e `pdf` levem
**os mesmos números do `json`**. É a promessa mais fácil de quebrar do contrato, porque
cada formato tem seu próprio código de montagem — e a única defesa é montar a resposta
uma vez e passar o resultado pronto aos exportadores, que é o que os testes conferem.

Tarefa: T121
"""

import pytest

from app.relatorios import exportacao_csv, exportacao_pdf

pytestmark = pytest.mark.contrato

ENDPOINTS_ACORDADOS = [
    ("get", "/api/relatorios/dre"),
    ("get", "/api/relatorios/clientes"),
    ("get", "/api/relatorios/variacao-categorias"),
    ("get", "/api/relatorios/matriz-mensal"),
]


@pytest.fixture
def openapi(cliente) -> dict:
    return cliente.get("/api/openapi.json").json()


@pytest.mark.parametrize(("metodo", "caminho"), ENDPOINTS_ACORDADOS)
def test_endpoint_existe_e_declara_papel(openapi, metodo, caminho):
    assert caminho in openapi["paths"], f"{caminho} está em contracts/ e não existe na API."
    operacao = openapi["paths"][caminho][metodo]
    assert "Papel:" in (operacao.get("description") or "")


@pytest.mark.parametrize(("metodo", "caminho"), ENDPOINTS_ACORDADOS)
def test_todo_relatorio_aceita_formato(openapi, metodo, caminho):
    """contracts §3: `formato` = `json` (padrão) | `csv` | `pdf`."""
    nomes = {p["name"] for p in openapi["paths"][caminho][metodo]["parameters"]}
    assert "formato" in nomes
    assert {"mundo", "periodo", "data_inicio", "data_fim"} <= nomes


# ── Os exportadores usam a resposta pronta, não uma segunda consulta ────────

DRE_DE_EXEMPLO = {
    "receitas": [
        {
            "nome": "Clientes",
            "valor": "14000.00",
            "subcategorias": [{"nome": "Estrutural Vidros", "valor": "4000.00"}],
        }
    ],
    "despesas": [
        {
            "nome": "Funcionários",
            "valor": "2100.00",
            "subcategorias": [{"nome": "Dylan", "valor": "1200.00"}],
        }
    ],
    "receita_bruta": "18400.00",
    "despesa_total": "9250.00",
    "resultado": "9150.00",
    "margem_percentual": "49.7",
    "leitura_linguagem_natural": "Julho teve R$ 18.400,00 de receita.",
}


def test_csv_do_dre_traz_os_mesmos_numeros_do_json():
    texto = exportacao_csv.dre(DRE_DE_EXEMPLO).decode("utf-8-sig")
    assert "Estrutural Vidros" in texto
    assert "18.400,00" in texto
    assert "9.150,00" in texto
    # Nenhum número aparece no formato de transporte — o arquivo é de leitura humana.
    assert "18400.00" not in texto


def test_csv_do_dre_indenta_a_hierarquia_por_coluna():
    """Categoria e subcategoria em colunas distintas, para a planilha poder agrupar."""
    linhas = exportacao_csv.dre(DRE_DE_EXEMPLO).decode("utf-8-sig").splitlines()
    cabecalho = linhas[0].split(";")
    assert cabecalho == ["Tipo", "Categoria", "Subcategoria", "Valor"]

    da_categoria = [linha for linha in linhas if linha.startswith("Receita;Clientes;;")]
    da_subcategoria = [
        linha for linha in linhas if linha.startswith("Receita;Clientes;Estrutural Vidros;")
    ]
    assert da_categoria and da_subcategoria


def test_csv_usa_separador_e_decimal_brasileiros_com_bom():
    arquivo = exportacao_csv.dre(DRE_DE_EXEMPLO)
    assert arquivo.startswith(b"\xef\xbb\xbf")
    assert ";" in arquivo.decode("utf-8-sig").splitlines()[0]


def test_numero_negativo_mantem_o_sinal():
    negativo = {**DRE_DE_EXEMPLO, "resultado": "-1234.50"}
    assert "-1.234,50" in exportacao_csv.dre(negativo).decode("utf-8-sig")


def test_csv_de_clientes_traz_a_quebra_por_mundo():
    """A quebra existe porque o cliente não tem mundo, mas a receita dele tem (D-04)."""
    resposta = {
        "clientes": [
            {
                "nome": "Estrutural Vidros",
                "empresa": "Estrutural",
                "total_recebido": "4000.00",
                "percentual_faturamento": "21.7",
                "situacao": "atrasado",
                "quebra_por_mundo": {"digital": "4000.00", "infra": "0.00"},
            }
        ]
    }
    texto = exportacao_csv.clientes(resposta).decode("utf-8-sig")
    assert "Synapse Digital" in texto
    assert "Synapse Infra" in texto
    assert "Atrasado" in texto
    assert "4.000,00" in texto


def test_csv_de_matriz_tem_uma_coluna_por_mes():
    resposta = {
        "meses": ["2026-05", "2026-06"],
        "linhas": [
            {
                "nome": "Marketing",
                "valores": {"2026-05": "800.00", "2026-06": "1080.00"},
                "total": "1880.00",
            }
        ],
    }
    linhas = exportacao_csv.matriz_mensal(resposta).decode("utf-8-sig").splitlines()
    assert linhas[0].split(";") == ["Categoria", "2026-05", "2026-06", "Total"]
    assert linhas[1].split(";") == ["Marketing", "800,00", "1.080,00", "1.880,00"]


def test_csv_de_variacao_marca_o_destaque():
    resposta = {
        "linhas": [
            {
                "nome": "Marketing",
                "valores": [
                    {"mes": "2026-05", "valor": "800.00", "variacao_percentual": None},
                    {
                        "mes": "2026-06",
                        "valor": "1080.00",
                        "variacao_percentual": "35.0",
                        "destacar": True,
                    },
                ],
            }
        ]
    }
    texto = exportacao_csv.variacao_categorias(resposta).decode("utf-8-sig")
    assert "35,0" in texto
    assert texto.strip().endswith("Sim")


# ── PDF ────────────────────────────────────────────────────────────────────


def test_pdf_do_dre_sai_como_pdf_de_verdade():
    arquivo = exportacao_pdf.dre(DRE_DE_EXEMPLO, periodo_rotulo="Este mês")
    assert arquivo.startswith(b"%PDF-"), "A saída não é um PDF."
    assert len(arquivo) > 1000


def test_pdf_e_csv_partem_da_mesma_resposta():
    """A promessa do contrato: `csv`/`pdf` **não** são um recorte diferente.

    Os dois recebem o mesmo dicionário já montado pelo endpoint. Se algum dia um deles
    passar a consultar o banco por conta, este teste continua passando — mas a
    assinatura das funções mudaria, e é isso que se está fixando aqui.
    """
    import inspect

    for funcao in (exportacao_csv.dre, exportacao_pdf.dre):
        parametros = list(inspect.signature(funcao).parameters)
        assert parametros[0] == "resposta"
        assert "conexao" not in parametros
