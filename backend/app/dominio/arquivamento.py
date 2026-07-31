"""`RN-06` — nunca lançamento órfão. Arquivar não é excluir.

Duas regras diferentes moram aqui porque as duas respondem à mesma pergunta ("o que
acontece com o que apontava para isto?"):

**Categoria com lançamentos** só pode ser arquivada com uma escolha explícita: mover os
lançamentos para outra categoria **ou** manter o vínculo somente-leitura. Sem escolha, a
resposta é `422` com a contagem — nunca um lançamento sem categoria.

**Cliente e funcionário nunca são excluídos**, só arquivados (constituição, "Padrões
Técnicos Obrigatórios"). Não existe `DELETE` nesses recursos em lugar nenhum da API.

## Por que "somente-leitura" é uma opção de verdade

A alternativa óbvia — obrigar a mover tudo — destruiria histórico: os lançamentos de
"Marketing" de 2025 deixariam de estar em Marketing, e o DRE daquele ano mudaria
sozinho. Manter o vínculo preserva o passado e tira a categoria dos formulários novos,
que é o que "arquivar" deveria significar.

Tarefa: T101
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.comum.erros import ErroConfirmacaoNecessaria, ErroRegraViolada


@dataclass(frozen=True)
class DestinoDoArquivamento:
    """O que fazer com os lançamentos que apontam para o que está sendo arquivado."""

    mover_para: str | None
    manter_somente_leitura: bool

    @property
    def move(self) -> bool:
        return self.mover_para is not None


def exige_destino(
    *,
    nome: str,
    quantidade_lancamentos: int,
    valor_total: Decimal,
    destino_lancamentos: str | None,
    manter_somente_leitura: bool,
) -> DestinoDoArquivamento:
    """`RN-06`/`FR-075`: sem lançamentos, arquiva direto; com eles, exige escolha."""
    if quantidade_lancamentos == 0:
        return DestinoDoArquivamento(mover_para=None, manter_somente_leitura=True)

    if destino_lancamentos and manter_somente_leitura:
        raise ErroRegraViolada(
            (
                "Escolha uma coisa só: mover os lançamentos para outra categoria "
                "**ou** manter o vínculo como está."
            ),
            requisito="RN-06",
            campos={"destino_lancamentos": "Não pode vir junto com manter_somente_leitura."},
        )

    if not destino_lancamentos and not manter_somente_leitura:
        raise ErroConfirmacaoNecessaria(
            (
                f"A categoria '{nome}' tem {quantidade_lancamentos} lançamentos. Escolha "
                "mover para outra categoria ou manter o vínculo somente-leitura."
            ),
            requisito="RN-06",
            previa={
                "quantidade_lancamentos": quantidade_lancamentos,
                "valor_total": f"{valor_total:.2f}",
                "opcoes": {
                    "destino_lancamentos": (
                        "Move os lançamentos para a categoria informada. O histórico passa "
                        "a contar na categoria nova."
                    ),
                    "manter_somente_leitura": (
                        "Os lançamentos continuam nesta categoria e ela some dos "
                        "formulários novos. Preserva o fechamento dos meses passados."
                    ),
                },
            },
            campo_confirmacao="destino_lancamentos",
        )

    return DestinoDoArquivamento(
        mover_para=destino_lancamentos, manter_somente_leitura=manter_somente_leitura
    )


def recusa_mover_para_si_mesma(*, origem: str, destino: str | None) -> None:
    if destino is not None and str(destino) == str(origem):
        raise ErroRegraViolada(
            "A categoria de destino é a própria categoria que está sendo arquivada.",
            requisito="RN-06",
            campos={"destino_lancamentos": "Escolha outra categoria."},
        )


def recusa_arquivar_especial(*, nome: str, especial: bool, vinculo: str | None) -> None:
    """Categoria especial não se arquiva pela tela de categorias.

    Ela existe porque há clientes ou funcionários cadastrados; arquivá-la deixaria
    todos eles sem onde lançar. O caminho é arquivar cliente a cliente — e aí a
    categoria fica vazia, sem nenhum efeito colateral.
    """
    if not especial:
        return
    quem = "clientes" if vinculo == "cliente" else "funcionários"
    raise ErroRegraViolada(
        (
            f"'{nome}' é a categoria de {quem} e não pode ser arquivada. Arquive os "
            f"{quem} que não estão mais ativos — a categoria fica vazia sozinha."
        ),
        requisito="RN-06",
        campos={"categoria": f"Categoria especial de {quem}."},
    )


def exige_arquivamento_em_vez_de_exclusao(recurso: str) -> None:
    """Chamado por qualquer caminho que tente excluir cliente ou funcionário.

    Não é defensivo à toa: existe para que a recusa, se acontecer, saia em PT-BR
    citando o requisito, em vez de um 404 ou de um erro de FK do Postgres.
    """
    raise ErroRegraViolada(
        f"{recurso.capitalize()} não é excluído, é arquivado — o histórico financeiro "
        "dele continua valendo.",
        requisito="RN-06",
        campos={recurso: "Use arquivar."},
    )


def resumo_do_arquivamento(
    *, ocorrencias_removidas: int, lancamentos_movidos: int = 0
) -> dict[str, Any]:
    """O que a resposta devolve depois de arquivar.

    A contagem de ocorrências futuras removidas é o *edge case* "desligado com
    lançamentos futuros programados": sem esse número, o usuário arquiva um cliente e
    não sabe que sumiram seis mensalidades da projeção.
    """
    return {
        "ocorrencias_futuras_removidas": ocorrencias_removidas,
        "lancamentos_movidos": lancamentos_movidos,
    }
