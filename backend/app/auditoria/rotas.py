"""Auditoria — contracts/plataforma.md §5. `FR-103`, `RN-08`.

**Somente leitura.** Não existe escrita nem exclusão pela API: quem grava é
`comum/auditoria.py`, na mesma transação da operação auditada, e a tabela nunca é
apagada (histórico financeiro é permanente).

Dois modos, com papéis diferentes e o motivo é concreto:

- **Por registro** (`?entidade=&entidade_id=`) — gestor **e operador**. É a linha do
  tempo do painel de detalhe (`FR-041`): quem lançou precisa ver o histórico do que
  lançou.
- **Geral**, com filtros de usuário e período — **só gestor**. É a visão de "o que
  aconteceu no sistema", que é supervisão, não operação.

Tarefa: T131
"""

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroSemPermissao
from app.comum.paginacao import Paginacao, envelope, parametros_de_paginacao
from app.db import obter_conexao
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/auditoria", tags=["Plataforma"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]


async def exige_papel_do_modo(
    usuario: Autenticado,
    entidade: Annotated[str | None, Query(description="lancamentos, clientes…")] = None,
    entidade_id: Annotated[UUID | None, Query()] = None,
) -> bool:
    """Decide o papel exigido a partir do modo, **antes** de o banco ser tocado.

    Podia estar no corpo do endpoint, e estava — mas aí a conexão já tinha sido aberta
    quando a recusa acontecia. Autorização que abre conexão para depois recusar gasta
    conexão de quem não deveria nem chegar ali, e é o oposto do que
    `test_401_nao_abre_conexao_com_o_banco` fixou em B0.

    Como dependência, o `403` sai antes: o FastAPI resolve as dependências na ordem da
    assinatura, e esta vem antes de `Conexao`.
    """
    por_registro = entidade is not None and entidade_id is not None

    if not por_registro and not usuario.e_gestor:
        raise ErroSemPermissao(
            (
                "O histórico geral é restrito a gestor. Para ver o histórico de um "
                "lançamento, abra o lançamento."
            ),
            requisito="FR-103",
        )
    return por_registro


@roteador.get(
    "",
    summary="Linha do tempo de um registro, ou o histórico geral",
    description=(
        "Papel: **gestor, operador** com `entidade` + `entidade_id` (é a linha do tempo do "
        "painel de detalhe, `FR-041`). **Só gestor** sem filtro de registro — a visão "
        "geral é supervisão, não operação. Somente leitura: não há escrita nem exclusão "
        "pela API. `alteracao_historica: true` marca edição de ocorrência passada já "
        "efetivada (data-model §5.8)."
    ),
)
async def listar(
    usuario: Autenticado,
    por_registro: Annotated[bool, Depends(exige_papel_do_modo)],
    conexao: Conexao,
    paginacao: Annotated[Paginacao, Depends(parametros_de_paginacao)],
    entidade: Annotated[str | None, Query(description="lancamentos, clientes…")] = None,
    entidade_id: Annotated[UUID | None, Query()] = None,
    usuario_id: Annotated[UUID | None, Query(description="Só gestor.")] = None,
    acao: Annotated[str | None, Query(description="criacao|edicao|exclusao|restauracao.")] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    condicoes = ["true"]
    parametros: dict[str, Any] = {}

    if por_registro:
        condicoes.append("a.entidade = :entidade and a.entidade_id = :entidade_id")
        parametros |= {"entidade": entidade, "entidade_id": str(entidade_id)}
    if usuario_id is not None:
        condicoes.append("a.usuario_id = :usuario_id")
        parametros["usuario_id"] = str(usuario_id)
    if acao is not None:
        condicoes.append("a.acao = cast(:acao as acao_auditoria)")
        parametros["acao"] = acao
    if data_inicio is not None:
        condicoes.append("a.criado_em >= :data_inicio")
        parametros["data_inicio"] = data_inicio
    if data_fim is not None:
        # `< data_fim + 1 dia` em vez de `<=`: `criado_em` é timestamptz, e `<= data_fim`
        # cortaria tudo que aconteceu depois da meia-noite do último dia.
        condicoes.append("a.criado_em < (cast(:data_fim as date) + 1)")
        parametros["data_fim"] = data_fim

    onde = " and ".join(condicoes)

    linhas = (
        (
            await conexao.execute(
                text(f"""
                    select a.id, a.entidade, a.entidade_id, a.acao, a.alteracoes, a.criado_em,
                           u.id as usuario_id, u.nome as usuario_nome
                    from auditoria a
                    join usuarios u on u.id = a.usuario_id
                    where {onde}
                    order by a.criado_em desc
                    limit :limite offset :deslocamento
                    """),
                parametros
                | {"limite": paginacao.por_pagina, "deslocamento": paginacao.deslocamento},
            )
        )
        .mappings()
        .all()
    )
    total = (
        await conexao.execute(text(f"select count(*) from auditoria a where {onde}"), parametros)
    ).scalar_one()

    return envelope(
        [
            {
                "id": linha["id"],
                "entidade": linha["entidade"],
                "entidade_id": str(linha["entidade_id"]),
                "acao": linha["acao"],
                "usuario": {"id": str(linha["usuario_id"]), "nome": linha["usuario_nome"]},
                "criado_em": linha["criado_em"].isoformat(),
                "alteracoes": (linha["alteracoes"] or {}).get("campos", {}),
                "alteracao_historica": (linha["alteracoes"] or {}).get(
                    "alteracao_historica", False
                ),
            }
            for linha in linhas
        ],
        total=total,
        paginacao=paginacao,
    )
