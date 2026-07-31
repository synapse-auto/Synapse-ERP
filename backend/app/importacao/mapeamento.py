"""Mapeamento coluna → campo e validação da prévia — `FR-044`.

O que este módulo garante, e é o ponto todo da importação em duas etapas: **nenhuma
linha é gravada antes de o usuário ver o que vai acontecer com ela**.

Cada linha do arquivo vira uma `LinhaMapeada` com o que foi entendido e o que deu
problema. A tela mostra as duas coisas juntas; o `confirmar` só grava as válidas — e
recusa a chamada inteira se houver inválida sem o usuário ter mandado ignorar.

## `mundo` é escolhido, não deduzido

O arquivo não traz mundo e `RN-15` não admite nulo. Então o mundo vem no mapeamento e
vale para o arquivo inteiro. Deduzir por palavra-chave da descrição seria adivinhação
sobre dado financeiro.

## Categoria não reconhecida não vira categoria nova

Ela é apontada na prévia com a lista do que existe. Criar sozinho encheria a base de
"Alimentação", "alimentacao" e "ALIMENTAÇÃO" em três meses.

## A sugestão de categoria (`FR-044`) **sugere, não aplica**

`FR-044` e o contrato pedem sugestão de categoria, e por um tempo isto aqui só fazia
casamento exato de nome: "Ferramentas" batia, "Ferramenta" caía como não reconhecida
sem nenhuma pista do que o usuário deveria escolher.

Agora cada texto não reconhecido ganha a categoria existente mais parecida, por
similaridade de string. Duas decisões que valem ser ditas:

1. **A sugestão nunca é aplicada sozinha.** Ela vai na prévia para o usuário aceitar.
   Adivinhar categoria de lançamento financeiro e gravar é pior que recusar — o erro
   fica invisível e contamina DRE, relatório por categoria e o card do Dashboard.
2. **A comparação é em Python, sem tocar o banco.** `pg_trgm` faria o mesmo, mas
   custaria uma consulta por linha do arquivo e tiraria a testabilidade sem Postgres
   que este módulo tem de propósito. São dezenas de categorias contra centenas de
   linhas — cabe na memória com folga.

Tarefa: T135
"""

import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from app.comum.erros import ErroValidacao
from app.importacao import csv as leitor_csv

CAMPOS_OBRIGATORIOS = ("data", "descricao", "valor")

# Abaixo disto a "sugestão" viraria chute. 0.6 aceita erro de acento, plural e uma
# palavra a mais ("Ferramentas de TI" → "Ferramentas/Assinaturas") e recusa duas
# palavras sem parentesco.
SIMILARIDADE_MINIMA = 0.6


