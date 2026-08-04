"""Notificações — geração e deduplicação. `FR-096`–`FR-100`.

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T123).

## A `chave_deduplicacao` é o módulo inteiro

A rotina diária pode rodar mais de uma vez no mesmo dia (D-08) — pelo cron, pelo disparo
manual e pela chamada implícita de uma leitura. Sem uma chave estável, o mesmo "vence em
3 dias" viraria três notificações no sino, e o usuário aprenderia a ignorar o sino.

O `UNIQUE (usuario_id, chave_deduplicacao)` do banco (migração `005`) faz o
`on conflict do nothing` resolver isso sem consulta prévia. Os quatro formatos vêm de
data-model §3.16 e estão montados aqui, num lugar só — espalhá-los pelos chamadores
garantiria que um deles ia divergir e voltar a duplicar.

## Uma linha por destinatário

Notificação não é broadcast: cada usuário tem a sua, com seu próprio `lida_em`. São 3
usuários, então "gerar para todos" é literalmente três inserts — e ter a linha por
pessoa é o que permite o contador de não lidas de `FR-100` existir.

Tarefa: T123
"""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

TIPOS = ("vencimento", "inadimplencia", "resumo_semanal", "caixa_baixo")


# ── Os quatro formatos de chave (data-model §3.16) ──────────────────────────


def chave_de_vencimento(lancamento_id: Any, dias: int) -> str:
    return f"vencimento:{lancamento_id}:{dias}"


def chave_de_inadimplencia(cliente_id: Any, quando: date) -> str:
    """Uma por cliente **por dia**: o atraso continua existindo amanhã, e o aviso
    de amanhã é um fato novo — mas o de hoje não pode se repetir três vezes."""
    return f"inadimplencia:{cliente_id}:{quando.isoformat()}"


def chave_de_resumo_semanal(quando: date) -> str:
    ano, semana, _ = quando.isocalendar()
    return f"resumo_semanal:{ano}-W{semana:02d}"


def chave_de_caixa_baixo(mundo: str, quando: date) -> str:
    ano, semana, _ = quando.isocalendar()
    return f"caixa_baixo:{mundo}:{ano}-W{semana:02d}"


# ── Geração ─────────────────────────────────────────────────────────────────


async def destinatarios(conexao: AsyncConnection) -> list[UUID]:
    """Todos os usuários ativos. São 3 — não vale complicar (Princípio I)."""
    linhas = (await conexao.execute(text("select id from usuarios where ativo"))).all()
    return [linha[0] for linha in linhas]


async def cria(
    conexao: AsyncConnection,
    *,
    tipo: str,
    titulo: str,
    corpo: str,
    chave: str,
    mundo: str | None = None,
    lancamento_id: Any = None,
    cliente_id: Any = None,
    usuarios: list[UUID] | None = None,
) -> int:
    """Cria a notificação para cada destinatário. Devolve quantas foram **criadas**.

    O `on conflict do nothing` é o que torna a rotina idempotente sem consultar antes:
    a segunda execução do dia tenta inserir e o banco recusa em silêncio, que é
    exatamente o desejado.
    """
    alvos = usuarios if usuarios is not None else await destinatarios(conexao)
    if not alvos:
        return 0

    resultado = await conexao.execute(
        text("""
            insert into notificacoes (
              usuario_id, tipo, titulo, corpo, mundo,
              lancamento_id, cliente_id, chave_deduplicacao
            )
            select unnest(cast(:usuarios as uuid[])),
                   cast(:tipo as tipo_notificacao), :titulo, :corpo,
                   cast(:mundo as mundo), cast(:lancamento as uuid),
                   cast(:cliente as uuid), :chave
            on conflict (usuario_id, chave_deduplicacao) do nothing
            """),
        {
            "usuarios": [str(u) for u in alvos],
            "tipo": tipo,
            "titulo": titulo,
            "corpo": corpo,
            "mundo": mundo,
            "lancamento": str(lancamento_id) if lancamento_id else None,
            "cliente": str(cliente_id) if cliente_id else None,
            "chave": chave,
        },
    )
    return resultado.rowcount or 0


