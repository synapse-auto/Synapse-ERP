"""Serviços da Synapse — leitura. `FR-104`, contracts/cadastros.md §5.

Alimenta o campo "serviço vinculado" do lançamento. Cada serviço pertence a um mundo
(CRM → digital, Redes → infra), então a lista já chega filtrada pelo mundo ativo.

O CRUD de gestor (`POST`, `PUT`, arquivar) fica em `T111`, sub-fase B4. Aqui só a
leitura, que é o que o formulário de lançamento precisa em B1.

Skill `supabase-postgres-best-practices` acionada antes da consulta (task 🟢).

Tarefa: T051
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

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
