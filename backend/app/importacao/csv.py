"""Leitura de CSV para importação — `FR-044`.

**Não grava nada.** Este módulo lê o arquivo, detecta as colunas e devolve a prévia. A
gravação é de `mapeamento.py` + o `confirmar`, e em lotes com cursor.

## Por que a prévia existe

Extrato de banco vem com colunas em qualquer ordem, com nomes em qualquer idioma e com
data e dinheiro em qualquer formato. Importar direto significaria descobrir o erro depois
de 300 lançamentos gravados. Com a prévia, o usuário confere 10 linhas e só então
confirma — que é o que `FR-044` pede.

## O que a importação NÃO faz

- **Não deduz `mundo`.** O arquivo não tem essa informação e `RN-15` não admite nulo,
  então o mundo é escolhido no mapeamento, para o arquivo inteiro.
- **Não cria categoria.** Categoria não reconhecida é apontada na prévia para o usuário
  escolher o destino — criar sozinho encheria a base de categorias parecidas.

Tarefa: T133
"""

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.comum.erros import ErroValidacao

# Separadores que aparecem de verdade em extrato brasileiro. Detectados, não perguntados:
# o usuário não sabe qual o banco dele usou.
SEPARADORES = (";", ",", "\t", "|")

CODIFICACOES = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

LINHAS_DA_PREVIA = 10
MAXIMO_DE_LINHAS = 5_000

# Palpite de coluna por nome. Só palpite — o mapeamento final é sempre do usuário.
PISTAS = {
    "data": ("data", "date", "dt", "lancamento", "movimento", "competencia"),
    "descricao": ("descricao", "historico", "memo", "description"),
    "valor": ("valor", "amount", "montante", "credito", "debito", "value"),
    "categoria": ("categoria", "category", "classificacao"),
}


@dataclass
class Leitura:
    colunas: list[str]
    linhas: list[dict[str, str]]
    separador: str
    codificacao: str
    total_de_linhas: int
    sugestoes: dict[str, str | None] = field(default_factory=dict)


def _decodifica(conteudo: bytes) -> tuple[str, str]:
    """Tenta as codificações em ordem. `cp1252`/`latin-1` porque extrato de banco
    brasileiro ainda vem assim, e um acento quebrado vira descrição ilegível."""
    for codificacao in CODIFICACOES:
        try:
            return conteudo.decode(codificacao), codificacao
        except UnicodeDecodeError:
            continue
    raise ErroValidacao(
        "Não foi possível ler o arquivo — a codificação não é reconhecida.",
        requisito="FR-044",
        campos={"arquivo": "Salve como CSV UTF-8 e tente de novo."},
    )


def _detecta_separador(texto: str) -> str:
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    contagens = {sep: primeira.count(sep) for sep in SEPARADORES}
    melhor = max(contagens, key=lambda sep: contagens[sep])
    if contagens[melhor] == 0:
        raise ErroValidacao(
            "O arquivo não parece um CSV — nenhuma coluna foi encontrada na primeira linha.",
            requisito="FR-044",
            campos={"arquivo": "Esperado CSV com separador ; , tab ou |."},
        )
    return melhor


def _sugere(colunas: list[str]) -> dict[str, str | None]:
    """Palpite de qual coluna é o quê, para o usuário só confirmar."""

    def normaliza(texto: str) -> str:
        """Tira acento **antes** de descartar o que não é letra.

        Descartar primeiro transformaria "Histórico" em "histrico", que não casa com
        pista nenhuma — e a coluna mais comum de extrato brasileiro deixaria de ser
        sugerida. `NFKD` separa a letra do acento, e aí o filtro remove só o acento.
        """
        sem_acento = unicodedata.normalize("NFKD", texto.lower())
        return re.sub(r"[^a-z]", "", sem_acento)

    sugestoes: dict[str, str | None] = {}
    for campo, pistas in PISTAS.items():
        achada = None
        for coluna in colunas:
            if any(pista in normaliza(coluna) for pista in pistas):
                achada = coluna
                break
        sugestoes[campo] = achada
    return sugestoes


def le(conteudo: bytes) -> Leitura:
    """Lê o arquivo inteiro na memória e devolve colunas, linhas e palpites.

    Ler tudo é aceitável: o teto de 5.000 linhas cabe com folga, e um extrato mensal
    tem dezenas. Acima do teto, recusa dizendo para dividir — melhor que ser cortado
    pela duração da função no meio da gravação.
    """
    texto, codificacao = _decodifica(conteudo)
    separador = _detecta_separador(texto)

    leitor = csv.DictReader(io.StringIO(texto), delimiter=separador)
    colunas = [coluna.strip() for coluna in (leitor.fieldnames or []) if coluna]
    if not colunas:
        raise ErroValidacao(
            "O arquivo não tem cabeçalho de colunas.",
            requisito="FR-044",
            campos={"arquivo": "A primeira linha precisa nomear as colunas."},
        )

    linhas = []
    for numero, linha in enumerate(leitor, start=1):
        if numero > MAXIMO_DE_LINHAS:
            raise ErroValidacao(
                f"O arquivo tem mais de {MAXIMO_DE_LINHAS} linhas. Divida em partes.",
                requisito="FR-044",
                campos={"arquivo": f"Máximo {MAXIMO_DE_LINHAS} linhas por importação."},
            )
        linhas.append({chave: (valor or "").strip() for chave, valor in linha.items() if chave})

    return Leitura(
        colunas=colunas,
        linhas=linhas,
        separador=separador,
        codificacao=codificacao,
        total_de_linhas=len(linhas),
        sugestoes=_sugere(colunas),
    )


# ── Conversão de valor e data ───────────────────────────────────────────────


def converte_data(texto: str) -> date | None:
    """Aceita `dd/mm/aaaa`, `aaaa-mm-dd` e `dd-mm-aaaa`.

    Ordem importa: `01/02/2026` é 1º de fevereiro no Brasil e 2 de janeiro nos EUA. O
    formato brasileiro vem primeiro porque é o do usuário — e um extrato com data
    trocada produz um fechamento errado que ninguém percebe.
    """
    texto = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def converte_valor(texto: str) -> Decimal | None:
    """Aceita `1.234,56`, `1234.56`, `-1.234,56` e `R$ 1.234,56`.

    A heurística: se tem vírgula, ela é o separador decimal (padrão brasileiro) e os
    pontos são de milhar. Sem vírgula, o ponto é decimal.
    """
    limpo = re.sub(r"[^\d,.\-]", "", texto or "")
    if not limpo:
        return None
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


def monta_previa(leitura: Leitura, *, limite: int = LINHAS_DA_PREVIA) -> list[dict[str, Any]]:
    """As primeiras linhas cruas, para a tela mostrar antes do mapeamento."""
    return leitura.linhas[:limite]