def _normaliza(texto: str) -> str:
    """Minúsculas sem acento — "Alimentação" e "alimentacao" são a mesma palavra."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).strip().lower()


def sugere_categoria(
    texto: str, categorias_por_nome: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    """Categoria existente mais parecida com `texto`, ou `None` se nada chega perto.

    Devolve `(id, nome original)` — o nome porque é o que a tela mostra ao perguntar
    "você quis dizer …?", e com a grafia do cadastro.
    """
    alvo = _normaliza(texto)
    if not alvo:
        return None

    melhor: tuple[float, str, str] | None = None
    for chave, (identificador, nome) in categorias_por_nome.items():
        pontuacao = SequenceMatcher(None, alvo, _normaliza(chave)).ratio()
        if pontuacao >= SIMILARIDADE_MINIMA and (melhor is None or pontuacao > melhor[0]):
            melhor = (pontuacao, identificador, nome)

    return (melhor[1], melhor[2]) if melhor else None


@dataclass
class LinhaMapeada:
    indice: int
    data: date | None
    descricao: str
    valor: Decimal | None
    tipo: str | None
    categoria_texto: str | None
    categoria_id: str | None = None
    # `FR-044`: preenchidos só quando o nome não bateu exato. Ficam na prévia para o
    # usuário aceitar; o `confirmar` nunca os aplica sozinho.
    categoria_sugerida_id: str | None = None
    categoria_sugerida_nome: str | None = None
    problemas: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.problemas

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "indice": self.indice,
            "data": self.data.isoformat() if self.data else None,
            "descricao": self.descricao,
            "valor": f"{abs(self.valor):.2f}" if self.valor is not None else None,
            "tipo": self.tipo,
            "categoria_texto": self.categoria_texto,
            "categoria_id": self.categoria_id,
            "categoria_sugerida_id": self.categoria_sugerida_id,
            "categoria_sugerida_nome": self.categoria_sugerida_nome,
            "valida": self.valida,
            "problemas": self.problemas,
        }


def valida_mapeamento(mapa: dict[str, str], colunas: list[str]) -> None:
    faltando = [campo for campo in CAMPOS_OBRIGATORIOS if not mapa.get(campo)]
    if faltando:
        raise ErroValidacao(
            f"Falta dizer qual coluna é {', '.join(faltando)}.",
            requisito="FR-044",
            campos={campo: "Escolha a coluna correspondente." for campo in faltando},
        )

    desconhecidas = [coluna for coluna in mapa.values() if coluna and coluna not in colunas]
    if desconhecidas:
        raise ErroValidacao(
            f"Coluna inexistente no arquivo: {', '.join(desconhecidas)}.",
            requisito="FR-044",
            campos={"mapeamento": f"Colunas do arquivo: {', '.join(colunas)}."},
        )


def mapeia(
    linhas: list[dict[str, str]],
    *,
    mapa: dict[str, str],
    categorias_por_nome: dict[str, str],
    tipo_padrao: str | None = None,
) -> list[LinhaMapeada]:
    """Traduz as linhas cruas e **acumula os problemas em vez de parar no primeiro**.

    Parar no primeiro erro faria o usuário corrigir uma linha, reenviar o arquivo e
    descobrir a próxima — dez vezes seguidas.
    """
    mapeadas: list[LinhaMapeada] = []

    for indice, linha in enumerate(linhas):
        bruto_data = linha.get(mapa["data"], "")
        bruto_valor = linha.get(mapa["valor"], "")
        descricao = (linha.get(mapa["descricao"], "") or "").strip()

        quando = leitor_csv.converte_data(bruto_data)
        valor = leitor_csv.converte_valor(bruto_valor)

        problemas: list[str] = []
        if quando is None:
            problemas.append(f"Data não reconhecida: '{bruto_data}'. Use dd/mm/aaaa.")
        if valor is None:
            problemas.append(f"Valor não reconhecido: '{bruto_valor}'.")
        elif valor == 0:
            problemas.append("Valor zero não é lançamento.")
        if not descricao:
            problemas.append("Descrição vazia.")

        # `RN-02`: o valor é sempre positivo e o sinal vira `tipo`. O sinal do extrato é
        # justamente o que diz se foi entrada ou saída.
        tipo = tipo_padrao
        if tipo is None and valor is not None:
            tipo = "despesa" if valor < 0 else "receita"

        categoria_texto = (linha.get(mapa.get("categoria", ""), "") or "").strip() or None
        categoria_id = None
        sugerida_id = sugerida_nome = None
        if categoria_texto:
            achado = categorias_por_nome.get(categoria_texto.strip().lower())
            categoria_id = achado[0] if achado else None
            if categoria_id is None:
                sugestao = sugere_categoria(categoria_texto, categorias_por_nome)
                if sugestao:
                    sugerida_id, sugerida_nome = sugestao
                problemas.append(
                    f"Categoria '{categoria_texto}' não existe. Escolha uma existente — a "
                    "importação não cria categoria."
                    + (f" Parecida: '{sugerida_nome}'." if sugerida_nome else "")
                )
        elif mapa.get("categoria"):
            problemas.append("Sem categoria nesta linha.")

        mapeadas.append(
            LinhaMapeada(
                indice=indice,
                data=quando,
                descricao=descricao,
                valor=valor,
                tipo=tipo,
                categoria_texto=categoria_texto,
                categoria_id=categoria_id,
                categoria_sugerida_id=sugerida_id,
                categoria_sugerida_nome=sugerida_nome,
                problemas=problemas,
            )
        )

    return mapeadas


def resumo(mapeadas: list[LinhaMapeada]) -> dict[str, Any]:
    validas = [linha for linha in mapeadas if linha.valida]
    invalidas = [linha for linha in mapeadas if not linha.valida]

    receitas = sum(
        (abs(linha.valor) for linha in validas if linha.tipo == "receita" and linha.valor),
        Decimal("0"),
    )
    despesas = sum(
        (abs(linha.valor) for linha in validas if linha.tipo == "despesa" and linha.valor),
        Decimal("0"),
    )
    datas = [linha.data for linha in validas if linha.data]

    return {
        "total": len(mapeadas),
        "validas": len(validas),
        "invalidas": len(invalidas),
        "total_receitas": f"{receitas:.2f}",
        "total_despesas": f"{despesas:.2f}",
        "primeira_data": min(datas).isoformat() if datas else None,
        "ultima_data": max(datas).isoformat() if datas else None,
        # As categorias que faltam, agrupadas: é o que a tela precisa para oferecer o
        # de-para uma vez em vez de linha a linha. Cada uma vem com a sugestão
        # (`FR-044`) — `sugestao_id` nulo quando nada no cadastro chega perto.
        "categorias_nao_reconhecidas": [
            {"texto": texto, "sugestao_id": sugestao[0], "sugestao_nome": sugestao[1]}
            for texto, sugestao in sorted(
                {
                    linha.categoria_texto: (
                        linha.categoria_sugerida_id,
                        linha.categoria_sugerida_nome,
                    )
                    for linha in mapeadas
                    if linha.categoria_texto and linha.categoria_id is None
                }.items()
            )
        ],
    }
