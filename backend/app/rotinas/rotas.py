"""Endpoints das rotinas automáticas — contracts/plataforma.md §6.

**Estes endpoints não usam JWT.** Quem chama é o Vercel Cron, e não há usuário na
chamada. A proteção é um segredo compartilhado no cabeçalho `X-Segredo-Rotina`,
guardado em variável de ambiente (Princípio VII, research.md D-08).

`GET /api/rotinas/estado` é o contrário: é gestor logado olhando se a automação rodou.
Existe porque o Princípio VI não aceita "a rotina funciona" como afirmação — a resposta
mostra a última execução e o que ela fez.

Tarefa: T084
"""

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroNaoAutenticado
from app.config import obter_configuracao
from app.db import obter_conexao
from app.rotinas import diaria, semanal
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/rotinas", tags=["Rotinas"])

Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]
Gestor = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))]


async def exige_segredo_da_rotina(
    x_segredo_rotina: Annotated[str | None, Header(alias="X-Segredo-Rotina")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Autenticação da máquina, não da pessoa. Aceita **dois** cabeçalhos.

    `X-Segredo-Rotina` é o que `contracts/plataforma.md §6` especifica, e é o caminho do
    disparo manual. `Authorization: Bearer <segredo>` existe porque o **Vercel Cron não
    envia cabeçalho personalizado**: ele chama o caminho e manda
    `Authorization: Bearer $CRON_SECRET`. Aceitar só o primeiro deixaria o cron sem
    conseguir se autenticar — divergência entre o contrato e a plataforma, registrada no
    README do backend.

    Os dois conferem o **mesmo** segredo. Na Vercel, `CRON_SECRET` e `SEGREDO_ROTINA`
    recebem o mesmo valor.

    `compare_digest` em vez de `==`: a comparação normal para no primeiro byte
    diferente, e o tempo que ela leva conta quantos bytes iniciais estavam certos. Para
    um segredo que fica exposto num endpoint público, isso é adivinhável.
    """
    esperado = obter_configuracao().segredo_rotina

    recebido = x_segredo_rotina
    if not recebido and authorization and authorization.lower().startswith("bearer "):
        recebido = authorization[7:].strip()

    if not recebido or not hmac.compare_digest(recebido, esperado):
        raise ErroNaoAutenticado(
            "Chamada de rotina sem o segredo correto.",
            requisito="D-08",
            campos={"X-Segredo-Rotina": "Cabeçalho ausente ou inválido."},
        )


@roteador.post(
    "/diaria",
    summary="Materializa recorrências e aplica o ciclo de status",
    description=(
        "Chamado pelo **Vercel Cron**, sem usuário. Protegido por `X-Segredo-Rotina`. "
        "**Idempotente**: rodar duas vezes no mesmo dia não duplica nada. **Recupera "
        "dia perdido**: cada passo traz o estado até hoje, então um cron falho é "
        "coberto na execução seguinte (research.md D-08)."
    ),
    dependencies=[Depends(exige_segredo_da_rotina)],
)
async def rodar_diaria(conexao: Conexao) -> dict[str, Any]:
    return await diaria.executa(conexao)


@roteador.get(
    "/diaria",
    summary="O mesmo, para o Vercel Cron (que só faz GET)",
    description=(
        "Existe porque o **Vercel Cron invoca o caminho com `GET`** e não envia "
        "cabeçalho personalizado — ele manda `Authorization: Bearer $CRON_SECRET`. "
        "Mesmo segredo, mesmo efeito, mesma idempotência do `POST`. Divergência entre o "
        "contrato e a plataforma, registrada no README do backend e em "
        "contracts/plataforma.md §6."
    ),
    dependencies=[Depends(exige_segredo_da_rotina)],
)
async def rodar_diaria_pelo_cron(conexao: Conexao) -> dict[str, Any]:
    return await diaria.executa(conexao)


@roteador.post(
    "/semanal",
    summary="Resumo da semana e alerta de caixa baixo",
    description=(
        "Protegido por `X-Segredo-Rotina`. `FR-098`, `FR-099`. **Não tem cron próprio**: "
        "o plano gratuito da Vercel dá um cron por dia, então a rotina diária dispara "
        "esta ao detectar que é segunda-feira. Este endpoint existe para disparo manual "
        "— é o que permite conferir o resumo sem esperar a próxima segunda. Idempotente "
        "por semana ISO."
    ),
    dependencies=[Depends(exige_segredo_da_rotina)],
)
async def rodar_semanal(conexao: Conexao) -> dict[str, Any]:
    return await semanal.executa(conexao)


@roteador.get(
    "/estado",
    summary="Quando a rotina rodou e o que ela fez",
    description=(
        "Papel: **gestor**. Princípio VI: sem isto, "
        '"a automação está funcionando" seria afirmação sem como conferir.'
    ),
)
async def estado(usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    linhas = (await conexao.execute(text("""
                    select nome, ultima_execucao_em, ultima_data_processada, ultimo_resultado
                    from execucoes_rotina order by nome
                    """))).mappings().all()
    return {
        "itens": [
            {
                "nome": linha["nome"],
                "ultima_execucao_em": linha["ultima_execucao_em"].isoformat(),
                "ultima_data_processada": linha["ultima_data_processada"].isoformat(),
                "ultimo_resultado": linha["ultimo_resultado"],
            }
            for linha in linhas
        ],
        # Lista vazia é resposta legítima e precisa ser distinguível de erro: significa
        # que a rotina **nunca** rodou, que é exatamente o que se quer descobrir logo
        # depois de publicar.
        "nunca_executada": not linhas,
    }
