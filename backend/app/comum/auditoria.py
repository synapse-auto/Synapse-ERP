"""Registro de auditoria — `RF-03`, `RN-08`, tabela `auditoria` (data-model §3.17).

Grava **só o que mudou**, no formato `{campo: {de, para}}`. Guardar a linha inteira a
cada edição encheria a tabela de repetição e, pior, tornaria a linha do tempo do
painel de detalhe (`FR-041`) ilegível: quem olha quer ver "valor: de 1.800,00 para
2.000,00", não 30 campos iguais.

A tabela **nunca é apagada** e não tem soft delete — histórico financeiro é
permanente (Assumptions da spec). Por isso `registra_auditoria` só insere; não existe
função de atualizar nem de remover neste módulo, de propósito.

O autor vem do token, nunca do corpo da requisição (contracts/README.md §Auditoria).
Quem chama passa o usuário que a dependência de autenticação já resolveu.

Tarefa: T029
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

AcaoAuditoria = Literal["criacao", "edicao", "exclusao", "restauracao"]

# Campos que o sistema mexe sozinho e que só poluiriam a linha do tempo.
_CAMPOS_IGNORADOS = frozenset({"atualizado_em", "atualizado_por", "versao", "criado_em"})


def _serializavel(valor: Any) -> Any:
    """Deixa o valor gravável em `jsonb` sem perder precisão de dinheiro.

    `Decimal` vira **string**, não float: `2000.00` como float perde exatidão, e o
    ponto de existir auditoria financeira é o número bater depois.
    """
    if valor is None or isinstance(valor, bool | int | str):
        return valor
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, list | tuple):
        return [_serializavel(item) for item in valor]
    if isinstance(valor, dict):
        return {str(chave): _serializavel(item) for chave, item in valor.items()}
    return str(valor)


def calcula_diferenca(
    antes: dict[str, Any] | None,
    depois: dict[str, Any] | None,
    *,
    ignorar: frozenset[str] = _CAMPOS_IGNORADOS,
) -> dict[str, dict[str, Any]]:
    """`{campo: {"de": ..., "para": ...}}` apenas dos campos que mudaram.

    Na criação, `antes` é `None` e todo campo preenchido entra com `de: null`. Na
    exclusão, `depois` é `None`. Comparação feita já no valor serializado, senão
    `Decimal("2000.00")` e `Decimal("2000.0")` apareceriam como mudança.
    """
    antes = antes or {}
    depois = depois or {}
    diferenca: dict[str, dict[str, Any]] = {}

    for campo in set(antes) | set(depois):
        if campo in ignorar:
            continue
        de = _serializavel(antes.get(campo))
        para = _serializavel(depois.get(campo))
        if de != para:
            diferenca[campo] = {"de": de, "para": para}

    return diferenca


async def registra_auditoria(
    conexao: AsyncConnection,
    *,
    entidade: str,
    entidade_id: str | UUID,
    acao: AcaoAuditoria,
    usuario_id: str | UUID,
    alteracoes: dict[str, Any] | None = None,
    antes: dict[str, Any] | None = None,
    depois: dict[str, Any] | None = None,
    alteracao_historica: bool = False,
) -> None:
    """Insere uma linha em `auditoria`.

    Ou se passa `alteracoes` já calculado, ou se passa `antes`/`depois` e a
    diferença sai daqui — o segundo caminho é o comum e evita cada serviço
    reimplementar a comparação (Princípio III).

    Roda na **mesma conexão e mesma transação** da escrita que está sendo auditada.
    É o que garante que não exista alteração sem registro: se o insert da auditoria
    falhar, a operação inteira volta atrás.

    `alteracao_historica` marca edição de ocorrência passada já efetivada
    (data-model §5.8) — o contrato de auditoria devolve essa marca (§5 de
    contracts/plataforma.md).
    """
    if alteracoes is None:
        alteracoes = calcula_diferenca(antes, depois)

    # Edição que não mudou nada não vira linha — senão a linha do tempo enche de
    # "editou" sem nada editado. Criação e exclusão sempre registram, mesmo com
    # diferença vazia, porque o fato em si é o registro.
    if acao == "edicao" and not alteracoes:
        return

    corpo = {"campos": _serializavel(alteracoes)}
    if alteracao_historica:
        corpo["alteracao_historica"] = True

    await conexao.execute(
        text("""
            insert into auditoria (entidade, entidade_id, acao, alteracoes, usuario_id)
            values (:entidade, :entidade_id, :acao, cast(:alteracoes as jsonb), :usuario_id)
            """),
        {
            "entidade": entidade,
            "entidade_id": str(entidade_id),
            "acao": acao,
            "alteracoes": json.dumps(corpo, ensure_ascii=False),
            "usuario_id": str(usuario_id),
        },
    )
