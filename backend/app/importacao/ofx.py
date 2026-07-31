"""Leitura de OFX — `FR-044`, T134.

OFX é o formato que todo banco brasileiro exporta e que já vem **estruturado**: data,
valor e memo em campos próprios, sem coluna para o usuário mapear. Por isso a leitura
devolve o mesmo formato do CSV (`Leitura`), com as colunas já nomeadas — daí para frente
o fluxo é idêntico, e `mapeamento.py` não sabe de que formato o arquivo veio.

## Sem `ofxparse`

A biblioteca arrasta `lxml` e `beautifulsoup4` (plan.md §Constraints, e o `pyproject`
registra a decisão). OFX 1.x é SGML e OFX 2.x é XML; nos dois, os campos que interessam
são cinco tags simples, e uma expressão regular sobre `<STMTTRN>` resolve sem
dependência nenhuma.

Isso é uma **troca declarada**, não um atalho: um OFX malformado que a `ofxparse`
aceitaria pode falhar aqui. O tratamento é dizer isso em PT-BR e sugerir o CSV, em vez
de gravar dado torto.

Tarefa: T134
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.comum.erros import ErroValidacao
from app.importacao.csv import CODIFICACOES, MAXIMO_DE_LINHAS, Leitura

# Uma transação por bloco `<STMTTRN>`, em OFX 1.x (SGML) e 2.x (XML).
_TRANSACAO = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)


def _campo(bloco: str, tag: str) -> str:
    """Lê `<TAG>valor` (SGML, sem fechamento) ou `<TAG>valor</TAG>` (XML)."""
    achado = re.search(rf"<{tag}>\s*([^<\r\n]*)", bloco, re.IGNORECASE)
    return achado.group(1).strip() if achado else ""


def _data(texto: str) -> str:
    """`20260710` ou `20260710120000[-3:BRT]` → `2026-07-10`."""
    limpo = re.sub(r"\D", "", texto)[:8]
    if len(limpo) != 8:
        return ""
    try:
        return datetime.strptime(limpo, "%Y%m%d").date().isoformat()
    except ValueError:
        return ""


def le(conteudo: bytes) -> Leitura:
    """Devolve a mesma estrutura do CSV, com colunas já nomeadas."""
    texto = None
    codificacao = CODIFICACOES[0]
    for tentativa in CODIFICACOES:
        try:
            texto = conteudo.decode(tentativa)
            codificacao = tentativa
            break
        except UnicodeDecodeError:
            continue

    if texto is None:
        raise ErroValidacao(
            "Não foi possível ler o arquivo OFX — a codificação não é reconhecida.",
            requisito="FR-044",
            campos={"arquivo": "Exporte de novo pelo banco, ou use o CSV."},
        )

    blocos = _TRANSACAO.findall(texto)
    if not blocos:
        raise ErroValidacao(
            "Nenhuma transação encontrada no arquivo OFX.",
            requisito="FR-044",
            campos={
                "arquivo": (
                    "O arquivo pode estar em um formato que não conseguimos ler. "
                    "Exporte em CSV e use a importação de CSV."
                )
            },
        )
    if len(blocos) > MAXIMO_DE_LINHAS:
        raise ErroValidacao(
            f"O arquivo tem mais de {MAXIMO_DE_LINHAS} transações. Divida em partes.",
            requisito="FR-044",
            campos={"arquivo": f"Máximo {MAXIMO_DE_LINHAS} por importação."},
        )

    linhas = []
    for bloco in blocos:
        bruto = _campo(bloco, "TRNAMT")
        try:
            valor = Decimal(bruto.replace(",", ".")) if bruto else None
        except InvalidOperation:
            valor = None

        linhas.append(
            {
                "data": _data(_campo(bloco, "DTPOSTED")),
                # `MEMO` costuma ser mais descritivo que `NAME`; quando falta, cai no
                # `NAME`. Ficar sem descrição é problema que o mapeamento aponta.
                "descricao": _campo(bloco, "MEMO") or _campo(bloco, "NAME"),
                "valor": str(valor) if valor is not None else bruto,
                "identificador": _campo(bloco, "FITID"),
                "tipo_ofx": _campo(bloco, "TRNTYPE"),
            }
        )

    return Leitura(
        colunas=["data", "descricao", "valor", "identificador", "tipo_ofx"],
        linhas=linhas,
        separador="ofx",
        codificacao=codificacao,
        total_de_linhas=len(linhas),
        # OFX já vem estruturado: o mapeamento chega preenchido e o usuário só confirma.
        sugestoes={
            "data": "data",
            "descricao": "descricao",
            "valor": "valor",
            "categoria": None,
        },
    )
