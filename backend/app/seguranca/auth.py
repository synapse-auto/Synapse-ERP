"""Autenticação: valida o token do Supabase e carrega o usuário — research.md D-03.

**Divisão de responsabilidade**: o Supabase Auth diz *quem* é (identidade); este
backend diz *o que pode* (autorização, em `rbac.py`). Escrever autenticação à mão
seria reinventar a roda mais arriscada que existe (Princípio II); autorização é o que
**não** se delega, porque `RF-02` e a constituição exigem papel declarado por
endpoint, verificável e testável.

## Modo de assinatura: resolvido

research.md D-03 deixou em aberto: "o Supabase migrou para JWT assimétrico (JWKS)
mantendo o segredo compartilhado legado; conferir no painel antes de escrever o
validador, não assumir."

**Conferido em 2026-07-30** no próprio projeto:
`GET /auth/v1/.well-known/jwks.json` devolve uma chave `kty=EC`, `alg=ES256`,
`kid=cc3b24c9-…`. O projeto usa **chave assimétrica**.

Consequências:

- Só ES256 é aceito. Nenhum caminho HS256 foi escrito — implementar um segundo modo
  sem uso real contraria o Princípio I, e "aceitar qualquer algoritmo que o token
  disser" é a falha clássica de validação de JWT.
- Não existe segredo de JWT em variável de ambiente. O que se busca é **chave
  pública**; por isso `SUPABASE_JWT_MODO` e `SUPABASE_JWT_SEGREDO` saíram do
  `.env.exemplo`.
- Se o projeto algum dia voltar ao segredo compartilhado, o JWKS fica vazio e todo
  token passa a ser recusado com mensagem clara — falha fechada, não aberta.

## O usuário tem que existir em `usuarios`

Token válido **não basta**. O papel mora na nossa tabela, não no token: quem se
cadastrasse sozinho no Auth teria token e nenhuma linha em `usuarios`, e recebe 401.
`ativo = false` também recebe 401 — desativar é a forma de tirar acesso, já que
usuário nunca é excluído (`RF-03`).

Tarefa: T030
"""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import jwt
from fastapi import Depends, Request
from jwt import PyJWKClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroNaoAutenticado
from app.config import Configuracao, obter_configuracao
from app.db import obter_conexao

ALGORITMOS = ["ES256"]

Papel = Literal["gestor", "operador"]

_cliente_jwks: PyJWKClient | None = None


def _obter_cliente_jwks(configuracao: Configuracao) -> PyJWKClient:
    """Cliente de chaves públicas, com cache.

    `PyJWKClient` guarda as chaves em memória, então o processo quente não vai à rede
    a cada requisição. `lifespan=300` faz a chave ser rebuscada de tempo em tempo, o
    que é o que permite ao Supabase rotacionar a chave sem derrubar o backend.
    """
    global _cliente_jwks
    if _cliente_jwks is None:
        _cliente_jwks = PyJWKClient(
            configuracao.url_jwks,
            cache_keys=True,
            max_cached_keys=8,
            lifespan=300,
        )
    return _cliente_jwks


@dataclass(frozen=True)
class UsuarioAutenticado:
    """Quem está chamando. Montado do token + da linha em `usuarios`."""

    id: UUID
    nome: str
    email: str
    papel: Papel
    preferencias: dict[str, Any]

    @property
    def e_gestor(self) -> bool:
        return self.papel == "gestor"

    def permissoes(self) -> dict[str, bool]:
        """O que a navegação pode mostrar — contracts/plataforma.md §1.

        Booleano explícito, vindo do servidor. O frontend esconde o menu a partir
        disto, mas **esconder não é autorizar**: cada endpoint valida o papel de novo
        (`rbac.py`). É por isso que `SC-010` se verifica duas vezes, pela tela e pela
        API direta.
        """
        return {
            "configuracoes": self.e_gestor,
            "usuarios": self.e_gestor,
            "cadastros": self.e_gestor,
            "lancamentos": True,
        }


def _extrai_token(request: Request) -> str:
    autorizacao = request.headers.get("Authorization", "")
    esquema, _, token = autorizacao.partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        raise ErroNaoAutenticado("Faça login para continuar.")
    return token.strip()


def valida_token(token: str, configuracao: Configuracao) -> dict[str, Any]:
    """Confere assinatura, validade e destinatário do token.

    `audience="authenticated"` e a checagem de `iss` não são detalhe: sem elas, um
    token legítimo emitido por outro projeto Supabase seria aceito aqui.
    """
    try:
        chave = _obter_cliente_jwks(configuracao).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            chave.key,
            algorithms=ALGORITMOS,
            audience="authenticated",
            issuer=f"{configuracao.supabase_url}/auth/v1",
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.ExpiredSignatureError as erro:
        raise ErroNaoAutenticado("Sua sessão expirou. Entre novamente.") from erro
    except jwt.InvalidAudienceError as erro:
        raise ErroNaoAutenticado("Token não pertence a este sistema.") from erro
    except jwt.InvalidIssuerError as erro:
        raise ErroNaoAutenticado("Token não pertence a este sistema.") from erro
    except jwt.PyJWKClientError as erro:
        # JWKS vazio ou fora do ar. Falha FECHADA, de propósito.
        raise ErroNaoAutenticado(
            "Não foi possível verificar sua sessão agora. Tente de novo em instantes."
        ) from erro
    except jwt.InvalidTokenError as erro:
        raise ErroNaoAutenticado("Sessão inválida. Entre novamente.") from erro


def dados_do_token(request: Request) -> dict[str, Any]:
    """Valida o token **sem tocar o banco**.

    Existe separado de `usuario_atual` por causa da ordem em que o FastAPI resolve
    dependências: ele resolve na ordem da assinatura e para na primeira que levanta.
    Enquanto a conexão era dependência direta de `usuario_atual`, toda requisição sem
    token abria uma conexão com o Postgres antes de descobrir que ia recusar — dois
    problemas de uma vez: conexão gasta com requisição de robô, e `401` virando `500`
    quando o banco está fora do ar.

    Vindo primeiro na assinatura, token ruim é recusado antes de o banco ser tocado.
    """
    return valida_token(_extrai_token(request), obter_configuracao())


async def usuario_atual(
    dados: dict[str, Any] = Depends(dados_do_token),
    conexao: AsyncConnection = Depends(obter_conexao),
) -> UsuarioAutenticado:
    """Dependência do FastAPI: exige token válido e usuário ativo em `usuarios`.

    A ordem dos parâmetros é significativa — ver `dados_do_token`.
    """
    id_do_token = dados.get("sub")
    if not id_do_token:
        raise ErroNaoAutenticado("Sessão inválida. Entre novamente.")

    linha = (
        (
            await conexao.execute(
                text("""
                select id, nome, email, papel, preferencias
                from usuarios
                where id = cast(:id as uuid) and ativo
                """),
                {"id": id_do_token},
            )
        )
        .mappings()
        .first()
    )

    if linha is None:
        # Cobre três casos de propósito com a mesma resposta: nunca convidado,
        # desativado, ou a linha `Sistema` (que é `ativo = false`). Distinguir
        # contaria a quem tentou qual dos três é.
        raise ErroNaoAutenticado(
            "Sua conta não tem acesso a este sistema. Peça um convite a um gestor."
        )

    return UsuarioAutenticado(
        id=linha["id"],
        nome=linha["nome"],
        email=linha["email"],
        papel=linha["papel"],
        preferencias=linha["preferencias"] or {},
    )
