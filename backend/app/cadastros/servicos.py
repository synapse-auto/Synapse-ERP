"""Serviços da Synapse — leitura. `FR-104`, contracts/cadastros.md §5.

Alimenta o campo "serviço vinculado" do lançamento. Cada serviço pertence a um mundo
(CRM → digital, Redes → infra), então a lista já chega filtrada pelo mundo ativo.

O CRUD de gestor (`POST`, `PUT`, arquivar) fica em `T111`, sub-fase B4. Aqui só a
leitura, que é o que o formulário de lançamento precisa em B1.

Skill `supabase-postgres-best-practices` acionada antes da consulta (task 🟢).

Tarefa: T051
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroNaoEncontrado
from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/servicos", tags=["Cadastros"])


@roteador.get(
    "",
    summary="Lista os serviços",
    description=(
        "Papel: gestor, operador. Filtra pelo mundo — um serviço pertence a um mundo só "
        "(`FR-104`). O índice `servicos_mundo_idx` cobre exatamente esta consulta."
    ),
)
async def listar(
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    incluir_inativos: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    mundos = mod_mundo.resolve_filtro(mundo)
    linhas = (
        (
            await conexao.execute(
                text("""
                    select id, nome, mundo, ativo, ordem
                    from servicos
                    where mundo = any(cast(:mundos as mundo[]))
                      and (:incluir_inativos or ativo)
                    order by mundo, ordem, lower(nome)
                    """),
                {"mundos": mundos, "incluir_inativos": incluir_inativos},
            )
        )
        .mappings()
        .all()
    )
    return {
        "itens": [
            {
                "id": str(linha["id"]),
                "nome": linha["nome"],
                "mundo": linha["mundo"],
                "ativo": linha["ativo"],
                "ordem": linha["ordem"],
            }
            for linha in linhas
        ]
    }


# ── T111 · CRUD de gestor (contracts/cadastros.md §5) ───────────────────────
#
# Serviço tem `mundo` e ele é imutável (`RN-15`): "Energia Solar" é do Infra e
# movê-la para o Digital reescreveria a receita por serviço dos dois lados.
# Não existe exclusão — só `ativo = false`, porque lançamento antigo continua
# apontando para o serviço (`RN-06`).


class ServicoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    mundo: str = Field(description="digital | infra. Imutável depois de criado (`RN-15`).")
    ordem: int = 0


def _servico_json(linha: Any) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "nome": linha["nome"],
        "mundo": linha["mundo"],
        "ativo": linha["ativo"],
        "ordem": linha["ordem"],
    }


async def _exige_servico(conexao: AsyncConnection, servico_id: UUID) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text("select id, nome, mundo, ativo, ordem from servicos where id = :id"),
                {"id": str(servico_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Serviço não encontrado.")
    return dict(linha)


@roteador.post("", status_code=201, summary="Cria um serviço", description="Papel: gestor.")
async def criar(
    corpo: ServicoEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    mundo_validado = mod_mundo.exige("servicos", corpo.mundo)
    novo = (
        (
            await conexao.execute(
                text("""
                    insert into servicos (nome, mundo, ordem)
                    values (:nome, cast(:mundo as mundo), :ordem)
                    returning id, nome, mundo, ativo, ordem
                    """),
                {"nome": corpo.nome, "mundo": mundo_validado, "ordem": corpo.ordem},
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="servicos",
        entidade_id=novo["id"],
        acao="criacao",
        usuario_id=usuario.id,
        depois=dict(novo),
    )
    return _servico_json(novo)


@roteador.put(
    "/{servico_id}",
    summary="Edita o nome e a ordem",
    description="Papel: gestor. Mudar `mundo` → `409` / `RN-15`.",
)
async def editar(
    servico_id: UUID,
    corpo: ServicoEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    atual = await _exige_servico(conexao, servico_id)
    mod_mundo.recusa_alteracao(atual["mundo"], corpo.mundo)

    depois = (
        (
            await conexao.execute(
                text("""
                    update servicos set nome = :nome, ordem = :ordem where id = :id
                    returning id, nome, mundo, ativo, ordem
                    """),
                {"id": str(servico_id), "nome": corpo.nome, "ordem": corpo.ordem},
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="servicos",
        entidade_id=servico_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes=atual,
        depois=dict(depois),
    )
    return _servico_json(depois)


@roteador.post(
    "/{servico_id}/arquivar",
    summary="Desativa o serviço",
    description=(
        "Papel: gestor. `RN-06`: o serviço some dos formulários novos e os lançamentos "
        "antigos continuam apontando para ele. Não existe exclusão."
    ),
)
async def arquivar(
    servico_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text("""
                    update servicos set ativo = false where id = :id and ativo
                    returning id, nome, mundo, ativo, ordem
                    """),
                {"id": str(servico_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Serviço não encontrado ou já desativado.")

    await registra_auditoria(
        conexao,
        entidade="servicos",
        entidade_id=servico_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={"ativo": {"de": True, "para": False}},
    )
    return _servico_json(linha)
