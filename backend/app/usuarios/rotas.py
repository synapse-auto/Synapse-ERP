"""Sessão do usuário — contracts/plataforma.md §1.

O login acontece pelo Supabase Auth direto do navegador (research.md D-03): **nenhum
endpoint deste backend recebe senha**. Estes dois fecham o ciclo — quem sou eu, o que
posso, e onde guardo minhas preferências.

As 5 rotas de gestão de usuários (§2 do contrato) ficam em `T129`, sub-fase B6.

Tarefa: T034
"""

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroValidacao
from app.db import obter_conexao
from app.seguranca.auth import UsuarioAutenticado, usuario_atual

roteador = APIRouter(prefix="/api/sessao", tags=["Sessão"])

Tema = Literal["claro", "escuro", "auto"]


class CardDoDashboard(BaseModel):
    id: str = Field(description="Id do card, conferido contra dashboard_cards_disponiveis.")
    visivel: bool = Field(default=True)
    ordem: int = Field(ge=0)


class Preferencias(BaseModel):
    """Corpo de `POST /api/sessao/preferencias` (`FR-071`, `FR-109`)."""

    tema: Tema | None = Field(default=None)
    dashboard_cards: list[CardDoDashboard] | None = Field(default=None)


async def _ids_de_card_conhecidos(conexao: AsyncConnection) -> set[str]:
    """Ids válidos, lidos de `configuracoes.dashboard_cards_disponiveis`.

    A lista vive no banco (`FR-106`, Princípio VII). Nenhum id de card escrito neste
    arquivo — promover um card novo é gravar uma linha, não editar código.
    """
    linha = (
        await conexao.execute(
            text("select valor from configuracoes where chave = 'dashboard_cards_disponiveis'")
        )
    ).scalar_one_or_none()
    if not linha:
        return set()
    return {str(card["id"]) for card in linha}


async def _tema_padrao(conexao: AsyncConnection) -> str:
    linha = (
        await conexao.execute(text("select valor from configuracoes where chave = 'tema_padrao'"))
    ).scalar_one_or_none()
    return str(linha) if linha else "auto"


@roteador.get(
    "",
    summary="Quem sou eu, o que posso, minhas preferências",
    description=(
        "Autenticado (qualquer papel). `permissoes` é booleano explícito vindo do "
        "servidor — o frontend esconde a navegação a partir disso, mas **esconder não é "
        "autorizar**: cada endpoint valida o papel de novo (`RF-02`)."
    ),
)
async def ler_sessao(
    usuario: Annotated[UsuarioAutenticado, Depends(usuario_atual)],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    nao_lidas = (
        await conexao.execute(
            text("""
                select count(*) from notificacoes
                where usuario_id = :usuario_id and lida_em is null
                """),
            {"usuario_id": str(usuario.id)},
        )
    ).scalar_one()

    preferencias = dict(usuario.preferencias)
    if not preferencias.get("tema"):
        preferencias["tema"] = await _tema_padrao(conexao)
    preferencias.setdefault("dashboard_cards", [])

    return {
        "usuario": {
            "id": str(usuario.id),
            "nome": usuario.nome,
            "email": usuario.email,
            "papel": usuario.papel,
        },
        "permissoes": usuario.permissoes(),
        "preferencias": preferencias,
        "notificacoes_nao_lidas": nao_lidas,
    }


@roteador.post(
    "/preferencias",
    summary="Salva tema e arranjo de cards",
    description=(
        "Autenticado (qualquer papel). Persiste **por usuário**, não global. Id de card "
        "desconhecido é recusado contra `configuracoes.dashboard_cards_disponiveis` → "
        "`400 validacao`."
    ),
)
async def salvar_preferencias(
    corpo: Preferencias,
    usuario: Annotated[UsuarioAutenticado, Depends(usuario_atual)],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    if corpo.tema is None and corpo.dashboard_cards is None:
        raise ErroValidacao(
            "Informe o tema, o arranjo de cards, ou os dois.",
            campos={"corpo": "Nada a salvar."},
        )

    # Escrita parcial: mandar só `tema` não deve apagar o arranjo de cards, e
    # vice-versa. Por isso parte-se do que já está gravado.
    preferencias = dict(usuario.preferencias)

    if corpo.tema is not None:
        preferencias["tema"] = corpo.tema

    if corpo.dashboard_cards is not None:
        conhecidos = await _ids_de_card_conhecidos(conexao)
        recebidos = [card.id for card in corpo.dashboard_cards]

        desconhecidos = sorted(set(recebidos) - conhecidos)
        if desconhecidos:
            raise ErroValidacao(
                f"Estes cards não existem: {', '.join(desconhecidos)}.",
                requisito="FR-106",
                campos={"dashboard_cards": "Id de card não reconhecido."},
            )

        repetidos = sorted({carta for carta in recebidos if recebidos.count(carta) > 1})
        if repetidos:
            raise ErroValidacao(
                f"Estes cards aparecem mais de uma vez: {', '.join(repetidos)}.",
                campos={"dashboard_cards": "Cada card pode aparecer uma única vez."},
            )

        preferencias["dashboard_cards"] = [
            card.model_dump() for card in sorted(corpo.dashboard_cards, key=lambda c: c.ordem)
        ]

    await conexao.execute(
        text("update usuarios set preferencias = cast(:preferencias as jsonb) where id = :id"),
        {"preferencias": json.dumps(preferencias, ensure_ascii=False), "id": str(usuario.id)},
    )

    # Preferência de interface não entra em `auditoria` de propósito: a tabela existe
    # para rastrear mudança de dado financeiro (`RF-03`), e encher a linha do tempo
    # com "trocou o tema" atrapalharia quem a lê para conferir dinheiro.
    return {"preferencias": preferencias}
