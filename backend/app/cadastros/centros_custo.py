"""Centros de custo — `RN-13`, contracts/cadastros.md §6.

**Ausência significa "geral".** Não se cria um centro de custo chamado "Geral": o
lançamento sem centro já é o geral. Criar um seria ter duas representações da mesma
coisa, e relatório por centro passaria a depender de qual delas o usuário escolheu.

Tem `mundo` (`RF-103`), obrigatório e imutável.

Skill `supabase-postgres-best-practices` acionada antes das consultas (task 🟢).

Tarefa: T049
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroNaoEncontrado, ErroValidacao
from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/centros-custo", tags=["Cadastros"])

NOMES_RESERVADOS = {"geral", "general", "padrao", "padrão"}


class CentroEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    mundo: str = Field(description="digital | infra. Imutável depois de criado (RN-15).")


def _para_json(linha: Any) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "nome": linha["nome"],
        "mundo": linha["mundo"],
        "arquivado_em": linha["arquivado_em"].isoformat() if linha["arquivado_em"] else None,
    }


def _recusa_nome_reservado(nome: str) -> None:
    if nome.strip().lower() in NOMES_RESERVADOS:
        raise ErroValidacao(
            f"Não crie um centro de custo chamado '{nome}'.",
            requisito="RN-13",
            campos={
                "nome": (
                    "Lançamento sem centro de custo já significa geral. "
                    "Criar um centro com esse nome duplicaria a mesma informação."
                )
            },
        )


@roteador.get("", summary="Lista os centros de custo", description="Papel: gestor, operador.")
async def listar(
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    incluir_arquivados: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    mundos = mod_mundo.resolve_filtro(mundo)
    linhas = (
        (
            await conexao.execute(
                text("""
                    select id, nome, mundo, arquivado_em
                    from centros_custo
                    where mundo = any(cast(:mundos as mundo[]))
                      and (:incluir_arquivados or arquivado_em is null)
                    order by mundo, lower(nome)
                    """),
                {"mundos": mundos, "incluir_arquivados": incluir_arquivados},
            )
        )
        .mappings()
        .all()
    )
    return {"itens": [_para_json(linha) for linha in linhas]}


@roteador.post("", status_code=201, summary="Cria um centro de custo", description="Papel: gestor.")
async def criar(
    corpo: CentroEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    _recusa_nome_reservado(corpo.nome)
    mundo_validado = mod_mundo.exige("centros_custo", corpo.mundo)

    linha = (
        (
            await conexao.execute(
                text("""
                    insert into centros_custo (nome, mundo)
                    values (:nome, cast(:mundo as mundo))
                    returning id, nome, mundo, arquivado_em
                    """),
                {"nome": corpo.nome, "mundo": mundo_validado},
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="centros_custo",
        entidade_id=linha["id"],
        acao="criacao",
        usuario_id=usuario.id,
        depois=dict(linha),
    )
    return _para_json(linha)


@roteador.put("/{centro_id}", summary="Edita o nome", description="Papel: gestor.")
async def editar(
    centro_id: UUID,
    corpo: CentroEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    _recusa_nome_reservado(corpo.nome)

    antes = (
        (
            await conexao.execute(
                text("select id, nome, mundo, arquivado_em from centros_custo where id = :id"),
                {"id": str(centro_id)},
            )
        )
        .mappings()
        .first()
    )
    if antes is None:
        raise ErroNaoEncontrado("Centro de custo não encontrado.")

    # RN-15: só o nome muda. O gatilho do banco recusaria de qualquer jeito, mas aqui a
    # mensagem sai em PT-BR com o requisito citado.
    mod_mundo.recusa_alteracao(antes["mundo"], corpo.mundo)

    depois = (
        (
            await conexao.execute(
                text("""
                    update centros_custo set nome = :nome where id = :id
                    returning id, nome, mundo, arquivado_em
                    """),
                {"id": str(centro_id), "nome": corpo.nome},
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="centros_custo",
        entidade_id=centro_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes=dict(antes),
        depois=dict(depois),
    )
    return _para_json(depois)


@roteador.post("/{centro_id}/arquivar", summary="Arquiva", description="Papel: gestor.")
async def arquivar(
    centro_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    """Arquiva, nunca exclui.

    Lançamento antigo continua apontando para o centro arquivado — ele só some dos
    formulários novos. `RN-06`: nunca lançamento órfão.
    """
    linha = (
        (
            await conexao.execute(
                text("""
                    update centros_custo set arquivado_em = now()
                    where id = :id and arquivado_em is null
                    returning id, nome, mundo, arquivado_em
                    """),
                {"id": str(centro_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Centro de custo não encontrado ou já arquivado.")

    await registra_auditoria(
        conexao,
        entidade="centros_custo",
        entidade_id=centro_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={"arquivado_em": {"de": None, "para": linha["arquivado_em"].isoformat()}},
    )
    return _para_json(linha)
