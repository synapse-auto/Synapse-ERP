"""Paginação no servidor — contracts/README.md §Paginação, `RNF-07`.

    ?pagina=1&por_pagina=50&ordenar=data&direcao=desc

    { "itens": [...],
      "paginacao": { "pagina": 1, "por_pagina": 50, "total": 0, "total_paginas": 0 } }

Paginação no servidor, não virtualização no cliente: a constituição aceita as duas,
mas carregar milhares de lançamentos para o navegador filtrar contraria `RNF-07` de
qualquer jeito, e a soma do conjunto filtrado (`FR-038`) precisa vir do banco —
somar só a página visível daria número errado.

**`ordenar` nunca entra em SQL por concatenação.** Cada endpoint declara as colunas
que aceita, e o valor recebido é conferido contra essa lista. Coluna fora da lista é
`400 validacao`, não texto interpolado numa query.

Tarefa: T026
"""

from dataclasses import dataclass
from math import ceil
from typing import Any, Literal

from fastapi import Query

from app.comum.erros import ErroValidacao

POR_PAGINA_PADRAO = 50
POR_PAGINA_MINIMO = 1
POR_PAGINA_MAXIMO = 200

Direcao = Literal["asc", "desc"]


@dataclass(frozen=True)
class Paginacao:
    """Parâmetros de paginação já validados."""

    pagina: int
    por_pagina: int
    ordenar: str | None
    direcao: Direcao

    @property
    def deslocamento(self) -> int:
        return (self.pagina - 1) * self.por_pagina

    def coluna_de_ordenacao(self, permitidas: dict[str, str], padrao: str) -> str:
        """Traduz `ordenar` em nome de coluna, conferindo contra a lista do endpoint.

        `permitidas` mapeia o nome público (o que o cliente manda) para a expressão
        SQL — os dois não são iguais quando a ordenação é por coluna de outra tabela
        (ordenar por `categoria` é ordenar por `categorias.nome`).
        """
        if self.ordenar is None:
            return padrao
        coluna = permitidas.get(self.ordenar)
        if coluna is None:
            aceitas = ", ".join(sorted(permitidas))
            raise ErroValidacao(
                f"Não é possível ordenar por '{self.ordenar}'.",
                campos={"ordenar": f"Valores aceitos: {aceitas}."},
            )
        return coluna

    def clausula_ordem(self, permitidas: dict[str, str], padrao: str) -> str:
        """`ORDER BY` pronto. A direção é literal, nunca vem do cliente como texto."""
        coluna = self.coluna_de_ordenacao(permitidas, padrao)
        return f"{coluna} {'asc' if self.direcao == 'asc' else 'desc'}"


def parametros_de_paginacao(
    pagina: int = Query(default=1, ge=1, description="Página, começando em 1."),
    por_pagina: int = Query(
        default=POR_PAGINA_PADRAO,
        ge=POR_PAGINA_MINIMO,
        le=POR_PAGINA_MAXIMO,
        description=f"Itens por página ({POR_PAGINA_MINIMO}–{POR_PAGINA_MAXIMO}).",
    ),
    ordenar: str | None = Query(default=None, description="Campo de ordenação."),
    direcao: Direcao = Query(default="desc", description="asc ou desc."),
) -> Paginacao:
    """Dependência do FastAPI. Entra na assinatura de todo endpoint de lista."""
    return Paginacao(pagina=pagina, por_pagina=por_pagina, ordenar=ordenar, direcao=direcao)


def envelope(itens: list[Any], *, total: int, paginacao: Paginacao) -> dict[str, Any]:
    """Monta a resposta paginada do contrato."""
    return {
        "itens": itens,
        "paginacao": {
            "pagina": paginacao.pagina,
            "por_pagina": paginacao.por_pagina,
            "total": total,
            "total_paginas": ceil(total / paginacao.por_pagina) if total else 0,
        },
    }
