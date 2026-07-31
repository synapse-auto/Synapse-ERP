"""`RF-16`/`FR-028` — dividir um valor fechado em N parcelas.

**A soma das parcelas tem que dar exatamente o valor total.** R$ 1.000,00 em 3 não é
333,33 três vezes — isso perde um centavo e o cliente pagaria 999,99. As primeiras
parcelas levam o valor arredondado para baixo e **a última absorve a diferença**.

Por que a última e não a primeira: a primeira é a que o cliente vê na proposta e a que
costuma ir para o contrato. Uma diferença de centavos numa parcela que ninguém destacou
incomoda menos do que a parcela anunciada sair diferente do anunciado.

Diferente de `recorrencia.py` em natureza, não só em código: parcelamento é um valor
**fechado** dividido; recorrência é uma regra que gera indefinidamente (data-model
§3.14).

Tarefa: T077
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Literal

from dateutil.relativedelta import relativedelta

from app.comum.erros import ErroValidacao

Intervalo = Literal["mensal", "semanal", "quinzenal"]

INTERVALOS: tuple[str, ...] = ("mensal", "semanal", "quinzenal")

CENTAVO = Decimal("0.01")

# Teto de parcelas por parcelamento. Guarda de sanidade, não regra de negócio: 360
# parcelas mensais são 30 anos, muito além de qualquer contrato que a Synapse feche.
MAXIMO_DE_PARCELAS = 360


@dataclass(frozen=True)
class Parcela:
    numero: int
    total: int
    valor: Decimal
    data: date

    @property
    def rotulo(self) -> str:
        """ "2/3" — o que aparece na descrição e na lista (`FR-043`)."""
        return f"{self.numero}/{self.total}"


def _data_da_parcela(primeira: date, indice: int, intervalo: str) -> date:
    if intervalo == "semanal":
        return primeira + timedelta(weeks=indice)
    if intervalo == "quinzenal":
        return primeira + timedelta(days=15 * indice)
    # Mensal calculado sempre a partir da primeira, nunca encadeado a partir da
    # anterior: encadear faria o clamp de fevereiro contaminar março (mesma razão de
    # `dominio/recorrencia.py`).
    base = primeira + relativedelta(months=indice)
    return base + relativedelta(day=primeira.day)


def divide(
    *,
    valor_total: Decimal,
    total_parcelas: int,
    data_primeira: date,
    intervalo: str = "mensal",
) -> list[Parcela]:
    """As N parcelas, com a soma batendo no centavo."""
    if total_parcelas < 2:
        raise ErroValidacao(
            "Um parcelamento tem pelo menos 2 parcelas.",
            requisito="FR-028",
            campos={"total_parcelas": "Mínimo 2."},
        )
    if total_parcelas > MAXIMO_DE_PARCELAS:
        raise ErroValidacao(
            f"São {total_parcelas} parcelas, acima do máximo de {MAXIMO_DE_PARCELAS}.",
            requisito="FR-028",
            campos={"total_parcelas": f"Máximo {MAXIMO_DE_PARCELAS}."},
        )
    if intervalo not in INTERVALOS:
        raise ErroValidacao(
            f"Intervalo '{intervalo}' não existe.",
            requisito="FR-028",
            campos={"intervalo": f"Aceitos: {', '.join(INTERVALOS)}."},
        )
    if valor_total <= 0:
        raise ErroValidacao(
            "O valor total precisa ser maior que zero.",
            requisito="RN-02",
            campos={"valor_total": "Maior que zero."},
        )

    # ROUND_DOWN de propósito: arredondar para cima faria a soma das primeiras
    # ultrapassar o total e a última virar negativa em casos de centavos.
    base = (valor_total / total_parcelas).quantize(CENTAVO, rounding=ROUND_DOWN)
    if base <= 0:
        raise ErroValidacao(
            (
                f"{total_parcelas} parcelas deixariam cada uma abaixo de um centavo. "
                "Reduza o número de parcelas."
            ),
            requisito="FR-028",
            campos={"total_parcelas": "Parcelas menores que R$ 0,01."},
        )

    parcelas = [
        Parcela(
            numero=indice + 1,
            total=total_parcelas,
            valor=base,
            data=_data_da_parcela(data_primeira, indice, intervalo),
        )
        for indice in range(total_parcelas - 1)
    ]
    resto = valor_total - (base * (total_parcelas - 1))
    parcelas.append(
        Parcela(
            numero=total_parcelas,
            total=total_parcelas,
            valor=resto,
            data=_data_da_parcela(data_primeira, total_parcelas - 1, intervalo),
        )
    )

    conferencia = sum(parcela.valor for parcela in parcelas)
    if conferencia != valor_total:
        # Não deveria acontecer; se acontecer, é melhor estourar aqui do que gravar
        # um parcelamento que não fecha e descobrir no fechamento do mês.
        raise ErroValidacao(
            f"Erro ao dividir: as parcelas somam {conferencia} e o total é {valor_total}.",
            requisito="FR-028",
            campos={"valor_total": "Divisão inconsistente."},
        )
    return parcelas


def descricao_da_parcela(descricao: str, parcela: Parcela) -> str:
    """ "Projeto site institucional (2/3)" — a posição na própria descrição (`FR-043`)."""
    return f"{descricao} ({parcela.rotulo})"
