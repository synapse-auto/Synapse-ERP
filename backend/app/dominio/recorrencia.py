"""`RF-15`/`RF-17a`, `RN-05a`, `RN-07` — geração de ocorrências. Só cálculo de datas.

**Nada aqui toca o banco.** A função central é `datas_das_ocorrencias`, que recebe a
regra e devolve as datas. Quem grava é `app/recorrencias/servico.py`. Essa separação é o
que torna o caso do dia 31 em fevereiro testável sem Postgres (quickstart §6).

## As três decisões que este módulo carrega

**1. Retroativa nasce `efetivado` (`RN-05a`).** Cadastrar em julho uma mensalidade que
começou em março gera cinco ocorrências passadas **já efetivadas**, mesmo com
`efetivar_automaticamente = false`. O passado já aconteceu; deixá-lo `pendente` faria o
sistema pedir confirmação de dinheiro que entrou meses atrás e mostrar o cliente como
inadimplente (`SC-004`).

**2. Dia 31 cai no último dia do mês.** "Todo dia 31" em fevereiro é 28 (ou 29). O
*clamp* é por mês, **nunca acumulado**: depois de cair em 28/02, março volta para 31 —
o combinado é o dia 31, não "o dia que deu no mês passado". `relativedelta(day=31)` do
dateutil faz exatamente isso, e é a razão de a dependência existir (Princípio II).

**3. Horizonte, não infinito.** Recorrência sem `data_fim` geraria linhas para sempre.
Materializa-se até `configuracoes.recorrencia_horizonte_meses` à frente, e a rotina
diária empurra o horizonte todo dia. `gerada_ate` é o que torna isso idempotente: gerar
é **avançar** de `gerada_ate` até o horizonte, nunca recriar (D-08).

Tarefa: T076
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from dateutil.relativedelta import relativedelta

from app.comum.erros import ErroValidacao

Frequencia = Literal["semanal", "mensal", "anual", "dias"]

FREQUENCIAS: tuple[str, ...] = ("semanal", "mensal", "anual", "dias")

ROTULOS: dict[str, str] = {
    "semanal": "Semanal",
    "mensal": "Mensal",
    "anual": "Anual",
    "dias": "A cada N dias",
}

# Teto de segurança do gerador. **Não é regra de negócio**: é o que impede um laço
# infinito virar uma função pendurada até o corte da Vercel, caso alguma combinação de
# parâmetros não avance a data. O horizonte de verdade vem de `configuracoes`.
MAXIMO_DE_OCORRENCIAS = 5_000


@dataclass(frozen=True)
class Regra:
    """A parte da recorrência que decide **quando**. Sem valor, sem categoria."""

    frequencia: Frequencia
    data_inicio: date
    dia_vencimento: int | None = None
    mes_vencimento: int | None = None
    intervalo_dias: int | None = None
    data_fim: date | None = None
    total_parcelas: int | None = None


@dataclass(frozen=True)
class Previa:
    """O que o `422` de `FR-027` mostra antes de gravar."""

    total_ocorrencias: int
    retroativas_efetivadas: int
    primeira: date | None
    ultima: date | None

    def como_dicionario(self, valor_unitario: str | None = None) -> dict[str, object]:
        return {
            "total_ocorrencias": self.total_ocorrencias,
            "retroativas_efetivadas": self.retroativas_efetivadas,
            "primeira": self.primeira.isoformat() if self.primeira else None,
            "ultima": self.ultima.isoformat() if self.ultima else None,
            "valor_total_retroativo": valor_unitario,
        }


def valida_regra(regra: Regra) -> None:
    """Recusa combinação impossível antes de qualquer cálculo.

    O banco tem `CHECK` para as mesmas coisas (migração `004`), mas o erro do Postgres
    sai em inglês e sem requisito. Aqui sai em PT-BR, com o campo apontado.
    """
    if regra.frequencia not in FREQUENCIAS:
        raise ErroValidacao(
            f"Frequência '{regra.frequencia}' não existe.",
            requisito="RF-15",
            campos={"frequencia": f"Aceitas: {', '.join(FREQUENCIAS)}."},
        )

    if regra.data_fim is not None and regra.total_parcelas is not None:
        raise ErroValidacao(
            "Escolha um jeito de terminar: uma data final **ou** um número de parcelas.",
            requisito="RF-15",
            campos={"data_fim": "Não pode vir junto com o número de parcelas."},
        )

    if regra.data_fim is not None and regra.data_fim < regra.data_inicio:
        raise ErroValidacao(
            "A data final é anterior à data de início.",
            requisito="RF-15",
            campos={"data_fim": "Precisa ser igual ou posterior ao início."},
        )

    if regra.frequencia == "dias":
        if not regra.intervalo_dias or regra.intervalo_dias <= 0:
            raise ErroValidacao(
                "Diga de quantos em quantos dias a repetição acontece.",
                requisito="RF-15",
                campos={"intervalo_dias": "Obrigatório e maior que zero."},
            )
    elif regra.intervalo_dias is not None:
        raise ErroValidacao(
            "O intervalo em dias só vale para a frequência 'a cada N dias'.",
            requisito="RF-15",
            campos={"intervalo_dias": "Deixe vazio nesta frequência."},
        )

    if regra.frequencia == "semanal" and regra.dia_vencimento is not None:
        if not 1 <= regra.dia_vencimento <= 7:
            raise ErroValidacao(
                "O dia da semana vai de 1 (segunda) a 7 (domingo).",
                requisito="RF-15",
                campos={"dia_vencimento": "Entre 1 e 7."},
            )
    elif regra.frequencia in ("mensal", "anual") and regra.dia_vencimento is not None:
        if not 1 <= regra.dia_vencimento <= 31:
            raise ErroValidacao(
                "O dia do mês vai de 1 a 31.",
                requisito="RF-15",
                campos={"dia_vencimento": "Entre 1 e 31."},
            )

    if regra.mes_vencimento is not None and regra.frequencia != "anual":
        raise ErroValidacao(
            "O mês de vencimento só vale na frequência anual.",
            requisito="RF-15",
            campos={"mes_vencimento": "Deixe vazio nesta frequência."},
        )


def _ajusta_ao_dia_do_mes(quando: date, dia: int) -> date:
    """`relativedelta(day=31)` devolve o **último dia** do mês quando 31 não existe.

    É o comportamento que se quer: "todo dia 31" em fevereiro é 28. E como o ajuste é
    aplicado sempre a partir do dia combinado, e não a partir do resultado anterior,
    março volta para 31 sozinho.
    """
    return quando + relativedelta(day=dia)


def _primeira_data(regra: Regra) -> date:
    """Onde a série começa de fato.

    `data_inicio` é a data que a pessoa escolheu. Se ela também disser "todo dia 10" e
    tiver escolhido o dia 3, a primeira ocorrência é o dia 10 **daquele mês** — o
    contrário empurraria a série um mês inteiro para frente sem ninguém pedir.
    """
    if regra.frequencia in ("mensal", "anual") and regra.dia_vencimento:
        candidata = _ajusta_ao_dia_do_mes(regra.data_inicio, regra.dia_vencimento)
        if regra.frequencia == "anual" and regra.mes_vencimento:
            candidata = candidata + relativedelta(month=regra.mes_vencimento)
            candidata = _ajusta_ao_dia_do_mes(candidata, regra.dia_vencimento)
            if candidata < regra.data_inicio:
                candidata = _ajusta_ao_dia_do_mes(
                    candidata + relativedelta(years=1), regra.dia_vencimento
                )
        return candidata

    if regra.frequencia == "semanal" and regra.dia_vencimento:
        # `isoweekday()`: 1 = segunda … 7 = domingo, a mesma convenção do campo.
        adiante = (regra.dia_vencimento - regra.data_inicio.isoweekday()) % 7
        return regra.data_inicio + timedelta(days=adiante)

    return regra.data_inicio


def _proxima(regra: Regra, atual: date, indice: int, primeira: date) -> date:
    """A ocorrência seguinte.

    Calculada **a partir da primeira** nos casos mensal/anual, não a partir da
    anterior: encadear a partir da anterior faria o clamp de fevereiro contaminar março
    ("caiu no 28, então o mês que vem é 28"), e o combinado era o dia 31.
    """
    if regra.frequencia == "dias":
        return atual + timedelta(days=regra.intervalo_dias or 1)
    if regra.frequencia == "semanal":
        return atual + timedelta(weeks=1)
    if regra.frequencia == "mensal":
        base = primeira + relativedelta(months=indice)
        return _ajusta_ao_dia_do_mes(base, regra.dia_vencimento or primeira.day)
    base = primeira + relativedelta(years=indice)
    return _ajusta_ao_dia_do_mes(base, regra.dia_vencimento or primeira.day)


def datas_das_ocorrencias(regra: Regra, *, ate: date, desde: date | None = None) -> Iterator[date]:
    """As datas da série, de `data_inicio` até `ate` (inclusive).

    `desde` serve à materialização incremental: a rotina diária passa
    `gerada_ate + 1 dia` e recebe só o que falta gerar, sem recalcular o que já existe.
    O contador de `total_parcelas` continua contando desde o começo — senão a
    recorrência de 12 parcelas geraria 12 **por execução**.
    """
    valida_regra(regra)

    primeira = _primeira_data(regra)
    atual = primeira
    indice = 0

    while atual <= ate:
        if regra.total_parcelas is not None and indice >= regra.total_parcelas:
            return
        if regra.data_fim is not None and atual > regra.data_fim:
            return
        if indice >= MAXIMO_DE_OCORRENCIAS:
            return

        if desde is None or atual >= desde:
            yield atual

        indice += 1
        seguinte = _proxima(regra, atual, indice, primeira)
        if seguinte <= atual:
            # Defesa: qualquer combinação que não avance viraria laço infinito, e um
            # laço infinito numa função serverless é um timeout sem mensagem.
            return
        atual = seguinte


def nasce_efetivada(quando: date, *, hoje: date | None = None) -> bool:
    """`RN-05a`: ocorrência de data passada ou de hoje nasce `efetivado`.

    **Independe de `efetivar_automaticamente`** — é o ponto todo da regra. Ver o
    cabeçalho do módulo.
    """
    return quando <= (hoje or date.today())


def horizonte(hoje: date, meses: int) -> date:
    """Até onde materializar. `configuracoes.recorrencia_horizonte_meses` (padrão 12)."""
    return hoje + relativedelta(months=meses)


def monta_previa(regra: Regra, *, ate: date, hoje: date | None = None) -> Previa:
    """Conta o que seria gerado, sem gerar. Alimenta `FR-027` e `POST /previa`."""
    hoje = hoje or date.today()
    datas = list(datas_das_ocorrencias(regra, ate=ate))
    retroativas = [quando for quando in datas if nasce_efetivada(quando, hoje=hoje)]
    return Previa(
        total_ocorrencias=len(datas),
        retroativas_efetivadas=len(retroativas),
        primeira=datas[0] if datas else None,
        ultima=datas[-1] if datas else None,
    )


def datas_que_o_escopo_alcanca(
    datas: list[date], *, escopo: str, hoje: date | None = None
) -> list[date]:
    """`RN-07`: `esta_e_futuras` **nunca** alcança ocorrência passada.

    Vive aqui, e não na rota, porque é a mesma regra usada ao editar a série, ao
    desativar e ao arquivar cliente/funcionário — três caminhos que precisam concordar.
    """
    hoje = hoje or date.today()
    if escopo == "apenas_esta":
        return datas
    return [quando for quando in datas if quando >= hoje]
