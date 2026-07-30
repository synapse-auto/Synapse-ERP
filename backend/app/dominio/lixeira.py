"""`RN-08` — soft delete e lixeira. Módulo dono da regra (Princípio III).

Excluir marca `excluido_em` e `excluido_por`; a linha **nunca sai do banco**. Passado
o prazo de `configuracoes.lixeira_retencao_dias` (padrão 90), a lixeira para de
oferecer a restauração — mas a linha continua lá, porque histórico financeiro é
permanente (Assumptions da spec, data-model §5.7).

Consequência que costuma surpreender: **não existe exclusão definitiva pela API**. Não
é esquecimento, é a regra.

Tarefa: T047
"""

from datetime import UTC, datetime, timedelta

from app.comum.erros import ErroRegraViolada

RETENCAO_PADRAO_DIAS = 90


def _agora(agora: datetime | None) -> datetime:
    return agora or datetime.now(UTC)


def dias_restantes(
    excluido_em: datetime,
    *,
    retencao_dias: int = RETENCAO_PADRAO_DIAS,
    agora: datetime | None = None,
) -> int:
    """Quantos dias ainda dá para restaurar. Nunca negativo — zero é o piso.

    Vai na resposta de `GET /api/lixeira` para a tela dizer "restam 12 dias" em vez de
    só listar (`FR-017`).
    """
    limite = excluido_em + timedelta(days=retencao_dias)
    faltam = (limite - _agora(agora)).days
    return max(faltam, 0)


def pode_restaurar(
    excluido_em: datetime,
    *,
    retencao_dias: int = RETENCAO_PADRAO_DIAS,
    agora: datetime | None = None,
) -> bool:
    return _agora(agora) - excluido_em < timedelta(days=retencao_dias)


def exige_pode_restaurar(
    excluido_em: datetime,
    *,
    retencao_dias: int = RETENCAO_PADRAO_DIAS,
    agora: datetime | None = None,
) -> None:
    """Recusa a restauração fora do prazo (`409 regra_violada` / `RN-08`).

    A mensagem diz que o dado **não foi apagado** — quem tenta restaurar depois de 90
    dias precisa saber que a informação continua no sistema, só não volta sozinha.
    """
    if pode_restaurar(excluido_em, retencao_dias=retencao_dias, agora=agora):
        return
    raise ErroRegraViolada(
        (
            f"Este lançamento foi excluído há mais de {retencao_dias} dias e não pode "
            "mais ser restaurado automaticamente. O registro não foi apagado — ele "
            "continua no histórico."
        ),
        requisito="RN-08",
        campos={"lancamento": f"Prazo de restauração: {retencao_dias} dias."},
    )


def exige_nao_excluido(excluido_em: datetime | None) -> None:
    """Impede operar sobre lançamento que está na lixeira.

    Sem isto, seria possível efetivar ou dividir um lançamento excluído — e ele voltaria
    aos totais pela porta dos fundos, sem nunca ter sido restaurado.
    """
    if excluido_em is None:
        return
    raise ErroRegraViolada(
        "Este lançamento está na lixeira. Restaure-o antes de alterá-lo.",
        requisito="RN-08",
        campos={"lancamento": "Excluído."},
    )
