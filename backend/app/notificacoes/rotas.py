"""Notificações — contracts/plataforma.md §4. `FR-096`–`FR-100`.

Papel: **autenticado**, sem distinção entre gestor e operador. Cada um vê só as próprias
notificações; não há como pedir as de outra pessoa, porque o `usuario_id` vem do token e
nunca da query.

**Não existe `POST` de criação.** Notificação é gerada pelas rotinas (§6), nunca por
usuário — deixar criar à mão transformaria o sino em caixa de recado e tiraria dele a
propriedade que o torna útil: tudo ali é um fato do sistema.

Tarefa: T124
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroNaoEncontrado
from app.comum.paginacao import Paginacao, envelope, parametros_de_paginacao
from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.notificacoes import servico
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/notificacoes", tags=["Plataforma"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]


@roteador.get(
    "",
    summary="As notificações do usuário logado",
    description=(
        "Papel: autenticado (gestor ou operador). Só as **do próprio usuário** — o id vem "
        "do token, nunca da query. `mundo: null` é notificação consolidada e aparece em "
        "qualquer filtro (`RF-101`). `nao_lidas` alimenta o contador do sino (`FR-100`)."
    ),
)
async def listar(
    usuario: Autenticado,
    conexao: Conexao,
    paginacao: Annotated[Paginacao, Depends(parametros_de_paginacao)],
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    apenas_nao_lidas: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    mundos = mod_mundo.resolve_filtro(mundo)
    linhas = await servico.lista(
        conexao,
        usuario.id,
        mundos=mundos,
        apenas_nao_lidas=apenas_nao_lidas,
        limite=paginacao.por_pagina,
        deslocamento=paginacao.deslocamento,
    )
    total = await servico.conta(
        conexao, usuario.id, mundos=mundos, apenas_nao_lidas=apenas_nao_lidas
    )
    resposta = envelope(
        [servico.para_json(linha) for linha in linhas], total=total, paginacao=paginacao
    )
    # O contador ignora o filtro de propósito: o sino mostra tudo que falta ler, não só
    # o que sobra do mundo selecionado.
    resposta["nao_lidas"] = await servico.nao_lidas(conexao, usuario.id)
    return resposta


@roteador.post(
    "/marcar-todas-lidas",
    summary="Marca todas como lidas",
    description="Papel: autenticado. Só as do próprio usuário.",
)
async def marcar_todas_lidas(usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    # ⚠️ Declarada ANTES de `/{notificacao_id}/marcar-lida`: sem isso,
    # "marcar-todas-lidas" seria lido como um id.
    resultado = await conexao.execute(
        text(
            "update notificacoes set lida_em = now() "
            "where usuario_id = :usuario and lida_em is null"
        ),
        {"usuario": str(usuario.id)},
    )
    return {"marcadas": resultado.rowcount or 0, "nao_lidas": 0}


@roteador.post(
    "/{notificacao_id}/marcar-lida",
    summary="Marca uma como lida",
    description="Papel: autenticado. Notificação de outro usuário responde `404`.",
)
async def marcar_lida(
    notificacao_id: UUID, usuario: Autenticado, conexao: Conexao
) -> dict[str, Any]:
    # O `usuario_id` no `where` é a autorização: pedir a notificação de outra pessoa
    # devolve 404, não 403 — responder 403 já contaria que ela existe.
    resultado = await conexao.execute(
        text("""
            update notificacoes set lida_em = coalesce(lida_em, now())
            where id = :id and usuario_id = :usuario
            """),
        {"id": str(notificacao_id), "usuario": str(usuario.id)},
    )
    if not resultado.rowcount:
        raise ErroNaoEncontrado("Notificação não encontrada.")

    return {"id": str(notificacao_id), "nao_lidas": await servico.nao_lidas(conexao, usuario.id)}
