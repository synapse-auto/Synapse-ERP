"""`RN-03` / `RN-04` — o ciclo de status. Módulo dono da regra (Princípio III).

```
                      ┌──────────────┐
       criado com     │  programado  │  data futura
       data futura →  └──────┬───────┘
                             │ chega a data
              ┌──────────────┴──────────────┐
   efetivar_auto = true          efetivar_auto = false
              │                              │
              ▼                              ▼
       ┌─────────────┐              ┌──────────────┐
       │  efetivado  │◄─────────────│   pendente   │
       └─────────────┘  1 clique    └──────┬───────┘
              ▲                            │ passa do vencimento
              │                            ▼
              │  1 clique          ┌──────────────┐
              └────────────────────│   atrasado   │
                                   └──────────────┘
```

## As duas consequências que mais confundem

**`atrasado` só existe com `efetivar_automaticamente = false`** (D-05). O lançamento
automático se efetiva na própria data e nunca vence. Isso não é detalhe de
implementação: o alerta de inadimplência (`RN-10`) depende de o lançamento poder ficar
`atrasado`, então o checkbox desligado é o que **liga** a cobrança do cliente.

**`cancelado` preserva o histórico.** Sai dos totais, a linha continua existindo e
visível. É diferente de excluído (`RN-08`, lixeira), que some da lista.

## Por que `pendente` e `atrasado` não são ação de usuário

As duas transições acontecem **na data**, sozinhas, dentro da rotina diária. O usuário
só tem dois botões: efetivar e cancelar. Por isso `TRANSICOES_MANUAIS` é separada de
`TRANSICOES_DA_ROTINA` — misturar as duas deixaria a API aceitar "marcar como
atrasado", que é estado que se descobre, não que se declara.

Tarefa: T075
"""

from datetime import date
from typing import Literal

from app.comum.erros import ErroConfirmacaoNecessaria, ErroRegraViolada

Status = Literal["programado", "pendente", "efetivado", "atrasado", "cancelado"]

STATUS: tuple[str, ...] = ("programado", "pendente", "efetivado", "atrasado", "cancelado")

# Só `efetivado` entra no realizado (`RN-05`).
CONTA_NO_REALIZADO: frozenset[str] = frozenset({"efetivado"})

# `programado` e `pendente` entram em projeção e nos cards A pagar / A receber.
# `atrasado` também: a conta vencida continua a pagar — é o que a torna urgente.
CONTA_NA_PROJECAO: frozenset[str] = frozenset({"programado", "pendente", "atrasado"})

# O que a pessoa pode pedir. Os dois botões do painel de detalhe (`FR-042`).
TRANSICOES_MANUAIS: dict[str, frozenset[str]] = {
    "programado": frozenset({"efetivado", "cancelado"}),
    "pendente": frozenset({"efetivado", "cancelado"}),
    "atrasado": frozenset({"efetivado", "cancelado"}),
    "efetivado": frozenset({"cancelado"}),
    "cancelado": frozenset(),
}

# O que a rotina diária faz sozinha, na data (`RN-04`).
TRANSICOES_DA_ROTINA: dict[str, frozenset[str]] = {
    "programado": frozenset({"efetivado", "pendente"}),
    "pendente": frozenset({"atrasado"}),
}

ROTULOS: dict[str, str] = {
    "programado": "Programado",
    "pendente": "Pendente",
    "efetivado": "Efetivado",
    "atrasado": "Atrasado",
    "cancelado": "Cancelado",
}


def status_inicial(*, data_do_lancamento: date, hoje: date | None = None) -> Status:
    """`FR-024`: passado ou hoje nasce `efetivado`; futuro nasce `programado`.

    **Independe do checkbox de propósito.** Quem lança com data de ontem está
    registrando dinheiro que já se moveu; deixar isso `pendente` faria o saldo mentir
    para menos até alguém clicar em cada linha.
    """
    hoje = hoje or date.today()
    return "efetivado" if data_do_lancamento <= hoje else "programado"


