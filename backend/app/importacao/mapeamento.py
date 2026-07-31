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

Tarefa: T135
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.comum.erros import ErroValidacao
from app.importacao import csv as leitor_csv

CAMPOS_OBRIGATORIOS = ("data", "descricao", "valor")


@dataclass
class LinhaMapeada:
    indice: int
    data: date | None
    descricao: str
    valor: Decimal | None
    tipo: str | None
    categoria_texto: str | None
    categoria_id: str | None = None
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
        if categoria_texto:
            categoria_id = categorias_por_nome.get(categoria_texto.strip().lower())
            if categoria_id is None:
                problemas.append(
                    f"Categoria '{categoria_texto}' não existe. Escolha uma existente — a "
                    "importação não cria categoria."
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
        # de-para uma vez em vez de linha a linha.
        "categorias_nao_reconhecidas": sorted(
            {
                linha.categoria_texto
                for linha in mapeadas
                if linha.categoria_texto and linha.categoria_id is None
            }
        ),
    }
