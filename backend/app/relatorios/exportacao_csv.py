"""CSV dos relatórios (`FR-094`).

Mesmas convenções do CSV de lançamentos (`app/lancamentos/exportacao_csv.py`): separador
`;`, decimal `1.234,50`, BOM UTF-8. O arquivo é aberto no Excel por uma pessoa, então vale
`RNF-03` e não as convenções de transporte de contracts/README.md.

**Os mesmos números do `json`, nunca um recorte diferente** (contracts/consultas.md §3).
Por isso estas funções recebem a resposta já montada pelo endpoint, em vez de consultarem
o banco por conta: um segundo caminho até o dado é um segundo lugar onde o número pode
divergir.

Tarefa: T119
"""

import csv
import io
from typing import Any

BOM = b"\xef\xbb\xbf"


def _numero(texto: str | None) -> str:
    """`"1234.50"` → `"1.234,50"`. Recebe o valor já formatado pela API."""
    if texto is None:
        return ""
    inteiro, _, decimais = str(texto).partition(".")
    negativo = inteiro.startswith("-")
    inteiro = inteiro.lstrip("-")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro or "0")
    return f"{'-' if negativo else ''}{'.'.join(grupos)},{decimais or '00'}"


def _escreve(cabecalho: list[str], linhas: list[list[Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return BOM + buffer.getvalue().encode("utf-8")


def dre(resposta: dict[str, Any]) -> bytes:
    """DRE achatado: uma linha por categoria, seguida das subcategorias indentadas."""
    linhas: list[list[Any]] = []

    for bloco, rotulo in (("receitas", "Receita"), ("despesas", "Despesa")):
        for categoria in resposta.get(bloco, []):
            linhas.append([rotulo, categoria["nome"], "", _numero(categoria["valor"])])
            for sub in categoria.get("subcategorias", []):
                linhas.append([rotulo, categoria["nome"], sub["nome"], _numero(sub["valor"])])

    linhas.append([])
    linhas.append(["Receita bruta", "", "", _numero(resposta["receita_bruta"])])
    linhas.append(["Despesa total", "", "", _numero(resposta["despesa_total"])])
    linhas.append(["Resultado", "", "", _numero(resposta["resultado"])])
    linhas.append(
        ["Margem (%)", "", "", (resposta.get("margem_percentual") or "").replace(".", ",")]
    )

    return _escreve(["Tipo", "Categoria", "Subcategoria", "Valor"], linhas)


def clientes(resposta: dict[str, Any]) -> bytes:
    linhas = [
        [
            item["nome"],
            item.get("empresa") or "",
            _numero(item["total_recebido"]),
            (item.get("percentual_faturamento") or "").replace(".", ","),
            "Atrasado" if item["situacao"] == "atrasado" else "Em dia",
            _numero(item["quebra_por_mundo"]["digital"]),
            _numero(item["quebra_por_mundo"]["infra"]),
        ]
        for item in resposta["clientes"]
    ]
    return _escreve(
        [
            "Cliente",
            "Empresa",
            "Total recebido",
            "% do faturamento",
            "Situação",
            "Synapse Digital",
            "Synapse Infra",
        ],
        linhas,
    )


def variacao_categorias(resposta: dict[str, Any]) -> bytes:
    linhas = []
    for linha in resposta["linhas"]:
        for valor in linha["valores"]:
            linhas.append(
                [
                    linha["nome"],
                    valor["mes"],
                    _numero(valor["valor"]),
                    (valor.get("variacao_percentual") or "").replace(".", ","),
                    "Sim" if valor.get("destacar") else "",
                ]
            )
    return _escreve(["Categoria", "Mês", "Valor", "Variação (%)", "Destacar"], linhas)


def matriz_mensal(resposta: dict[str, Any]) -> bytes:
    """Matriz de verdade: uma coluna por mês, como a pessoa vê na tela."""
    meses = resposta["meses"]
    linhas = [
        [
            linha["nome"],
            *[_numero(linha["valores"].get(mes, "0.00")) for mes in meses],
            _numero(linha["total"]),
        ]
        for linha in resposta["linhas"]
    ]
    return _escreve(["Categoria", *meses, "Total"], linhas)