def status_na_data(
    *,
    status_atual: str,
    data_do_lancamento: date,
    efetivar_automaticamente: bool,
    hoje: date | None = None,
) -> Status | None:
    """O que a rotina diária deve gravar, ou `None` se não há nada a fazer.

    Devolver `None` em vez do próprio status é o que torna a rotina idempotente sem
    depender de contar linhas: rodar de novo no mesmo dia simplesmente não encontra
    nada para mudar (D-08).
    """
    hoje = hoje or date.today()

    if status_atual in ("efetivado", "cancelado"):
        return None  # estado final: a rotina não mexe

    if status_atual == "programado":
        if data_do_lancamento > hoje:
            return None  # ainda não chegou a data
        # `RN-04`: chegou a data. Automático vira efetivado; manual espera confirmação.
        return "efetivado" if efetivar_automaticamente else "pendente"

    if status_atual == "pendente" and data_do_lancamento < hoje:
        # `RN-03`: passou do vencimento sem confirmação. Só chega aqui quem tem
        # efetivação manual — o automático nunca esteve `pendente`.
        return "atrasado"

    return None


def pode_atrasar(*, efetivar_automaticamente: bool) -> bool:
    """`atrasado` é alcançável? Só com efetivação manual (D-05).

    Existe como função nomeada porque essa é a pergunta que a inadimplência
    (`RN-10`) e o alerta de vencimento (`FR-096`) fazem — e escrever
    `not efetivar_automaticamente` espalhado pelo código esconderia a regra.
    """
    return not efetivar_automaticamente


def exige_transicao_manual(*, de: str, para: str, descricao: str = "Este lançamento") -> None:
    """Recusa, em PT-BR, a mudança de status que o ciclo não permite."""
    if de not in TRANSICOES_MANUAIS:
        raise ErroRegraViolada(
            f"Status '{de}' não existe.", requisito="RN-03", campos={"status": "Inválido."}
        )
    if para == de:
        raise ErroRegraViolada(
            f"{descricao} já está {ROTULOS[de].lower()}.",
            requisito="RN-03",
            campos={"status": f"Já {ROTULOS[de].lower()}."},
        )
    if para not in TRANSICOES_MANUAIS[de]:
        if para in ("pendente", "atrasado"):
            raise ErroRegraViolada(
                (
                    f"'{ROTULOS.get(para, para)}' não é uma escolha: o sistema chega nesse "
                    "estado sozinho, na data do vencimento."
                ),
                requisito="RN-03",
                campos={"status": "Estado automático."},
            )
        raise ErroRegraViolada(
            f"{descricao} está {ROTULOS[de].lower()} e não pode passar para "
            f"{ROTULOS.get(para, para).lower()}.",
            requisito="RN-03",
            campos={"status": f"Transição não permitida a partir de {ROTULOS[de].lower()}."},
        )


def exige_confirmacao_de_alteracao_historica(
    *,
    status_atual: str,
    data_do_lancamento: date,
    confirmado: bool,
    hoje: date | None = None,
) -> bool:
    """Editar ocorrência passada já efetivada exige `confirmar_alteracao_historica`.

    data-model §5.8. Devolve `True` quando a edição **é** histórica, para quem chama
    marcar a auditoria — a marca é o que permite depois responder "por que o
    fechamento de maio mudou?".

    Não é proibição: é fricção deliberada. O número de um mês fechado já foi olhado
    por alguém, e mudá-lo sem avisar transforma um relatório conferido em outro
    diferente sem rastro.
    """
    hoje = hoje or date.today()
    e_historica = status_atual == "efetivado" and data_do_lancamento < hoje

    if e_historica and not confirmado:
        raise ErroConfirmacaoNecessaria(
            (
                f"Este lançamento é de {data_do_lancamento.strftime('%d/%m/%Y')} e já está "
                "efetivado. Alterar muda um período que já foi fechado."
            ),
            requisito="RN-07",
            previa={
                "data": data_do_lancamento.isoformat(),
                "status": status_atual,
                "efeito": "O total do período já fechado muda.",
            },
            campo_confirmacao="confirmar_alteracao_historica",
        )

    return e_historica
