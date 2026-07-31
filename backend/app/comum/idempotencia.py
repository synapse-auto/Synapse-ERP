"""Cabeçalho `Idempotency-Key` nos POST de criação — contracts/README.md.

**O problema real**: a Vercel pode repetir uma invocação depois de um timeout de
rede. Um clique lento em "Salvar" viraria dois lançamentos iguais, e num sistema
financeiro isso é um valor contado em dobro no saldo — não um incômodo de interface.

**Como funciona**: o cliente manda uma chave por tentativa. A primeira chamada
registra a chave junto do resultado. Repetição com a mesma chave devolve o resultado
guardado, sem executar de novo.

## Onde a chave é guardada — e por que mudou

Até 2026-07-31 este módulo guardava em **memória do processo**, e dizia em voz alta que
isso não fechava o caso principal: a repetição que a Vercel faz depois de um timeout cai
normalmente numa instância nova, com a memória vazia. Ou seja, o mecanismo cobria clique
duplo na mesma instância quente e falhava exatamente no cenário para o qual foi escrito.
O README do backend listava isso como divergência aberta desde B0.

Agora a chave vive na tabela `chaves_idempotencia` (migração `012`), com PK
`(usuario_id, rota, chave)` — a mesma tripla de antes. A escrita acontece **na mesma
transação** da operação auditada: se a criação volta atrás, a chave volta junto, e uma
repetição depois de um erro é tratada como tentativa nova, que é o certo.

**O que a PK resolve além da leitura**: se duas invocações correrem de fato ao mesmo
tempo, a segunda falha no `insert` em vez de criar a linha duplicada. Falhar é o
comportamento desejado — o cliente repete e, a essa altura, a primeira já commitou e a
resposta guardada é devolvida.

**O que continua fora do alcance**: duas invocações simultâneas em que a segunda lê antes
de a primeira commitar veem o banco sem a chave. Aí a proteção é a PK acima, não a
leitura. Para 3 usuários, a janela é teórica; está escrito para não passar por resolvido
o que é apenas improvável.

Tarefa: T028 (fechada em 2026-07-31)
"""

import json
from datetime import timedelta
from typing import Annotated, Any

from fastapi import Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroValidacao

# Uma chave repetida depois disso é tratada como tentativa nova. Prazo curto de
# propósito: a janela que interessa é a de uma repetição de rede, medida em
# segundos. Guardar por horas só acumularia lixo.
VALIDADE = timedelta(minutes=10)

TAMANHO_MAXIMO = 200


def chave_de_idempotencia(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    """Dependência do FastAPI. O cabeçalho é opcional (contracts/README.md)."""
    if idempotency_key is None:
        return None
    chave = idempotency_key.strip()
    if not chave:
        return None
    if len(chave) > TAMANHO_MAXIMO:
        raise ErroValidacao(
            "A chave de idempotência é longa demais.",
            campos={"Idempotency-Key": f"Máximo de {TAMANHO_MAXIMO} caracteres."},
        )
    return chave


async def resposta_ja_registrada(
    conexao: AsyncConnection, chave: str | None, *, rota: str, usuario_id: str
) -> Any | None:
    """Resultado guardado desta chave, se houver e se ainda estiver no prazo.

    A chave é escopada por rota e por usuário: a mesma chave em endpoints
    diferentes, ou vinda de pessoas diferentes, são operações diferentes.
    """
    if chave is None:
        return None

    linha = (
        await conexao.execute(
            text("""
                select resposta from chaves_idempotencia
                where usuario_id = cast(:usuario as uuid)
                  and rota = :rota and chave = :chave
                  and expira_em > now()
                """),
            {"usuario": usuario_id, "rota": rota, "chave": chave},
        )
    ).scalar_one_or_none()
    return linha


async def registra_resposta(
    conexao: AsyncConnection,
    chave: str | None,
    *,
    rota: str,
    usuario_id: str,
    resposta: Any,
) -> None:
    """Guarda o resultado para que a repetição devolva o mesmo, sem executar de novo.

    Sem `on conflict`: conflito aqui significa duas invocações concorrentes com a mesma
    chave, e nesse caso falhar é o certo — ver o topo do módulo. Silenciar com
    `do nothing` esconderia justamente a corrida que a PK existe para pegar.
    """
    if chave is None:
        return

    await conexao.execute(
        text("""
            insert into chaves_idempotencia (usuario_id, rota, chave, resposta, expira_em)
            values (
              cast(:usuario as uuid), :rota, :chave, cast(:resposta as jsonb),
              now() + make_interval(secs => :validade_segundos)
            )
            """),
        {
            "usuario": usuario_id,
            "rota": rota,
            "chave": chave,
            "resposta": json.dumps(resposta, ensure_ascii=False, default=str),
            # `make_interval` em vez de `cast(:validade as interval)`: com o cast, o
            # asyncpg infere o parâmetro como `interval` e exige um `timedelta` — passar
            # a string "600 seconds" morre em `'str' object has no attribute 'days'`.
            # Com segundos, o parâmetro é numérico e não há ambiguidade de tipo.
            "validade_segundos": VALIDADE.total_seconds(),
        },
    )
