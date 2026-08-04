"""Gestão de usuários — contracts/plataforma.md §2. `FR-102`.

Papel: **gestor** em tudo. É a tela que decide quem entra no sistema.

## Duas travas que não são opcionais

**Nunca existe `DELETE`.** Usuário desativado precisa continuar existindo para a
auditoria apontar para ele (`RF-03`) — apagar a linha deixaria "editado por" apontando
para o nada em todo o histórico dele.

**Rebaixar ou desativar o último gestor ativo é recusado** com `409`. Sem isso, o sistema
fica sem ninguém que possa entrar em Configurações ou convidar alguém — e a saída seria
mexer no banco à mão. A checagem é feita **na mesma transação** da alteração; conferir
antes e gravar depois abriria uma janela para duas requisições simultâneas rebaixarem os
dois últimos gestores.

## O convite passa pelo Supabase Auth

O backend não guarda senha (research.md D-03). Criar usuário é criar no Auth e gravar a
linha em `usuarios` com o **mesmo id**. Se o Auth recusar (e-mail repetido, por exemplo),
nada é gravado aqui.

Tarefa: T129
"""

from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroDaApi, ErroNaoEncontrado, ErroRegraViolada, ErroValidacao
from app.config import obter_configuracao
from app.db import obter_conexao
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/usuarios", tags=["Plataforma"])

Gestor = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

TEMPO_LIMITE_AUTH = httpx.Timeout(15.0)


class ErroDoAuth(ErroDaApi):
    """502 — o Supabase Auth recusou ou não respondeu."""

    status = 502
    codigo = "fonte_externa_indisponivel"


class UsuarioEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    # `EmailStr` do Pydantic exige a dependência `email-validator`, que entraria no
    # pacote da função só para este campo. **Quem valida o e-mail de verdade é o
    # Supabase Auth**, que é onde a conta nasce — e ele recusa antes de qualquer coisa
    # ser gravada aqui. O padrão abaixo pega o erro de digitação óbvio sem custar
    # dependência (plan.md §Constraints).
    email: str = Field(
        min_length=5,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Validado de verdade pelo Supabase Auth, que é onde a conta nasce.",
    )
    papel: Literal["gestor", "operador"] = Field(
        description="`visualizador` não existe na v1 (Out of Scope) → `400 validacao`."
    )


class UsuarioEdicao(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    papel: Literal["gestor", "operador"]


def _para_json(linha: Any) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "nome": linha["nome"],
        "email": linha["email"],
        "papel": linha["papel"],
        "ativo": linha["ativo"],
        "criado_em": linha["criado_em"].isoformat(),
    }


