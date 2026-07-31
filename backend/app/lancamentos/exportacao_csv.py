"""Monta o CSV da lista filtrada (`FR-045`).

**O arquivo é apresentação, não transporte.** A API entrega dinheiro como `"1234.56"` e
data como `2026-07-30` (contracts/README.md), mas este arquivo não é lido por programa
nenhum: é aberto no Excel por uma pessoa no Brasil. Então aqui vale `RNF-03` — `1.234,56`
e `dd/mm/aaaa`.

Três decisões que existem só por causa do Excel brasileiro:

- **Separador `;`**, não vírgula. Em máquina configurada em PT-BR a vírgula é separador
  decimal, e o Excel joga a linha inteira numa célula só.
- **BOM UTF-8** no começo. Sem ele o Excel lê o arquivo como ANSI e "Manutenção" vira
  "ManutenÃ§Ã£o".
- **`\r\n`** como fim de linha, que é o que o formato CSV (RFC 4180) pede.

Tarefa: T065
"""

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Any

from app.dominio import mundo as mod_mundo

CABECALHO = [
    "Data",
    "Mundo",
    "Tipo",
    "Descrição",
    "Valor",
    "Status",
    "Categoria",
    "Subcategoria",
    "Serviço",
    "Centro de custo",
    "Tags",
    "Moeda de origem",
    "Valor de origem",
    "Cotação",
    "Observações",
]

ROTULOS_TIPO = {"receita": "Receita", "despesa": "Despesa"}
ROTULOS_STATUS = {
    "programado": "Programado",
    "pendente": "Pendente",
    "efetivado": "Efetivado",
    "atrasado": "Atrasado",
    "cancelado": "Cancelado",
}


def _numero(valor: Any, casas: int = 2) -> str:
    """`Decimal("1234.5")` → `"1.234,50"`. Vazio quando não há valor."""
    if valor is None:
        return ""
    texto = f"{Decimal(str(valor)):,.{casas}f}"
    # Troca em duas etapas: o formato do Python usa `,` para milhar e `.` para decimal,
    # exatamente o inverso do brasileiro. O `X` intermediário evita trocar duas vezes.
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _data(valor: date | None) -> str:
    return "" if valor is None else valor.strftime("%d/%m/%Y")


def monta(linhas: list[dict[str, Any]]) -> bytes:
    """Devolve o arquivo pronto, já codificado.

    Sem `StreamingResponse` de propósito: a conexão com o banco é uma dependência que o
    FastAPI encerra **antes** de o corpo da resposta ser enviado, então um gerador que
    ainda consultasse o banco durante o streaming acharia a conexão fechada. Com o teto
    de linhas aplicado em `rotas.py`, montar tudo na memória é a solução simples que
    funciona (Princípio I).
    """
    buffer = io.StringIO(newline="")
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    escritor.writerow(CABECALHO)

    for linha in linhas:
        escritor.writerow(
            [
                _data(linha["data"]),
                mod_mundo.ROTULOS.get(linha["mundo"], linha["mundo"]),
                ROTULOS_TIPO.get(linha["tipo"], linha["tipo"]),
                linha["descricao"],
                _numero(linha["valor"]),
                ROTULOS_STATUS.get(linha["status"], linha["status"]),
                linha["categoria"],
                linha["subcategoria"] or "",
                linha["servico"] or "",
                linha["centro_custo"] or "",
                linha["tags"],
                linha["moeda_origem"],
                _numero(linha["valor_origem"]),
                _numero(linha["cotacao"], casas=4),
                linha["observacoes"] or "",
            ]
        )

    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def nome_do_arquivo(inicio: date | None, fim: date | None, mundo: str | None) -> str:
    """`lancamentos-digital-2026-07-01-a-2026-07-31.csv`.

    Nome descritivo porque quem exporta duas vezes com filtros diferentes acaba com os
    dois arquivos na mesma pasta de Downloads.
    """
    partes = ["lancamentos"]
    if mundo and mundo != "ambos":
        partes.append(mundo)
    if inicio and fim:
        partes.append(f"{inicio.isoformat()}-a-{fim.isoformat()}")
    return "-".join(partes) + ".csv"
