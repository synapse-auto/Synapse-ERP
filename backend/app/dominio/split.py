"""`RN-11` — integridade do split. Módulo dono da regra (Princípio III).

Dividir um lançamento (`RF-13a`) é quebrar um valor em partes com categorias
diferentes: a fatura de R$ 500,00 do provedor vira R$ 300,00 de Infraestrutura e
R$ 200,00 de Ferramentas.

Duas garantias, e a segunda é a que mais dá problema quando falta:

1. **`Σ(partes) = valor(pai)`**, comparado em `Decimal`. Diferença é recusada com o
   valor que falta ou sobra dito na mensagem — "não fecha" sem dizer quanto obriga o
   usuário a fazer a conta de cabeça.
2. **O pai deixa de contar nos totais quando tem partes.** Sem isso o mesmo dinheiro
   é somado duas vezes, uma no pai e outra nas partes, e o saldo fica com o dobro.

Por que `Decimal` e não float: `0.1 + 0.2` dá `0.30000000000000004` em ponto
flutuante. Um sistema que recusasse um split correto de dez centavos com vinte
centavos seria pior que não ter a validação.

Tarefa: T045
"""

from collections.abc import Iterable
from decimal import Decimal

from app.comum.erros import ErroRegraViolada, formata_dinheiro

MINIMO_DE_PARTES = 2


def valida_soma(valor_pai: Decimal, partes: Iterable[Decimal]) -> None:
    """Recusa o split cuja soma não fecha com o valor do lançamento-pai."""
    valores = list(partes)

    if len(valores) < MINIMO_DE_PARTES:
        raise ErroRegraViolada(
            f"Um lançamento dividido precisa de pelo menos {MINIMO_DE_PARTES} partes.",
            requisito="RN-11",
            campos={"partes": f"Informe {MINIMO_DE_PARTES} ou mais."},
        )

    if any(valor <= 0 for valor in valores):
        raise ErroRegraViolada(
            "Cada parte precisa ter valor maior que zero.",
            requisito="RN-11",
            campos={"partes": "Valor é sempre positivo; o sinal vem do tipo do lançamento."},
        )

    soma = sum(valores, Decimal("0"))
    diferenca = valor_pai - soma

    # `!= 0` em vez de comparar as strings: Decimal("200.0") e Decimal("200.00") são o
    # mesmo dinheiro com escala diferente, e recusar isso seria falso positivo.
    if diferenca != 0:
        falta = diferenca > 0
        quanto = formata_dinheiro(abs(diferenca))
        raise ErroRegraViolada(
            (
                f"A soma das partes ({formata_dinheiro(soma)}) não fecha com o valor do "
                f"lançamento ({formata_dinheiro(valor_pai)})."
            ),
            requisito="RN-11",
            campos={"partes": f"{'Faltam' if falta else 'Sobram'} {quanto}."},
        )


def valida_pode_dividir(*, e_parte_de_split: bool, tem_partes: bool) -> None:
    """Um nível só de divisão (data-model §3.10).

    A regra é entre linhas — `CHECK` não alcança outra linha —, por isso mora aqui e
    não no banco.
    """
    if e_parte_de_split:
        raise ErroRegraViolada(
            "Este lançamento já é parte de uma divisão e não pode ser dividido de novo.",
            requisito="RN-11",
            campos={"lancamento": "Divida o lançamento original, com mais partes."},
        )
    if tem_partes:
        raise ErroRegraViolada(
            "Este lançamento já está dividido.",
            requisito="RN-11",
            campos={"lancamento": "Edite as partes existentes em vez de dividir de novo."},
        )


def conta_nos_totais(*, tem_partes: bool) -> bool:
    """O lançamento-pai sai dos totais quando tem partes — senão soma em dobro."""
    return not tem_partes
