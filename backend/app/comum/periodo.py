"""Resolução de período e do período de comparação — contracts/README.md §Período.

Atalhos aceitos: `hoje`, `esta_semana`, `este_mes`, `mes_passado`,
`ultimos_3_meses`, `este_ano`, `personalizado` (com `data_inicio` e `data_fim`).

**Por que a resolução é do servidor e não do frontend**: o comparativo de `FR-055`
tem que usar exatamente a mesma régua do período principal. Se cada lado calculasse
por conta, um "-12% em relação ao mês anterior" poderia estar comparando 30 dias
contra 31 sem ninguém notar.

## A régua do período anterior

Depende de o período estar aberto ou fechado, e as duas metades da regra existem por
um motivo concreto.

**Período fechado** (`mes_passado`, ou `este_mes` no último dia do mês): o dado está
completo, então compara **cheio contra cheio**. Junho tem 30 dias e maio 31; se o
anterior fosse cortado em 30/05 para "igualar os dias", o DRE de maio e o "mês
anterior" do card mostrariam números diferentes para o mesmo maio — e quem confere
fechamento à mão (`SC-003`) encontraria uma diferença que não existe.

**Período aberto** (`este_mes` no dia 3, `este_ano` em julho): só parte aconteceu, e
aí o anterior **encolhe para o mesmo número de dias decorridos**. Sem isso, 3 dias de
agosto contra 31 dias de julho apareceria como "queda de 90%" sem queda nenhuma.

Em código: `decorrido_ate = min(fim, hoje)`; se `decorrido_ate >= fim` o período
anterior vai até o próprio fim dele, senão vai até
`inicio_anterior + (decorrido_ate - inicio)`.

**Semana começa na segunda** (ISO 8601). É o que `chave_deduplicacao` já usa em
`resumo_semanal:{aaaa-Www}` (data-model §3.16); duas convenções de semana no mesmo
sistema geraria resumo semanal e filtro "esta semana" cobrindo dias diferentes.

Tarefa: T027
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from dateutil.relativedelta import relativedelta

from app.comum.erros import ErroValidacao

AtalhoPeriodo = Literal[
    "hoje",
    "esta_semana",
    "este_mes",
    "mes_passado",
    "ultimos_3_meses",
    "este_ano",
    "personalizado",
]

ATALHOS: tuple[str, ...] = (
    "hoje",
    "esta_semana",
    "este_mes",
    "mes_passado",
    "ultimos_3_meses",
    "este_ano",
    "personalizado",
)

# Rótulo em PT-BR para as mensagens e para o resumo em linguagem natural (FR-070).
ROTULOS: dict[str, str] = {
    "hoje": "hoje",
    "esta_semana": "esta semana",
    "este_mes": "este mês",
    "mes_passado": "mês passado",
    "ultimos_3_meses": "últimos 3 meses",
    "este_ano": "este ano",
    "personalizado": "período personalizado",
}


def _ultimo_dia_do_mes(referencia: date) -> date:
    return referencia + relativedelta(day=31)


@dataclass(frozen=True)
class Periodo:
    """Um período resolvido, com o período de comparação já calculado."""

    atalho: str
    inicio: date
    fim: date
    inicio_anterior: date
    fim_anterior: date
    decorrido_ate: date

    @property
    def rotulo(self) -> str:
        return ROTULOS.get(self.atalho, self.atalho)

    @property
    def dias(self) -> int:
        return (self.fim - self.inicio).days + 1

    @property
    def dias_decorridos(self) -> int:
        return (self.decorrido_ate - self.inicio).days + 1

    @property
    def esta_aberto(self) -> bool:
        """O período ainda não terminou — parte dele é futuro."""
        return self.decorrido_ate < self.fim

    def como_dicionario(self) -> dict[str, str | int | bool]:
        """Vai na resposta junto do dado, para a tela dizer o que está comparando."""
        return {
            "atalho": self.atalho,
            "rotulo": self.rotulo,
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat(),
            "inicio_anterior": self.inicio_anterior.isoformat(),
            "fim_anterior": self.fim_anterior.isoformat(),
            "dias": self.dias,
            "dias_decorridos": self.dias_decorridos,
            "esta_aberto": self.esta_aberto,
        }


def _limites(atalho: str, hoje: date, inicio: date | None, fim: date | None) -> tuple[date, date]:
    """Calendário do período — sem olhar o anterior ainda."""
    if atalho == "hoje":
        return hoje, hoje
    if atalho == "esta_semana":
        segunda = hoje - timedelta(days=hoje.weekday())
        return segunda, segunda + timedelta(days=6)
    if atalho == "este_mes":
        return hoje.replace(day=1), _ultimo_dia_do_mes(hoje)
    if atalho == "mes_passado":
        mes_passado = hoje - relativedelta(months=1)
        return mes_passado.replace(day=1), _ultimo_dia_do_mes(mes_passado)
    if atalho == "ultimos_3_meses":
        # 3 meses inteiros terminando no mês corrente, inclusive.
        return (hoje - relativedelta(months=2)).replace(day=1), _ultimo_dia_do_mes(hoje)
    if atalho == "este_ano":
        return date(hoje.year, 1, 1), date(hoje.year, 12, 31)

    # personalizado
    if inicio is None or fim is None:
        raise ErroValidacao(
            "Informe a data de início e a data de fim do período.",
            campos={
                "data_inicio": "Obrigatória quando periodo=personalizado.",
                "data_fim": "Obrigatória quando periodo=personalizado.",
            },
        )
    if fim < inicio:
        raise ErroValidacao(
            "A data de fim não pode ser anterior à data de início.",
            campos={"data_fim": "Deve ser igual ou posterior à data de início."},
        )
    return inicio, fim


def _inicio_do_anterior(atalho: str, inicio: date, fim: date) -> date:
    """Onde começa o período de comparação.

    Para os atalhos de calendário, recua uma unidade de calendário — assim
    "este mês" compara contra o mês anterior de verdade, e não contra "os 31 dias
    antes de hoje", que atravessaria dois meses.
    """
    if atalho == "hoje":
        return inicio - timedelta(days=1)
    if atalho == "esta_semana":
        return inicio - timedelta(days=7)
    if atalho in ("este_mes", "mes_passado"):
        return inicio - relativedelta(months=1)
    if atalho == "ultimos_3_meses":
        return inicio - relativedelta(months=3)
    if atalho == "este_ano":
        return inicio - relativedelta(years=1)
    # personalizado: o mesmo número de dias, imediatamente antes
    return inicio - timedelta(days=(fim - inicio).days + 1)


def _fim_do_anterior(atalho: str, inicio: date, fim: date, inicio_anterior: date) -> date:
    """Limite do período de comparação — ver "A régua do período anterior" no topo."""
    if atalho == "hoje":
        return inicio_anterior
    if atalho == "esta_semana":
        return inicio_anterior + timedelta(days=6)
    if atalho in ("este_mes", "mes_passado"):
        return _ultimo_dia_do_mes(inicio_anterior)
    if atalho == "ultimos_3_meses":
        return _ultimo_dia_do_mes(inicio_anterior + relativedelta(months=2))
    if atalho == "este_ano":
        return date(inicio_anterior.year, 12, 31)
    return inicio_anterior + timedelta(days=(fim - inicio).days)


def resolve(
    atalho: str | None = None,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    hoje: date | None = None,
) -> Periodo:
    """Resolve o atalho em `(inicio, fim, inicio_anterior, fim_anterior)`.

    `hoje` é injetável para que os testes não dependam da data do relógio — sem
    isso, um teste de "este_mes" passaria em julho e falharia em fevereiro.
    """
    hoje = hoje or date.today()
    atalho = atalho or "este_mes"

    if atalho not in ATALHOS:
        raise ErroValidacao(
            f"Período '{atalho}' não existe.",
            campos={"periodo": f"Valores aceitos: {', '.join(ATALHOS)}."},
        )

    inicio, fim = _limites(atalho, hoje, data_inicio, data_fim)
    inicio_anterior = _inicio_do_anterior(atalho, inicio, fim)
    limite_do_anterior = _fim_do_anterior(atalho, inicio, fim, inicio_anterior)

    decorrido_ate = min(fim, hoje) if hoje >= inicio else inicio

    if decorrido_ate >= fim:
        # Período FECHADO — o dado dele está completo. Compara cheio contra cheio,
        # senão o comparativo não bate com o relatório do mesmo período: junho tem 30
        # dias e maio 31, e cortar 31/05 faria o DRE de maio e o "mês anterior" do
        # card mostrarem números diferentes para o mesmo mês.
        fim_anterior = limite_do_anterior
    else:
        # Período ABERTO — só parte dele aconteceu. Aí sim o anterior encolhe para o
        # mesmo número de dias decorridos, senão 3 dias de agosto contra 31 de julho
        # apareceria como "queda de 90%" sem queda nenhuma.
        fim_anterior = min(
            inicio_anterior + timedelta(days=(decorrido_ate - inicio).days),
            limite_do_anterior,
        )

    return Periodo(
        atalho=atalho,
        inicio=inicio,
        fim=fim,
        inicio_anterior=inicio_anterior,
        fim_anterior=fim_anterior,
        decorrido_ate=decorrido_ate,
    )
