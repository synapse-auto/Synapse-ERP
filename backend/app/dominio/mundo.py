"""`RN-15` — mundo obrigatório e imutável. Módulo dono da regra (Princípio III).

Separação em dois braços do negócio: **Synapse Digital** (CRM, automação com IA,
desenvolvimento web) e **Synapse Infra** (redes, segurança, energia solar, ar
condicionado, LED, racks). `SC-005` exige zero vazamento entre os dois.

## As quatro exceções

`RN-15` foi atualizado em 2026-07-30: são **quatro** entidades sem `mundo`, não uma.

| Entidade | Por quê |
|---|---|
| `categorias`, `subcategorias` | `RF-104`: compartilhadas, para não duplicar |
| `tags` | `RF-103` não as lista nos formulários com campo Mundo |
| `clientes` | D-04, decisão do dono do projeto — cadastro único |

A de `clientes` tem consequência: o filtro "clientes do mundo X" é **derivado da
movimentação**, e cliente sem lançamento aparece nos três estados do seletor. Isso
mora em `app/clientes/repositorio.py`, não aqui.

## Duas camadas para a imutabilidade

Este módulo recusa a alteração **antes** de chegar ao banco, para a mensagem sair em
PT-BR com o requisito citado. O gatilho `recusa_alteracao_de_mundo` recusa de novo, no
banco, com SQLSTATE `RN015` — é a rede embaixo, para o caso de algum caminho de código
esquecer de perguntar. `traduz_erro_do_banco` converte essa rede em erro de negócio,
para o usuário nunca ver texto de Postgres.

Tarefa: T043
"""

from collections.abc import Iterable
from typing import Any, Literal

from app.comum.erros import ErroRegraViolada, ErroValidacao

Mundo = Literal["digital", "infra"]

MUNDOS: tuple[str, ...] = ("digital", "infra")

# Rótulo para mensagem e para a interface (`RF-100`).
ROTULOS: dict[str, str] = {"digital": "Synapse Digital", "infra": "Synapse Infra"}

# SQLSTATE próprio do gatilho — ver migracoes/004_lancamentos.sql.
SQLSTATE_MUNDO_IMUTAVEL = "RN015"

# Onde `mundo` existe (data-model §1).
ENTIDADES_COM_MUNDO: frozenset[str] = frozenset(
    {"lancamentos", "recorrencias", "parcelamentos", "funcionarios", "servicos", "centros_custo"}
)

# As exceções documentadas. Explícito de propósito: uma entidade nova que não esteja em
# nenhuma das duas listas levanta erro em `exige`, em vez de nascer sem mundo em silêncio.
ENTIDADES_SEM_MUNDO: frozenset[str] = frozenset(
    {
        "categorias",
        "subcategorias",
        "tags",
        "clientes",
        # plataforma
        "usuarios",
        "configuracoes",
        "auditoria",
        "cotacoes_cambio",
        "execucoes_rotina",
        "notificacoes",
        "clientes_servicos",
        "lancamentos_tags",
        "anexos",
    }
)


def tem_mundo(entidade: str) -> bool:
    """A entidade carrega a coluna `mundo`?"""
    if entidade in ENTIDADES_COM_MUNDO:
        return True
    if entidade in ENTIDADES_SEM_MUNDO:
        return False
    raise ValueError(
        f"Entidade '{entidade}' não está classificada em RN-15. Declare-a em "
        "ENTIDADES_COM_MUNDO ou ENTIDADES_SEM_MUNDO antes de usar — silêncio aqui "
        "viraria dado financeiro sem mundo."
    )


def resolve_filtro(mundo: str | None) -> list[str]:
    """Traduz o parâmetro `?mundo=` na lista de mundos a consultar.

    Ausente = `ambos` (contracts/README.md). Nunca inferido do último uso no servidor:
    o cliente sempre manda, senão duas abas abertas em mundos diferentes se
    atrapalhariam.
    """
    if mundo is None or mundo == "ambos":
        return list(MUNDOS)
    if mundo in MUNDOS:
        return [mundo]
    raise ErroValidacao(
        f"Mundo '{mundo}' não existe.",
        requisito="RN-15",
        campos={"mundo": f"Valores aceitos: {', '.join(MUNDOS)}, ambos."},
    )


def deve_quebrar_por_mundo(mundo: str | None) -> bool:
    """No modo "Ambos", o consolidado vem com a quebra (`FR-003`, `RF-102`)."""
    return mundo is None or mundo == "ambos"


def filtra(linhas: Iterable[dict[str, Any]], mundo: str | None) -> list[dict[str, Any]]:
    """Filtra em memória. O filtro de verdade é no SQL — este serve a agregação já lida.

    Linha com `mundo` nulo **não passa em nenhum filtro**, nem no "ambos": dado
    financeiro sem mundo é corrompido, não "de ambos os mundos". Deixá-lo passar no
    consolidado esconderia o problema justamente na visão que soma tudo.
    """
    aceitos = set(resolve_filtro(mundo))
    return [linha for linha in linhas if linha.get("mundo") in aceitos]


def exige(entidade: str, mundo: str | None) -> str | None:
    """Valida o `mundo` na criação, conforme a entidade tenha ou não a coluna."""
    if not tem_mundo(entidade):
        return None

    if mundo is None:
        raise ErroValidacao(
            "Escolha o mundo: Synapse Digital ou Synapse Infra.",
            requisito="RN-15",
            campos={"mundo": "Obrigatório e não pode ser alterado depois."},
        )
    if mundo not in MUNDOS:
        raise ErroValidacao(
            f"Mundo '{mundo}' não existe.",
            requisito="RN-15",
            campos={"mundo": f"Valores aceitos: {', '.join(MUNDOS)}."},
        )
    return mundo


def recusa_alteracao(mundo_atual: str, mundo_novo: str | None) -> None:
    """Recusa mudança de `mundo` na edição (`FR-005`).

    `mundo_novo` nulo ou igual ao atual **não** é alteração — o `PUT` reenvia o corpo
    inteiro, e transformar isso em erro impediria qualquer edição.
    """
    if mundo_novo is None or mundo_novo == mundo_atual:
        return
    raise ErroRegraViolada(
        (
            f"O mundo não pode ser alterado depois de criado. "
            f"Este lançamento é de {ROTULOS.get(mundo_atual, mundo_atual)}. "
            f"Para mudar, exclua e crie de novo no outro mundo."
        ),
        requisito="RN-15",
        campos={"mundo": "Campo imutável."},
    )


def traduz_erro_do_banco(erro: Exception) -> ErroRegraViolada | None:
    """Converte o erro do gatilho em erro de negócio, ou `None` se não for esse caso.

    Devolver `None` em vez de levantar é deliberado: quem chama decide o que fazer com
    os outros erros de banco, e engolir um erro desconhecido aqui esconderia defeito.
    """
    sqlstate = getattr(erro, "sqlstate", None) or getattr(erro, "pgcode", None)
    if sqlstate != SQLSTATE_MUNDO_IMUTAVEL:
        # asyncpg embrulha a exceção original dentro de `__cause__`.
        causa = getattr(erro, "__cause__", None)
        if causa is None:
            return None
        sqlstate = getattr(causa, "sqlstate", None) or getattr(causa, "pgcode", None)
        if sqlstate != SQLSTATE_MUNDO_IMUTAVEL:
            return None

    return ErroRegraViolada(
        "O mundo não pode ser alterado depois de criado.",
        requisito="RN-15",
        campos={"mundo": "Campo imutável."},
    )
