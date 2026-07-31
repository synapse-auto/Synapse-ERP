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

## Os alertas (B6 — T125, T126)

Depois de materializar e aplicar o ciclo de status, a rotina gera as notificações. As
duas famílias dependem de coisas diferentes:

- **Vencimento** (`FR-096`): olha as antecedências de `configuracoes.alerta_vencimento_dias`
  (`[1, 3, 7]` por padrão) e avisa do que vence nesses dias. A chave de deduplicação inclui
  a antecedência, então "vence em 7" e "vence em 3" são avisos diferentes do mesmo
  lançamento — que é o comportamento desejado.
- **Inadimplência** (`FR-097`): sai de `dominio/inadimplencia.py`, com a mesma regra da
  tela. Cliente com mensalidade **automática** nunca aparece aqui (D-05), e isso não é
  falha da rotina.

Tarefa: T083, T125, T126
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import formata_dinheiro
from app.dominio import inadimplencia as mod_inadimplencia
from app.lancamentos.servico import le_configuracao
from app.notificacoes import servico as servico_notificacoes
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
    clientes_marcados_inadimplentes: int = 0
    notificacoes_criadas: int = 0
    importacoes_expiradas_removidas: int = 0
    chaves_idempotencia_removidas: int = 0
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


# ── Passo 3 — alertas de vencimento (`FR-096`, T125) ───────────────────────


async def _alerta_de_vencimento(
    conexao: AsyncConnection, resultado: Resultado, *, hoje: date
) -> None:
    """Avisa do que vence nas antecedências configuradas.

    As antecedências vêm de `configuracoes.alerta_vencimento_dias` — `[1, 3, 7]` por
    padrão, mas é dado, não código (`RNF-02`). A chave de deduplicação inclui a
    antecedência, então o mesmo lançamento avisa em 7, em 3 e em 1 dia sem repetir
    nenhum dos três.
    """
    antecedencias = await le_configuracao(conexao, "alerta_vencimento_dias", padrao=[1, 3, 7])
    usuarios = await servico_notificacoes.destinatarios(conexao)
    if not usuarios:
        return

    for dias in antecedencias:
        vencem = (
            (
                await conexao.execute(
                    text("""
                        select l.id, l.mundo, l.tipo, l.descricao, l.valor, l.data
                        from lancamentos_ativos l
                        where l.data = :quando
                          and l.status in ('programado','pendente')
                        order by l.valor desc
                        """),
                    {"quando": hoje + timedelta(days=int(dias))},
                )
            )
            .mappings()
            .all()
        )

        for item in vencem:
            verbo = "receber" if item["tipo"] == "receita" else "pagar"
            quando = "amanhã" if dias == 1 else f"em {dias} dias"
            resultado.notificacoes_criadas += await servico_notificacoes.cria(
                conexao,
                tipo="vencimento",
                titulo=f"{item['descricao']} vence {quando}",
                corpo=(
                    f"{formata_dinheiro(item['valor'])} a {verbo} em "
                    f"{item['data'].strftime('%d/%m/%Y')}."
                ),
                chave=servico_notificacoes.chave_de_vencimento(item["id"], int(dias)),
                mundo=item["mundo"],
                lancamento_id=item["id"],
                usuarios=usuarios,
            )


# ── Passo 4 — alerta de inadimplência (`FR-097`, T126) ─────────────────────


