"""Rotina semanal — resumo de segunda e alerta de caixa baixo. `FR-098`, `FR-099`.

## Por que ela não tem cron próprio

O plano gratuito da Vercel limita os crons a **uma execução diária** (plan.md
§Constraints). Em vez de pedir um cron semanal que a plataforma não dá, a rotina diária
chama esta ao detectar que é segunda-feira — e a `chave_deduplicacao` por semana ISO
garante que rodar cinco vezes na mesma segunda produza um resumo só.

`POST /api/rotinas/semanal` existe para disparo manual: é o que permite conferir o
resumo sem esperar a próxima segunda (Princípio VI).

## O caixa baixo é diferente do semáforo do Dashboard

O semáforo (`RF-46b`) olha 30 dias e classifica em três faixas. Este alerta olha
`configuracoes.caixa_baixo_horizonte_dias` (7, por padrão) e faz **uma** pergunta: o
saldo cobre as contas da semana que vem? É a pergunta que se responde numa segunda de
manhã, e por isso a janela é outra.

Tarefa: T127
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import formata_dinheiro
from app.dominio import mundo as mod_mundo
from app.lancamentos.servico import le_configuracao
from app.notificacoes import servico as servico_notificacoes

registrador = logging.getLogger("synapse.erp.rotina")

NOME = "semanal"
SEGUNDA_FEIRA = 1  # isoweekday


@dataclass
class Resultado:
    resumo_criado: bool = False
    alertas_de_caixa_baixo: int = 0
    notificacoes_criadas: int = 0
    avisos: list[str] = field(default_factory=list)


def e_segunda(quando: date) -> bool:
    return quando.isoweekday() == SEGUNDA_FEIRA


async def _numeros_da_semana(
    conexao: AsyncConnection, *, inicio: date, fim: date
) -> dict[str, Decimal]:
    linha = (
        (
            await conexao.execute(
                text("""
                    select
                      coalesce(sum(l.valor) filter (where l.tipo = 'receita'), 0) as receitas,
                      coalesce(sum(l.valor) filter (where l.tipo = 'despesa'), 0) as despesas
                    from lancamentos_ativos l
                    where l.data between :inicio and :fim and l.status = 'efetivado'
                      and not exists (
                        select 1 from lancamentos p
                        where p.lancamento_pai_id = l.id and p.excluido_em is null
                      )
                    """),
                {"inicio": inicio, "fim": fim},
            )
        )
        .mappings()
        .one()
    )
    return {
        "receitas": Decimal(str(linha["receitas"])),
        "despesas": Decimal(str(linha["despesas"])),
    }


async def _saldo_e_compromissos(
    conexao: AsyncConnection, *, mundo: str, hoje: date, horizonte_dias: int
) -> tuple[Decimal, Decimal]:
    saldo = (
        await conexao.execute(
            text("""
                select coalesce(sum(
                  case when l.tipo = 'receita' then l.valor else -l.valor end), 0)
                from lancamentos_ativos l
                where l.mundo = cast(:mundo as mundo) and l.status = 'efetivado'
                  and not exists (
                    select 1 from lancamentos p
                    where p.lancamento_pai_id = l.id and p.excluido_em is null
                  )
                """),
            {"mundo": mundo},
        )
    ).scalar_one()

    compromissos = (
        await conexao.execute(
            text("""
                select coalesce(sum(l.valor), 0)
                from lancamentos_ativos l
                where l.mundo = cast(:mundo as mundo)
                  and l.tipo = 'despesa'
                  and l.data between :hoje and :ate
                  and l.status in ('programado','pendente','atrasado')
                """),
            {"mundo": mundo, "hoje": hoje, "ate": hoje + timedelta(days=horizonte_dias)},
        )
    ).scalar_one()

    return Decimal(str(saldo)), Decimal(str(compromissos))


async def executa(conexao: AsyncConnection, *, hoje: date | None = None) -> dict[str, Any]:
    """Gera o resumo da semana passada e os alertas de caixa baixo."""
    hoje = hoje or date.today()
    comeco = time.monotonic()
    resultado = Resultado()

    usuarios = await servico_notificacoes.destinatarios(conexao)
    if not usuarios:
        resultado.avisos.append("Nenhum usuário ativo para receber o resumo.")

    # ── Resumo da semana que terminou (`FR-098`) ────────────────────────────
    fim = hoje - timedelta(days=hoje.isoweekday())  # domingo anterior
    inicio = fim - timedelta(days=6)
    numeros = await _numeros_da_semana(conexao, inicio=inicio, fim=fim)
    resultado_semana = numeros["receitas"] - numeros["despesas"]

    criadas = await servico_notificacoes.cria(
        conexao,
        tipo="resumo_semanal",
        titulo=f"Resumo de {inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}",
        corpo=(
            f"Entrou {formata_dinheiro(numeros['receitas'])}, saiu "
            f"{formata_dinheiro(numeros['despesas'])}. Resultado da semana: "
            f"{formata_dinheiro(resultado_semana)}."
        ),
        chave=servico_notificacoes.chave_de_resumo_semanal(hoje),
        usuarios=usuarios,
    )
    resultado.resumo_criado = criadas > 0
    resultado.notificacoes_criadas += criadas

    # ── Caixa baixo, por mundo (`FR-099`) ───────────────────────────────────
    horizonte = int(await le_configuracao(conexao, "caixa_baixo_horizonte_dias", padrao=7))
    for nome_do_mundo in mod_mundo.MUNDOS:
        saldo, compromissos = await _saldo_e_compromissos(
            conexao, mundo=nome_do_mundo, hoje=hoje, horizonte_dias=horizonte
        )
        # Sem compromisso não há alerta a dar — e avisar "seu caixa cobre R$ 0,00"
        # seria ruído que ensina o usuário a ignorar o sino.
        if compromissos <= 0 or saldo >= compromissos:
            continue

        resultado.alertas_de_caixa_baixo += 1
        resultado.notificacoes_criadas += await servico_notificacoes.cria(
            conexao,
            tipo="caixa_baixo",
            titulo=f"Caixa apertado em {mod_mundo.ROTULOS[nome_do_mundo]}",
            corpo=(
                f"O saldo de {formata_dinheiro(saldo)} não cobre "
                f"{formata_dinheiro(compromissos)} de contas nos próximos "
                f"{horizonte} dias."
            ),
            chave=servico_notificacoes.chave_de_caixa_baixo(nome_do_mundo, hoje),
            mundo=nome_do_mundo,
            usuarios=usuarios,
        )

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
            "processada": hoje,
            "resultado": json.dumps(asdict(resultado), ensure_ascii=False),
        },
    )
    registrador.info("rotina semanal: %s", asdict(resultado))

    return {
        "data_processada": hoje.isoformat(),
        "semana": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "resultado": asdict(resultado),
        "duracao_ms": int((time.monotonic() - comeco) * 1000),
    }
