"""`RN-10` / `FR-115` — inadimplência. **Situação derivada, nunca gravada.**

Não existe coluna `situacao` em `clientes`. A situação é calculada toda vez que alguém
pergunta, a partir dos lançamentos em aberto.

## Por que derivada e não gravada

Se fosse coluna, mudar `configuracoes.inadimplencia_dias_tolerancia` de 3 para 5 exigiria
varrer a base e reescrever a situação de todo mundo — e até a varredura terminar, a tela
mostraria o critério antigo. Derivada, a mudança da tolerância **reavalia todo mundo na
hora**, que é o que `FR-105` pede.

## A dependência que parece detalhe e não é

**Só conta como atrasado o lançamento com `efetivar_automaticamente = false`** (D-05). O
lançamento automático se efetiva na data e nunca chega a `atrasado` (`RN-03`) — então
uma mensalidade marcada como automática **nunca** vai gerar alerta de inadimplência, por
mais que o cliente não pague. O checkbox desligado é o que liga a cobrança.

Isso está aqui, escrito, porque é a pergunta que alguém vai fazer olhando um cliente
devedor que não aparece na lista: o problema não é este módulo, é a recorrência dele
estar com efetivação automática.

Tarefa: T100
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

Situacao = Literal["em_dia", "atrasado"]

PADRAO_DIAS_TOLERANCIA = 3

# Os status que representam dinheiro esperado e não recebido. `programado` fica de fora:
# ainda não venceu, não há nada a cobrar.
STATUS_EM_ATRASO: frozenset[str] = frozenset({"pendente", "atrasado"})


@dataclass(frozen=True)
class SituacaoDoCliente:
    situacao: Situacao
    dias_atraso: int
    valor_atrasado: Decimal
    quantidade: int
    tolerancia_dias: int

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "situacao": self.situacao,
            # `null` quando não há atraso — `0` diria "atrasou zero dias", que é outra
            # coisa (contracts/README.md §Ausência).
            "dias_atraso": self.dias_atraso or None,
            "valor_atrasado": f"{self.valor_atrasado:.2f}",
            "quantidade_em_atraso": self.quantidade,
            "tolerancia_dias": self.tolerancia_dias,
        }


def avalia(
    lancamentos_em_aberto: list[dict[str, Any]],
    *,
    tolerancia_dias: int = PADRAO_DIAS_TOLERANCIA,
    hoje: date | None = None,
) -> SituacaoDoCliente:
    """Situação a partir dos lançamentos em aberto do cliente.

    Cada lançamento precisa trazer `data`, `valor`, `status` e
    `efetivar_automaticamente`. O módulo não consulta o banco de propósito — assim a
    regra é testável sem Postgres e a mesma função serve à lista, ao perfil, ao
    Dashboard e ao alerta da rotina (Princípio III).
    """
    hoje = hoje or date.today()

    vencidos = [
        item
        for item in lancamentos_em_aberto
        if item["status"] in STATUS_EM_ATRASO
        # D-05: sem isto, cliente com mensalidade automática apareceria como
        # inadimplente por um lançamento que o sistema vai efetivar sozinho.
        and not item["efetivar_automaticamente"] and (hoje - item["data"]).days > tolerancia_dias
    ]

    if not vencidos:
        return SituacaoDoCliente(
            situacao="em_dia",
            dias_atraso=0,
            valor_atrasado=Decimal("0.00"),
            quantidade=0,
            tolerancia_dias=tolerancia_dias,
        )

    # O atraso relatado é o do **mais antigo**: é o que descreve a gravidade. Usar a
    # média suavizaria justamente o caso que importa.
    mais_antigo = min(item["data"] for item in vencidos)
    return SituacaoDoCliente(
        situacao="atrasado",
        dias_atraso=(hoje - mais_antigo).days,
        valor_atrasado=sum((Decimal(str(item["valor"])) for item in vencidos), Decimal("0.00")),
        quantidade=len(vencidos),
        tolerancia_dias=tolerancia_dias,
    )


def pode_ficar_inadimplente(*, efetivar_automaticamente: bool) -> bool:
    """A cobrança deste lançamento chega a existir? (D-05)

    Função nomeada porque é a pergunta que a tela precisa fazer para **explicar** ao
    usuário por que um cliente devedor não aparece na lista — em vez de o usuário
    concluir que o sistema está errado.
    """
    return not efetivar_automaticamente
