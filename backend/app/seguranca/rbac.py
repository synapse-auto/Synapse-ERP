"""Autorização por papel — `RF-02` e "Padrões Técnicos Obrigatórios" da constituição.

Uso:

    @roteador.get("/api/configuracoes")
    async def ler(usuario = Depends(exige_papel("gestor", "operador"))): ...

    @roteador.put("/api/configuracoes")
    async def gravar(usuario = Depends(exige_papel("gestor"))): ...

**Todo endpoint declara o papel.** Não existe padrão implícito neste módulo de
propósito: se `exige_papel` tivesse um valor padrão, esquecer a dependência viraria
um endpoint aberto sem ninguém notar. Faltando a dependência, o endpoint nem
autentica — o erro aparece na primeira chamada, não em produção seis meses depois.

**Esconder o menu não é autorizar.** `permissoes` de `GET /api/sessao` serve à
navegação; a garantia é o `403` daqui. É a razão de `SC-010` ser verificado duas
vezes: pela tela e chamando a API direto com token de operador (`T138`).

Regra geral (contracts/README.md): **operador** cria e edita lançamentos e lê tudo.
**Gestor** faz o resto — configurações, usuários, cadastros estruturais, clientes e
funcionários.

Tarefa: T031
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends

from app.comum.erros import ErroSemPermissao
from app.config import obter_configuracao
from app.seguranca.auth import Papel, UsuarioAutenticado, usuario_atual

_NOME_DO_PAPEL = {"gestor": "gestor", "operador": "operador"}


def exige_papel(*papeis: Papel) -> Callable[..., Awaitable[UsuarioAutenticado]]:
    """Dependência que exige um dos papéis informados.

    Devolve o usuário autenticado, para o endpoint não precisar declarar duas
    dependências (o papel e o usuário) quando precisa dos dois.
    """
    if not papeis:
        raise ValueError(
            "exige_papel precisa de ao menos um papel. Endpoint sem papel declarado "
            "não passa (constituição, Padrões Técnicos Obrigatórios)."
        )

    aceitos = set(papeis)

    async def verifica(
        usuario: UsuarioAutenticado = Depends(usuario_atual),
    ) -> UsuarioAutenticado:
        if usuario.papel not in aceitos:
            exigido = " ou ".join(_NOME_DO_PAPEL[p] for p in sorted(aceitos))
            raise ErroSemPermissao(
                f"Esta ação é restrita a {exigido}.",
                requisito="RF-02",
            )
        return usuario

    return verifica


def exige_segredo_de_rotina(x_segredo_rotina: str | None = None) -> None:
    """Protege `POST /api/rotinas/*` — contracts/plataforma.md §6.

    O Vercel Cron chama sem usuário logado, então não há token nem papel a verificar;
    a proteção é um segredo compartilhado em cabeçalho, vindo de variável de ambiente
    (Princípio VII).

    A comparação é feita por tempo constante. Comparar segredo com `==` vaza, pelo
    tempo de resposta, quantos caracteres iniciais estavam certos — o que permite
    descobrir o segredo por tentativa. `compare_digest` não tem esse vazamento.
    """
    from secrets import compare_digest

    esperado = obter_configuracao().segredo_rotina
    if not x_segredo_rotina or not compare_digest(x_segredo_rotina, esperado):
        raise ErroSemPermissao(
            "Chamada de rotina não autorizada.",
            requisito="contracts/plataforma.md §6",
        )
