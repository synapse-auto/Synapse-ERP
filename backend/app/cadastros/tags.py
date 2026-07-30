"""Tags — `RN-14`, contracts/cadastros.md §7.

Sem hierarquia, sem mundo, sem limite por lançamento. Servem para filtro e agrupamento
ad-hoc.

**Papéis** (contracts/README.md): `GET`/`POST` para gestor e operador — quem lança
precisa criar a tag na hora, senão o cadastro vira gargalo. `PUT`/`DELETE` só gestor:
renomear ou apagar tag mexe em lançamentos de todo mundo.

Skill `supabase-postgres-best-practices` acionada antes das consultas (task 🟢).

Tarefa: T048
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada, ErroValidacao
from app.db import obter_conexao
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/tags", tags=["Cadastros"])

HEX = r"^#[0-9A-Fa-f]{6}$"


class TagEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    cor: str = Field(pattern=HEX, description="Hex #RRGGBB.")


def _linha_para_json(linha: Any) -> dict[str, Any]:
    return {"id": str(linha["id"]), "nome": linha["nome"], "cor": linha["cor"]}


@roteador.get("", summary="Lista as tags", description="Papel: gestor, operador.")
async def listar(
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    linhas = (
        (await conexao.execute(text("select id, nome, cor from tags order by lower(nome)")))
        .mappings()
        .all()
    )
    # Sem paginação de propósito: são dezenas, e a tela usa a lista inteira para montar
    # o seletor de filtro. Paginar aqui obrigaria o frontend a juntar páginas para
    # desenhar um dropdown (Princípio I).
    return {"itens": [_linha_para_json(linha) for linha in linhas]}


@roteador.post("", status_code=201, summary="Cria uma tag", description="Papel: gestor, operador.")
async def criar(
    corpo: TagEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    ja_existe = (
        await conexao.execute(
            text("select id from tags where lower(nome) = lower(:nome)"), {"nome": corpo.nome}
        )
    ).scalar_one_or_none()
    if ja_existe:
        raise ErroValidacao(
            f"Já existe uma tag chamada '{corpo.nome}'.",
            campos={"nome": "Escolha outro nome."},
        )

    linha = (
        (
            await conexao.execute(
                text("insert into tags (nome, cor) values (:nome, :cor) returning id, nome, cor"),
                {"nome": corpo.nome, "cor": corpo.cor},
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="tags",
        entidade_id=linha["id"],
        acao="criacao",
        usuario_id=usuario.id,
        depois=dict(linha),
    )
    return _linha_para_json(linha)


@roteador.put("/{tag_id}", summary="Edita uma tag", description="Papel: gestor.")
async def editar(
    tag_id: UUID,
    corpo: TagEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    antes = (
        (
            await conexao.execute(
                text("select id, nome, cor from tags where id = :id"), {"id": str(tag_id)}
            )
        )
        .mappings()
        .first()
    )
    if antes is None:
        raise ErroNaoEncontrado("Tag não encontrada.")

    depois = (
        (
            await conexao.execute(
                text(
                    "update tags set nome = :nome, cor = :cor where id = :id returning id, nome, cor"
                ),
                {"id": str(tag_id), "nome": corpo.nome, "cor": corpo.cor},
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="tags",
        entidade_id=tag_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes=dict(antes),
        depois=dict(depois),
    )
    return _linha_para_json(depois)


@roteador.delete(
    "/{tag_id}", status_code=204, summary="Remove uma tag", description="Papel: gestor."
)
async def remover(
    tag_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> None:
    antes = (
        (
            await conexao.execute(
                text("select id, nome, cor from tags where id = :id"), {"id": str(tag_id)}
            )
        )
        .mappings()
        .first()
    )
    if antes is None:
        raise ErroNaoEncontrado("Tag não encontrada.")

    em_uso = (
        await conexao.execute(
            text("select count(*) from lancamentos_tags where tag_id = :id"), {"id": str(tag_id)}
        )
    ).scalar_one()
    if em_uso:
        # Apagar em cascata tiraria a marcação de lançamentos antigos sem aviso. Tag é
        # dos poucos cadastros sem arquivamento (data-model §3.9), então a saída é
        # obrigar a desmarcar antes.
        raise ErroRegraViolada(
            f"Esta tag está em uso em {em_uso} lançamento(s) e não pode ser removida.",
            requisito="RN-14",
            campos={"tag": "Remova a tag dos lançamentos antes de excluí-la."},
        )

    await conexao.execute(text("delete from tags where id = :id"), {"id": str(tag_id)})
    await registra_auditoria(
        conexao,
        entidade="tags",
        entidade_id=tag_id,
        acao="exclusao",
        usuario_id=usuario.id,
        antes=dict(antes),
    )