async def _exige(conexao: AsyncConnection, usuario_id: UUID) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text(
                    "select id, nome, email, papel, ativo, criado_em from usuarios where id = :id"
                ),
                {"id": str(usuario_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Usuário não encontrado.")
    return dict(linha)


async def _recusa_deixar_sem_gestor(
    conexao: AsyncConnection, *, alvo: dict[str, Any], acao: str
) -> None:
    """A trava. Roda **na mesma transação** da alteração (ver cabeçalho)."""
    if alvo["papel"] != "gestor" or not alvo["ativo"]:
        return

    outros = (
        await conexao.execute(
            text("select count(*) from usuarios where papel = 'gestor' and ativo and id <> :id"),
            {"id": str(alvo["id"])},
        )
    ).scalar_one()

    if outros == 0:
        raise ErroRegraViolada(
            (
                f"{alvo['nome']} é o único gestor ativo. {acao} deixaria o sistema sem "
                "ninguém que possa entrar em Configurações ou convidar alguém."
            ),
            requisito="FR-102",
            campos={"papel": "Promova outra pessoa a gestor antes."},
        )


async def _cria_no_auth(*, email: str, nome: str) -> UUID:
    """Cria no Supabase Auth e devolve o id, que vira a PK em `usuarios`.

    O usuário nasce **sem senha**, com convite por e-mail: o backend nunca vê senha
    (D-03), e mandar uma senha inicial por outro canal seria pior que o convite.
    """
    configuracao = obter_configuracao()
    try:
        async with httpx.AsyncClient(timeout=TEMPO_LIMITE_AUTH) as cliente:
            resposta = await cliente.post(
                f"{configuracao.supabase_url}/auth/v1/admin/users",
                headers={
                    "Authorization": f"Bearer {configuracao.supabase_service_role_key}",
                    "apikey": configuracao.supabase_service_role_key,
                },
                json={
                    "email": email,
                    "email_confirm": False,
                    "user_metadata": {"nome": nome},
                },
            )
            if resposta.status_code == 422:
                raise ErroValidacao(
                    f"Já existe uma conta com o e-mail {email}.",
                    requisito="FR-102",
                    campos={"email": "E-mail já cadastrado."},
                )
            resposta.raise_for_status()
            return UUID(resposta.json()["id"])
    except ErroDaApi:
        raise
    except (httpx.HTTPError, KeyError, ValueError) as erro:
        raise ErroDoAuth(
            "Não foi possível criar o acesso agora. **Nenhum usuário foi criado** — "
            "tente de novo em instantes.",
            requisito="FR-102",
        ) from erro


@roteador.get("", summary="Lista os usuários", description="Papel: **gestor**.")
async def listar(usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    linhas = (
        (
            await conexao.execute(
                text("""
                    select id, nome, email, papel, ativo, criado_em
                    from usuarios order by ativo desc, lower(nome)
                    """)
            )
        )
        .mappings()
        .all()
    )
    return {
        "itens": [_para_json(linha) for linha in linhas],
        # Vai na resposta para a tela poder desabilitar o botão **antes** de o usuário
        # tentar e levar um 409 (`FR-102`).
        "gestores_ativos": sum(
            1 for linha in linhas if linha["papel"] == "gestor" and linha["ativo"]
        ),
    }


@roteador.post(
    "",
    status_code=201,
    summary="Convida um usuário",
    description=(
        "Papel: **gestor**. Cria no Supabase Auth e a linha em `usuarios`, com o mesmo "
        "id. O backend **não recebe senha** — o convite vai por e-mail (D-03). Se o Auth "
        "recusar, nada é gravado."
    ),
)
async def criar(corpo: UsuarioEntrada, usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    identificador = await _cria_no_auth(email=str(corpo.email), nome=corpo.nome)

    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, :nome, :email, cast(:papel as papel_usuario))
            """),
        {
            "id": str(identificador),
            "nome": corpo.nome,
            "email": str(corpo.email),
            "papel": corpo.papel,
        },
    )
    await registra_auditoria(
        conexao,
        entidade="usuarios",
        entidade_id=identificador,
        acao="criacao",
        usuario_id=usuario.id,
        depois={"nome": corpo.nome, "email": str(corpo.email), "papel": corpo.papel},
    )
    return _para_json(await _exige(conexao, identificador))


@roteador.put(
    "/{usuario_id}",
    summary="Edita nome e papel",
    description=(
        "Papel: **gestor**. Rebaixar o **último gestor ativo** → `409 regra_violada`. "
        "E-mail não muda por aqui: ele é a identidade no Supabase Auth."
    ),
)
async def editar(
    usuario_id: UUID, corpo: UsuarioEdicao, usuario: Gestor, conexao: Conexao
) -> dict[str, Any]:
    alvo = await _exige(conexao, usuario_id)

    if alvo["papel"] == "gestor" and corpo.papel != "gestor":
        await _recusa_deixar_sem_gestor(conexao, alvo=alvo, acao="Rebaixá-lo")

    await conexao.execute(
        text(
            "update usuarios set nome = :nome, papel = cast(:papel as papel_usuario) where id = :id"
        ),
        {"id": str(usuario_id), "nome": corpo.nome, "papel": corpo.papel},
    )
    await registra_auditoria(
        conexao,
        entidade="usuarios",
        entidade_id=usuario_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes={"nome": alvo["nome"], "papel": alvo["papel"]},
        depois={"nome": corpo.nome, "papel": corpo.papel},
    )
    return _para_json(await _exige(conexao, usuario_id))


@roteador.post(
    "/{usuario_id}/desativar",
    summary="Desativa o acesso",
    description=(
        "Papel: **gestor**. `ativo = false` — **nunca `DELETE`**: a auditoria precisa "
        "continuar apontando para ele (`RF-03`). Desativar o último gestor ativo → `409`."
    ),
)
async def desativar(usuario_id: UUID, usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    alvo = await _exige(conexao, usuario_id)
    if not alvo["ativo"]:
        raise ErroRegraViolada(
            f"{alvo['nome']} já está desativado.",
            requisito="FR-102",
            campos={"ativo": "Já desativado."},
        )

    await _recusa_deixar_sem_gestor(conexao, alvo=alvo, acao="Desativá-lo")

    await conexao.execute(
        text("update usuarios set ativo = false where id = :id"), {"id": str(usuario_id)}
    )
    await registra_auditoria(
        conexao,
        entidade="usuarios",
        entidade_id=usuario_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={"ativo": {"de": True, "para": False}},
    )
    return _para_json(await _exige(conexao, usuario_id))


@roteador.post(
    "/{usuario_id}/reativar",
    summary="Reativa o acesso",
    description="Papel: **gestor**.",
)
async def reativar(usuario_id: UUID, usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    alvo = await _exige(conexao, usuario_id)
    if alvo["ativo"]:
        raise ErroRegraViolada(
            f"{alvo['nome']} já está ativo.", requisito="FR-102", campos={"ativo": "Já ativo."}
        )

    await conexao.execute(
        text("update usuarios set ativo = true where id = :id"), {"id": str(usuario_id)}
    )
    await registra_auditoria(
        conexao,
        entidade="usuarios",
        entidade_id=usuario_id,
        acao="restauracao",
        usuario_id=usuario.id,
        alteracoes={"ativo": {"de": False, "para": True}},
    )
    return _para_json(await _exige(conexao, usuario_id))
