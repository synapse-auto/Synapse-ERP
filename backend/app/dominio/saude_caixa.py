"""`RF-46b` / `FR-069` — o semáforo de saúde do caixa. Módulo dono da regra.

A pergunta que o card responde: **o dinheiro que tenho cobre as contas fixas que já
estão marcadas para os próximos dias?**

    cobertura = saldo ÷ despesas fixas do horizonte

- `cobertura >= folga`   → **verde**
- `cobertura >= minimo`  → **amarelo**
- abaixo disso           → **vermelho**

**Os multiplicadores e o horizonte vêm de `configuracoes`**, nunca do código — é
literalmente o exemplo que o Princípio VII dá. Trocar "folga é 1,5×" por "folga é 2×" é
um `UPDATE`, não um deploy, porque o que conta como folga muda com o momento da empresa.

## Duas decisões que o número esconde

**Despesa fixa é a que já está lançada no futuro**, não uma média histórica. O sistema
sabe o que vem porque as recorrências já foram materializadas (D-08); estimar por média
daria um número que não corresponde a nenhuma conta real e que ninguém conseguiria
conferir.

**Sem despesa fixa nenhuma, a cobertura é indefinida — não infinita.** Dividir por zero
e mostrar "∞× de cobertura" seria matematicamente cômodo e enganoso: não há cobertura
nenhuma sendo demonstrada, só ausência de contas cadastradas. O semáforo fica verde e a
explicação diz exatamente isso.

Tarefa: T088
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Semaforo = Literal["verde", "amarelo", "vermelho"]

PADRAO_MULTIPLICADORES: dict[str, float] = {"minimo": 1.0, "folga": 1.5}
PADRAO_HORIZONTE_DIAS = 30


@dataclass(frozen=True)
class SaudeDoCaixa:
    semaforo: Semaforo
    cobertura: Decimal | None
    saldo: Decimal
    despesas_fixas_horizonte: Decimal
    horizonte_dias: int
    multiplicadores: dict[str, float]
    explicacao: str

    def como_dicionario(self) -> dict[str, object]:
        return {
            "semaforo": self.semaforo,
            # `null` explícito quando não há como calcular — melhor que um número
            # inventado (contracts/README.md §Ausência).
            "cobertura": None if self.cobertura is None else f"{self.cobertura:.2f}",
            "saldo": f"{self.saldo:.2f}",
            "despesas_fixas_horizonte": f"{self.despesas_fixas_horizonte:.2f}",
            "horizonte_dias": self.horizonte_dias,
            "multiplicadores": self.multiplicadores,
            "explicacao": self.explicacao,
        }


def _virgula(valor: Decimal) -> str:
    """`1.83` → `"1,8"`. A explicação é texto de tela, então vai em PT-BR (`RNF-03`)."""
    return f"{valor:.1f}".replace(".", ",")


def avalia(
    *,
    saldo: Decimal,
    despesas_fixas_horizonte: Decimal,
    horizonte_dias: int = PADRAO_HORIZONTE_DIAS,
    multiplicadores: dict[str, float] | None = None,
) -> SaudeDoCaixa:
    """Calcula o semáforo e a frase que o acompanha.

    A `explicacao` é montada aqui, no servidor, e não na tela: ela cita números que só
    o cálculo conhece, e `RNF-02` proíbe o frontend montar texto de regra de negócio.
    """
    multiplicadores = multiplicadores or dict(PADRAO_MULTIPLICADORES)
    minimo = Decimal(str(multiplicadores.get("minimo", 1.0)))
    folga = Decimal(str(multiplicadores.get("folga", 1.5)))

    if despesas_fixas_horizonte <= 0:
        return SaudeDoCaixa(
            semaforo="verde",
            cobertura=None,
            saldo=saldo,
            despesas_fixas_horizonte=Decimal("0.00"),
            horizonte_dias=horizonte_dias,
            multiplicadores=multiplicadores,
            explicacao=(
                f"Não há despesa fixa lançada para os próximos {horizonte_dias} dias, "
                "então não há o que cobrir."
            ),
        )

    if saldo <= 0:
        return SaudeDoCaixa(
            semaforo="vermelho",
            cobertura=Decimal("0.00"),
            saldo=saldo,
            despesas_fixas_horizonte=despesas_fixas_horizonte,
            horizonte_dias=horizonte_dias,
            multiplicadores=multiplicadores,
            explicacao=(
                f"O saldo não cobre nenhuma das despesas fixas dos próximos "
                f"{horizonte_dias} dias."
            ),
        )

    cobertura = (saldo / despesas_fixas_horizonte).quantize(Decimal("0.01"))

    if cobertura >= folga:
        semaforo: Semaforo = "verde"
    elif cobertura >= minimo:
        semaforo = "amarelo"
    else:
        semaforo = "vermelho"

    if semaforo == "verde":
        explicacao = (
            f"O saldo cobre {_virgula(cobertura)}× as despesas fixas dos próximos "
            f"{horizonte_dias} dias."
        )
    elif semaforo == "amarelo":
        explicacao = (
            f"O saldo cobre {_virgula(cobertura)}× as despesas fixas dos próximos "
            f"{horizonte_dias} dias — dá para pagar, mas sem folga."
        )
    else:
        explicacao = (
            f"O saldo cobre só {_virgula(cobertura)}× as despesas fixas dos próximos "
            f"{horizonte_dias} dias. Falta caixa para as contas já marcadas."
        )

    return SaudeDoCaixa(
        semaforo=semaforo,
        cobertura=cobertura,
        saldo=saldo,
        despesas_fixas_horizonte=despesas_fixas_horizonte,
        horizonte_dias=horizonte_dias,
        multiplicadores=multiplicadores,
        explicacao=explicacao,
    )
