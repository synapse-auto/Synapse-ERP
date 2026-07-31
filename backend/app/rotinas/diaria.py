"""Rotina diária — materializa recorrências e aplica o ciclo de status (D-08).

Skill `supabase-postgres-best-practices` acionada antes das consultas (task 🟢 T083).

## As três propriedades que esta rotina precisa ter

**1. Idempotente.** Rodar duas vezes no mesmo dia não pode duplicar nada. Não é
disciplina, é consequência do desenho: cada passo pergunta "qual é o estado correto
hoje?" e grava a diferença, em vez de "avance um dia". A materialização se apoia no
índice único `(recorrencia_id, data)` (migração `010`); o ciclo de status só troca
linhas cujo status atual está errado para a data de hoje.

**2. Recupera dia perdido.** O cron do plano gratuito roda uma vez por dia e pode
falhar. Como cada passo traz o estado **até hoje** — e não "processa o dia seguinte" —,
um dia perdido some sozinho na execução seguinte. `ultima_data_processada` existe para
o relato dizer o que houve, não porque o cálculo dependa dela.

**3. Verificável.** `execucoes_rotina.ultimo_resultado` guarda o que a rotina de fato
fez. Sem isso, "a automação funcionou" seria afirmação, e o Princípio VI proíbe
afirmar o que não se pode conferir. É o que `GET /api/rotinas/estado` devolve.

## O que ainda não está aqui

Inadimplência (`RN-10`), alertas de vencimento e caixa baixo são da sub-fase B6
(T125–T127). O resultado já traz os contadores zerados para o contrato não mudar de
forma quando eles chegarem.

Tarefa: T083
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.recorrencias import repositorio as repositorio_recorrencias
from app.recorrencias import servico as servico_recorrencias

registrador = logging.getLogger("synapse.erp.rotina")

NOME = "diaria"

# Teto de recorrências materializadas por execução. Guarda da plataforma: com muitas
# séries longas, a rotina pararia no meio pelo corte de duração da Vercel e o relato
# mentiria. Parando por conta própria, ela grava o que fez e a execução seguinte
# continua — `gerada_ate` é o cursor (D-02a).
MAXIMO_DE_RECORRENCIAS_POR_EXECUCAO = 100


@dataclass
class Resultado:
    """O que a rotina fez. Vira `execucoes_rotina.ultimo_resultado` e a resposta."""

    ocorrencias_geradas: int = 0
    efetivados_automaticamente: int = 0
    movidos_para_pendente: int = 0
    movidos_para_atrasado: int = 0
    recorrencias_processadas: int = 0
    recorrencias_pendentes_de_geracao: int = 0
    # Chegam em B6 (T125–T127). Já declarados para o contrato não mudar de forma.
    clientes_marcados_inadimplentes: int = 0
    notificacoes_criadas: int = 0
    avisos: list[str] = field(default_factory=list)


async def _estado(conexao: AsyncConnection) -> dict[str, Any] | None:
    linha = (
        (
            await conexao.execute(
                text(
                    "select nome, ultima_execucao_em, ultima_data_processada, ultimo_resultado "
                    "from execucoes_rotina where nome = :nome"
                ),
                {"nome": NOME},
            )
        )
        .mappings()
        .first()
    )
    return dict(linha) if linha else None


async def ja_rodou_hoje(conexao: AsyncConnection, hoje: date | None = None) -> bool:
    """Usado pela chamada implícita (T085) para não repetir trabalho a cada leitura."""
    estado = await _estado(conexao)
    return estado is not None and estado["ultima_data_processada"] >= (hoje or date.today())


async def _grava_estado(
    conexao: AsyncConnection, *, processada: date, resultado: Resultado
) -> None:
    await conexao.execute(
        text("""
            insert into execucoes_rotina (
              nome, ultima_execucao_em, ultima_data_processada, ultimo_resultado
            ) values (:nome, now(), :processada, cast(:resultado as jsonb))
            on conflict (nome) do update set
              ultima_execucao_em = now(),
              ultima_data_processada = excluded.ultima_data_processada,
              ultimo_resultado = excluded.ultimo_resultado
            """),
        {
            "nome": NOME,
            "processada": processada,
            "resultado": json.dumps(asdict(resultado), ensure_ascii=False),
        },
    )


# ── Passo 1 — materializar as recorrências ──────────────────────────────────


async def _materializa_recorrencias(
    conexao: AsyncConnection, resultado: Resultado, *, hoje: date, usuario_sistema: UUID | None
) -> None:
    ate = await servico_recorrencias.horizonte_configurado(conexao, hoje)
    pendentes = await repositorio_recorrencias.a_materializar(conexao, ate=ate)

    for linha in pendentes[:MAXIMO_DE_RECORRENCIAS_POR_EXECUCAO]:
        # O autor da ocorrência é quem criou a regra. Atribuir a rotina exigiria um
        # usuário-robô em `usuarios` e faria a auditoria dizer "criado pelo sistema"
        # onde a resposta útil é "criado pela regra que fulano cadastrou".
        geracao = await servico_recorrencias.materializa(
            conexao,
            linha,
            usuario_id=usuario_sistema or linha["criado_por"],
            ate=ate,
            hoje=hoje,
        )
        resultado.ocorrencias_geradas += geracao.geradas
        resultado.recorrencias_processadas += 1
        if not geracao.concluida:
            resultado.recorrencias_pendentes_de_geracao += 1

    if len(pendentes) > MAXIMO_DE_RECORRENCIAS_POR_EXECUCAO:
        sobra = len(pendentes) - MAXIMO_DE_RECORRENCIAS_POR_EXECUCAO
        resultado.avisos.append(
            f"{sobra} recorrências ficaram para a próxima execução (teto por invocação)."
        )


# ── Passo 2 — aplicar o ciclo de status (`RN-03`, `RN-04`) ──────────────────


async def _aplica_ciclo_de_status(
    conexao: AsyncConnection, resultado: Resultado, *, hoje: date
) -> None:
    """Três `UPDATE` em conjunto, não um laço linha a linha.

    Poderia ser `for lancamento in ...: status_na_data(...)`, e seria mais legível. Não
    é o que está aqui porque a rotina roda contra milhares de linhas numa função com
    duração limitada — e as três transições são exatamente expressáveis em SQL. O
    módulo de domínio continua sendo o dono da regra; estes `UPDATE` são a **mesma**
    regra, e o teste de unidade de `status.py` mais o de integração da rotina existem
    justamente para as duas versões não divergirem.
    """
    # programado + data chegou + automático → efetivado
    efetivados = await conexao.execute(
        text("""
            update lancamentos
            set status = 'efetivado', efetivado_em = now(), efetivado_por = criado_por
            where status = 'programado' and data <= :hoje
              and efetivar_automaticamente and excluido_em is null
            """),
        {"hoje": hoje},
    )
    resultado.efetivados_automaticamente = efetivados.rowcount or 0

    # programado + data chegou + manual → pendente (espera confirmação de 1 clique)
    pendentes = await conexao.execute(
        text("""
            update lancamentos set status = 'pendente'
            where status = 'programado' and data <= :hoje
              and not efetivar_automaticamente and excluido_em is null
            """),
        {"hoje": hoje},
    )
    resultado.movidos_para_pendente = pendentes.rowcount or 0

    # pendente + passou do vencimento → atrasado.
    # `data < hoje`, não `<=`: vencer hoje não é atrasar, o dia ainda não acabou.
    atrasados = await conexao.execute(
        text("""
            update lancamentos set status = 'atrasado'
            where status = 'pendente' and data < :hoje and excluido_em is null
            """),
        {"hoje": hoje},
    )
    resultado.movidos_para_atrasado = atrasados.rowcount or 0


# ── Execução ────────────────────────────────────────────────────────────────


async def executa(
    conexao: AsyncConnection, *, hoje: date | None = None, usuario_sistema: UUID | None = None
) -> dict[str, Any]:
    """Roda a rotina e devolve o corpo de contracts/plataforma.md §6."""
    hoje = hoje or date.today()
    comeco = time.monotonic()

    estado = await _estado(conexao)
    ja_executada = estado is not None and estado["ultima_data_processada"] >= hoje

    resultado = Resultado()
    await _materializa_recorrencias(conexao, resultado, hoje=hoje, usuario_sistema=usuario_sistema)
    await _aplica_ciclo_de_status(conexao, resultado, hoje=hoje)

    if estado is not None and estado["ultima_data_processada"] < hoje:
        dias = (hoje - estado["ultima_data_processada"]).days
        if dias > 1:
            # Não é erro: é o desenho funcionando. Fica no relato para quem olhar
            # `GET /api/rotinas/estado` saber que houve um buraco e que ele foi coberto.
            resultado.avisos.append(
                f"{dias} dias desde a última execução — o período foi recuperado nesta."
            )

    await _grava_estado(conexao, processada=hoje, resultado=resultado)
    registrador.info("rotina diaria: %s", asdict(resultado))

    return {
        "data_processada": hoje.isoformat(),
        "ja_executada_hoje": ja_executada,
        "resultado": asdict(resultado),
        "duracao_ms": int((time.monotonic() - comeco) * 1000),
    }


async def executa_se_necessario(conexao: AsyncConnection, hoje: date | None = None) -> None:
    """Chamada implícita de T085: garante que a leitura não mostre número velho.

    Um cron que falhou não pode virar Dashboard errado. A primeira leitura do dia
    dispara a rotina antes de responder (contracts/plataforma.md §6).

    **Falha aqui não derruba a leitura.** Se a materialização quebrar, o usuário
    prefere ver os números de ontem a ver um erro no lugar do Dashboard — e o problema
    aparece em `GET /api/rotinas/estado`, que é onde se olha para isso.
    """
    try:
        if await ja_rodou_hoje(conexao, hoje):
            return
        await executa(conexao, hoje=hoje)
    except Exception:  # noqa: BLE001 — ver docstring
        registrador.exception("rotina diária implícita falhou; a leitura segue com o que há")