async def _alerta_de_inadimplencia(
    conexao: AsyncConnection, resultado: Resultado, *, hoje: date
) -> None:
    """A mesma regra da tela, vinda de `dominio/inadimplencia.py`.

    Reimplementar o critério aqui faria a rotina e a lista de clientes discordarem no
    dia em que a tolerância mudasse — e a discordância apareceria como "o sistema
    avisou de um cliente que a tela diz estar em dia".
    """
    tolerancia = int(
        await le_configuracao(
            conexao,
            "inadimplencia_dias_tolerancia",
            padrao=mod_inadimplencia.PADRAO_DIAS_TOLERANCIA,
        )
    )
    usuarios = await servico_notificacoes.destinatarios(conexao)
    if not usuarios:
        return

    clientes = (await conexao.execute(text("""
                    select c.id, c.nome,
                           jsonb_agg(jsonb_build_object(
                             'data', l.data, 'valor', l.valor, 'status', l.status,
                             'efetivar_automaticamente', l.efetivar_automaticamente
                           )) as em_aberto
                    from clientes c
                    join subcategorias s on s.cliente_id = c.id
                    join lancamentos_ativos l on l.subcategoria_id = s.id
                    where c.arquivado_em is null
                      and l.tipo = 'receita'
                      and l.status in ('pendente','atrasado')
                    group by c.id, c.nome
                    """))).mappings().all()

    for cliente in clientes:
        situacao = mod_inadimplencia.avalia(
            [
                {
                    "data": date.fromisoformat(item["data"]),
                    "valor": item["valor"],
                    "status": item["status"],
                    "efetivar_automaticamente": item["efetivar_automaticamente"],
                }
                for item in cliente["em_aberto"]
            ],
            tolerancia_dias=tolerancia,
            hoje=hoje,
        )
        if situacao.situacao != "atrasado":
            continue

        resultado.clientes_marcados_inadimplentes += 1
        resultado.notificacoes_criadas += await servico_notificacoes.cria(
            conexao,
            tipo="inadimplencia",
            titulo=f"{cliente['nome']} está com pagamento atrasado",
            corpo=(
                f"{formata_dinheiro(situacao.valor_atrasado)} vencidos há "
                f"{situacao.dias_atraso} dias."
            ),
            chave=servico_notificacoes.chave_de_inadimplencia(cliente["id"], hoje),
            cliente_id=cliente["id"],
            usuarios=usuarios,
        )


# ── Passo 5 — faxina do estado temporário ───────────────────────────────────


async def _limpa_chaves_de_idempotencia(conexao: AsyncConnection, resultado: Resultado) -> None:
    """Apaga as chaves de `Idempotency-Key` vencidas (migração `012`).

    A janela útil é de minutos — o tempo de uma repetição de rede. Sem a faxina, a tabela
    só cresceria guardando corpos de resposta que ninguém vai mais pedir.
    """
    apagadas = (
        await conexao.execute(text("delete from chaves_idempotencia where expira_em <= now()"))
    ).rowcount
    resultado.chaves_idempotencia_removidas = max(apagadas or 0, 0)


async def _limpa_importacoes_expiradas(conexao: AsyncConnection, resultado: Resultado) -> None:
    """Apaga o estado de importação que passou de `expira_em` (migração `011`).

    `importacoes` é uma das duas tabelas do sistema onde apagar linha é o certo (a outra
    é `chaves_idempotencia`): ela guarda o conteúdo do arquivo em `jsonb` como rascunho de
    três etapas, não histórico financeiro. O que vira lançamento sai dela e passa a viver
    em `lancamentos`, que nunca é apagado (`RN-08`).

    A migração e o comentário da tabela já diziam que esta faxina existia. Ela não
    existia: a coluna era só um `default`, ninguém a conferia e ninguém a limpava —
    então um upload abandonado ficava gravável para sempre, com o arquivo inteiro na
    tabela. O `DELETE` mora aqui, e a recusa de confirmar depois do prazo mora em
    `importacao/rotas.py`; as duas pontas são necessárias, porque a rotina pode ter
    falhado no dia.
    """
    # `DELETE` sem `RETURNING` de propósito: com `RETURNING` o `rowcount` do asyncpg
    # deixa de ser confiável (a operação passa a devolver linhas), e aqui o número vai
    # para `ultimo_resultado`, que é registro de verificação (Princípio VI). Contagem
    # errada num relato é pior que contagem nenhuma.
    apagadas = (
        await conexao.execute(text("delete from importacoes where expira_em <= now()"))
    ).rowcount
    resultado.importacoes_expiradas_removidas = max(apagadas or 0, 0)


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
    # Os alertas vêm DEPOIS do ciclo de status de propósito: um lançamento que acabou de
    # virar `atrasado` nesta mesma execução precisa entrar na conta da inadimplência.
    await _alerta_de_vencimento(conexao, resultado, hoje=hoje)
    await _alerta_de_inadimplencia(conexao, resultado, hoje=hoje)
    await _limpa_importacoes_expiradas(conexao, resultado)
    await _limpa_chaves_de_idempotencia(conexao, resultado)

    # `FR-098`: o plano gratuito da Vercel só dá um cron por dia, então o semanal é
    # disparado daqui, na segunda. A chave por semana ISO garante um resumo só, mesmo
    # que a rotina rode cinco vezes na mesma segunda.
    from app.rotinas import semanal as rotina_semanal

    if rotina_semanal.e_segunda(hoje):
        do_semanal = await rotina_semanal.executa(conexao, hoje=hoje)
        resultado.notificacoes_criadas += do_semanal["resultado"]["notificacoes_criadas"]

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