async def cria_varias(
    conexao: AsyncConnection,
    *,
    tipo: str,
    itens: list[dict[str, Any]],
    usuarios: list[UUID] | None = None,
) -> int:
    """Várias notificações do **mesmo tipo**, numa ida ao banco.

    `cria` já resolvia o produto "uma notificação × N destinatários" num `INSERT`; o que
    faltava era o outro eixo. A rotina diária avisa de tudo que vence em 1, 3 e 7 dias e
    chamava `cria` uma vez por lançamento — com 50 contas vencendo, 150 idas ao banco
    (Skill: `data-batch-inserts`).

    Cada item traz `titulo`, `corpo`, `chave` e, opcionalmente, `mundo`, `lancamento_id`
    e `cliente_id`. `tipo` é comum a todos de propósito: misturar tipos numa chamada
    esconderia qual alerta é qual no relato da rotina.

    O `on conflict do nothing` continua sendo o que torna a rotina idempotente sem
    consultar antes.
    """
    alvos = usuarios if usuarios is not None else await destinatarios(conexao)
    if not alvos or not itens:
        return 0

    resultado = await conexao.execute(
        text("""
            insert into notificacoes (
              usuario_id, tipo, titulo, corpo, mundo,
              lancamento_id, cliente_id, chave_deduplicacao
            )
            select u.usuario_id, cast(:tipo as tipo_notificacao),
                   n.titulo, n.corpo, cast(n.mundo as mundo),
                   cast(n.lancamento as uuid), cast(n.cliente as uuid), n.chave
            from unnest(
              cast(:titulos as text[]), cast(:corpos as text[]), cast(:mundos as text[]),
              cast(:lancamentos as text[]), cast(:clientes as text[]), cast(:chaves as text[])
            ) as n(titulo, corpo, mundo, lancamento, cliente, chave)
            cross join unnest(cast(:usuarios as uuid[])) as u(usuario_id)
            on conflict (usuario_id, chave_deduplicacao) do nothing
            """),
        {
            "usuarios": [str(u) for u in alvos],
            "tipo": tipo,
            "titulos": [item["titulo"] for item in itens],
            "corpos": [item["corpo"] for item in itens],
            "mundos": [item.get("mundo") for item in itens],
            "lancamentos": [
                str(item["lancamento_id"]) if item.get("lancamento_id") else None for item in itens
            ],
            "clientes": [
                str(item["cliente_id"]) if item.get("cliente_id") else None for item in itens
            ],
            "chaves": [item["chave"] for item in itens],
        },
    )
    return resultado.rowcount or 0


# ── Consultas do sino ───────────────────────────────────────────────────────


async def nao_lidas(conexao: AsyncConnection, usuario_id: UUID) -> int:
    """`FR-100` — o contador do sino."""
    return (
        await conexao.execute(
            text(
                "select count(*) from notificacoes where usuario_id = :usuario and lida_em is null"
            ),
            {"usuario": str(usuario_id)},
        )
    ).scalar_one()


async def lista(
    conexao: AsyncConnection,
    usuario_id: UUID,
    *,
    mundos: list[str],
    apenas_nao_lidas: bool,
    limite: int,
    deslocamento: int,
) -> list[dict[str, Any]]:
    """Só as do próprio usuário.

    `mundo is null` sempre entra: é a notificação consolidada, que não pertence a um
    lado do negócio e some se o filtro for aplicado sem exceção (`RF-101`).
    """
    linhas = (
        (
            await conexao.execute(
                text("""
                    select id, tipo, titulo, corpo, mundo,
                           lancamento_id, cliente_id, lida_em, criado_em
                    from notificacoes
                    where usuario_id = :usuario
                      and (mundo is null or mundo = any(cast(:mundos as mundo[])))
                      and (not :apenas_nao_lidas or lida_em is null)
                    order by criado_em desc
                    limit :limite offset :deslocamento
                    """),
                {
                    "usuario": str(usuario_id),
                    "mundos": mundos,
                    "apenas_nao_lidas": apenas_nao_lidas,
                    "limite": limite,
                    "deslocamento": deslocamento,
                },
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def conta(
    conexao: AsyncConnection, usuario_id: UUID, *, mundos: list[str], apenas_nao_lidas: bool
) -> int:
    return (
        await conexao.execute(
            text("""
                select count(*) from notificacoes
                where usuario_id = :usuario
                  and (mundo is null or mundo = any(cast(:mundos as mundo[])))
                  and (not :apenas_nao_lidas or lida_em is null)
                """),
            {
                "usuario": str(usuario_id),
                "mundos": mundos,
                "apenas_nao_lidas": apenas_nao_lidas,
            },
        )
    ).scalar_one()


def para_json(linha: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "tipo": linha["tipo"],
        "titulo": linha["titulo"],
        "corpo": linha["corpo"],
        "mundo": linha["mundo"],
        "lancamento_id": str(linha["lancamento_id"]) if linha["lancamento_id"] else None,
        "cliente_id": str(linha["cliente_id"]) if linha["cliente_id"] else None,
        "lida_em": linha["lida_em"].isoformat() if linha["lida_em"] else None,
        "criado_em": linha["criado_em"].isoformat(),
    }
