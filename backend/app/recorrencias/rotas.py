"""Endpoints de recorrências e parcelamento — contracts/lancamentos.md §3 e §4.

Papéis: tudo `gestor, operador`, exceto `DELETE /api/recorrencias/{id}`, que é só
gestor — apagar a regra é ato estrutural, desativar já resolve o dia a dia.

Duas coisas que este arquivo faz e não são óbvias:

- **`POST /api/recorrencias` responde `422` antes de gravar** quando a série retroativa
  passa do limiar configurado (`FR-027`). A prévia vem no corpo do erro; o cliente
  reenvia com `confirmar_geracao_retroativa: true`.
- **`PUT` com `esta_e_futuras` apaga e regera** só o que é de hoje em diante. Ocorrência
  passada nunca muda por essa via (`RN-07`) — quem quiser mexer no passado edita a
  ocorrência, uma a uma, com confirmação histórica.

Tarefas: T079, T080, T081, T082
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroConfirmacaoNecessaria, ErroNaoEncontrado, ErroRegraViolada
from app.comum.idempotencia import chave_de_idempotencia, registra_resposta, resposta_ja_registrada
from app.comum.paginacao import Paginacao, envelope, parametros_de_paginacao
from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.dominio import parcelamento as mod_parcelamento
from app.dominio import recorrencia as mod_recorrencia
from app.lancamentos import servico as servico_lancamentos
from app.recorrencias import repositorio, servico
from app.recorrencias.esquemas import (
    ContinuarGeracaoEntrada,
    ParcelamentoEntrada,
    PreviaEntrada,
    RecorrenciaEdicao,
    RecorrenciaEntrada,
)
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/recorrencias", tags=["Recorrências"])
roteador_parcelamentos = APIRouter(prefix="/api/parcelamentos", tags=["Recorrências"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Gestor = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]


def _campos(corpo: RecorrenciaEntrada) -> dict[str, Any]:
    """Do corpo validado para os parâmetros do repositório."""
    return {
        "tipo": corpo.tipo,
        "descricao": corpo.descricao,
        "valor": corpo.valor,
        "categoria_id": str(corpo.categoria_id),
        "subcategoria_id": str(corpo.subcategoria_id) if corpo.subcategoria_id else None,
        "servico_id": str(corpo.servico_id) if corpo.servico_id else None,
        "centro_custo_id": str(corpo.centro_custo_id) if corpo.centro_custo_id else None,
        "frequencia": corpo.frequencia,
        "intervalo_dias": corpo.intervalo_dias,
        "dia_vencimento": corpo.dia_vencimento,
        "mes_vencimento": corpo.mes_vencimento,
        "data_inicio": corpo.data_inicio,
        "data_fim": corpo.data_fim,
        "total_parcelas": corpo.total_parcelas,
        "efetivar_automaticamente": corpo.efetivar_automaticamente,
        "cliente_id": str(corpo.cliente_id) if corpo.cliente_id else None,
        "funcionario_id": str(corpo.funcionario_id) if corpo.funcionario_id else None,
    }


def _regra_do_corpo(corpo: Any) -> mod_recorrencia.Regra:
    return mod_recorrencia.Regra(
        frequencia=corpo.frequencia,
        data_inicio=corpo.data_inicio,
        dia_vencimento=corpo.dia_vencimento,
        mes_vencimento=corpo.mes_vencimento,
        intervalo_dias=corpo.intervalo_dias,
        data_fim=corpo.data_fim,
        total_parcelas=corpo.total_parcelas,
    )


# ── T079 · GET /api/recorrencias ────────────────────────────────────────────


@roteador.get(
    "",
    summary="Lista as recorrências, com próxima ocorrência e quantas já geraram",
    description="Papel: gestor, operador. `?mundo=` e `?apenas_ativas=` (contracts §3).",
)
async def listar(
    usuario: Autenticado,
    conexao: Conexao,
    paginacao: Annotated[Paginacao, Depends(parametros_de_paginacao)],
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    apenas_ativas: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    mundos = mod_mundo.resolve_filtro(mundo)
    linhas = await repositorio.lista(
        conexao,
        mundos=mundos,
        apenas_ativas=apenas_ativas,
        limite=paginacao.por_pagina,
        deslocamento=paginacao.deslocamento,
    )
    total = await repositorio.conta(conexao, mundos=mundos, apenas_ativas=apenas_ativas)
    return envelope(
        [servico.para_json(linha) for linha in linhas], total=total, paginacao=paginacao
    )


# ── T080 · POST /api/recorrencias/previa ────────────────────────────────────
#
# ⚠️ Declarada ANTES de `/{recorrencia_id}` — mesma armadilha de ordem de rota dos
# lançamentos: com a rota de id na frente, "previa" seria lido como UUID.


@roteador.post(
    "/previa",
    summary="Conta quantas ocorrências a regra geraria. Não grava nada",
    description=(
        "Papel: gestor, operador. `FR-027`. Serve à tela mostrar o impacto **antes** de "
        "o usuário confirmar — e ao próprio `POST`, que usa a mesma contagem para "
        "decidir se responde `422`."
    ),
)
async def previa(corpo: PreviaEntrada, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    ate = await servico.horizonte_configurado(conexao)
    resultado = mod_recorrencia.monta_previa(_regra_do_corpo(corpo), ate=ate)

    total_retroativo = None
    if corpo.valor is not None:
        total_retroativo = f"{corpo.valor * resultado.retroativas_efetivadas:.2f}"

    return {
        "previa": resultado.como_dicionario(total_retroativo),
        "limiar_de_confirmacao": await servico.limiar_de_aviso(conexao),
        "horizonte": ate.isoformat(),
    }


# ── T079/T080/T081 · POST /api/recorrencias ─────────────────────────────────


@roteador.post(
    "",
    status_code=201,
    summary="Cria a recorrência e materializa as ocorrências",
    description=(
        "Papel: gestor, operador. Aceita `Idempotency-Key`. Série retroativa acima de "
        "`configuracoes.recorrencia_aviso_ocorrencias` → `422 confirmacao_necessaria` "
        "com a prévia (`FR-027`); reenvie com `confirmar_geracao_retroativa: true`. "
        "Ocorrências até hoje nascem `efetivado` (`RN-05a`). Se a série for longa "
        "demais para uma invocação, a resposta traz `geracao.concluida: false` e um "
        "`cursor` para `continuar-geracao` (D-02a)."
    ),
)
async def criar(
    corpo: RecorrenciaEntrada,
    usuario: Autenticado,
    conexao: Conexao,
    chave: Annotated[str | None, Depends(chave_de_idempotencia)] = None,
) -> dict[str, Any]:
    ja_feito = await resposta_ja_registrada(
        conexao, chave, rota="POST /api/recorrencias", usuario_id=str(usuario.id)
    )
    if ja_feito is not None:
        return ja_feito

    mundo_validado = mod_mundo.exige("recorrencias", corpo.mundo)
    await servico_lancamentos.valida_classificacao(
        conexao,
        categoria_id=corpo.categoria_id,
        subcategoria_id=corpo.subcategoria_id,
        tipo=corpo.tipo,
    )
    await servico_lancamentos.valida_vinculos_de_mundo(
        conexao,
        mundo=mundo_validado,
        servico_id=corpo.servico_id,
        centro_custo_id=corpo.centro_custo_id,
    )

    regra = _regra_do_corpo(corpo)
    ate = await servico.horizonte_configurado(conexao)
    resultado_previa = mod_recorrencia.monta_previa(regra, ate=ate)
    limiar = await servico.limiar_de_aviso(conexao)

    # `FR-027`: avisa antes de criar, e só quando o número é grande o bastante para
    # surpreender. Perguntar sempre viraria clique automático, e clique automático não
    # é confirmação.
    if resultado_previa.total_ocorrencias > limiar and not corpo.confirmar_geracao_retroativa:
        primeira = resultado_previa.primeira
        ultima = resultado_previa.ultima
        raise ErroConfirmacaoNecessaria(
            (
                f"Serão criadas {resultado_previa.total_ocorrencias} ocorrências entre "
                f"{primeira.strftime('%d/%m/%Y') if primeira else '—'} e "
                f"{ultima.strftime('%d/%m/%Y') if ultima else '—'}, sendo "
                f"{resultado_previa.retroativas_efetivadas} já efetivadas."
            ),
            requisito="FR-027",
            previa=resultado_previa.como_dicionario(
                f"{corpo.valor * resultado_previa.retroativas_efetivadas:.2f}"
            ),
            campo_confirmacao="confirmar_geracao_retroativa",
        )

    nova = await repositorio.insere(
        conexao, campos=_campos(corpo), mundo=mundo_validado, usuario_id=usuario.id
    )
    linha = await servico.exige_recorrencia(conexao, nova["id"])
    geracao = await servico.materializa(conexao, linha, usuario_id=usuario.id, ate=ate)

    await registra_auditoria(
        conexao,
        entidade="recorrencias",
        entidade_id=nova["id"],
        acao="criacao",
        usuario_id=usuario.id,
        depois={
            "mundo": mundo_validado,
            "descricao": corpo.descricao,
            "valor": corpo.valor,
            "frequencia": corpo.frequencia,
            "data_inicio": corpo.data_inicio,
        },
    )

    atualizada = await servico.exige_recorrencia(conexao, nova["id"])
    resposta = servico.para_json(atualizada) | {"geracao": geracao.como_dicionario()}
    await registra_resposta(
        conexao, chave, rota="POST /api/recorrencias", usuario_id=str(usuario.id), resposta=resposta
    )
    return resposta


# ── T079 · GET /api/recorrencias/{id} ───────────────────────────────────────


@roteador.get(
    "/{recorrencia_id}",
    summary="A regra mais as ocorrências já materializadas",
    description="Papel: gestor, operador.",
)
async def detalhar(recorrencia_id: UUID, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    linha = await servico.exige_recorrencia(conexao, recorrencia_id)
    materializadas = await repositorio.ocorrencias(conexao, recorrencia_id)

    return servico.para_json(linha) | {
        "ocorrencias": [
            {
                "id": str(item["id"]),
                "data": item["data"].isoformat(),
                "valor": f"{Decimal(str(item['valor'])):.2f}",
                "status": item["status"],
                "descricao": item["descricao"],
            }
            for item in materializadas
        ]
    }


# ── T079 · PUT /api/recorrencias/{id} (`RN-07`) ─────────────────────────────


@roteador.put(
    "/{recorrencia_id}",
    summary="Edita a regra, com escopo obrigatório",
    description=(
        "Papel: gestor, operador. `escopo_serie` é **obrigatório** (`RN-07`). "
        "`esta_e_futuras` apaga as ocorrências de hoje em diante ainda não efetivadas e "
        "regera com a regra nova; **nenhuma ocorrência passada é tocada**. "
        "`apenas_esta` não faz sentido numa edição de regra — para mudar uma ocorrência "
        "isolada, edite o lançamento. Mudar `mundo` → `409` / `RN-15`."
    ),
)
async def editar(
    recorrencia_id: UUID, corpo: RecorrenciaEdicao, usuario: Autenticado, conexao: Conexao
) -> dict[str, Any]:
    atual = await servico.exige_recorrencia(conexao, recorrencia_id)
    mod_mundo.recusa_alteracao(atual["mundo"], corpo.mundo)

    if corpo.escopo_serie == "apenas_esta":
        raise ErroRegraViolada(
            (
                "Para mudar uma única ocorrência, edite o lançamento dela. Aqui você "
                "está editando a regra que gera a série inteira."
            ),
            requisito="RN-07",
            campos={"escopo_serie": "Use 'esta_e_futuras' para editar a regra."},
        )

    await servico_lancamentos.valida_classificacao(
        conexao,
        categoria_id=corpo.categoria_id,
        subcategoria_id=corpo.subcategoria_id,
        tipo=corpo.tipo,
    )
    await servico_lancamentos.valida_vinculos_de_mundo(
        conexao,
        mundo=atual["mundo"],
        servico_id=corpo.servico_id,
        centro_custo_id=corpo.centro_custo_id,
    )

    hoje = date.today()
    # `RN-07` em duas etapas: apaga só o que é de hoje em diante e ainda não efetivado,
    # depois recua `gerada_ate` para hoje para a materialização refazer esse trecho.
    #
    # `definitivo=True` é obrigatório aqui, não uma preferência: o índice único de
    # `(recorrencia_id, data)` (migração `010`) não filtra `excluido_em`, então soft
    # delete não libera a data e o `on conflict do nothing` da regeneração não inseria
    # nada. A edição limpava o futuro e não regerava — ver `remove_futuras_nao_efetivadas`.
    removidas = await repositorio.remove_futuras_nao_efetivadas(
        conexao, recorrencia_id, a_partir_de=hoje, usuario_id=usuario.id, definitivo=True
    )
    await repositorio.atualiza(conexao, recorrencia_id, campos=_campos(corpo))
    await conexao.execute(
        text("update recorrencias set gerada_ate = :ontem where id = :id"),
        {"id": str(recorrencia_id), "ontem": hoje - timedelta(days=1)},
    )

    linha = await servico.exige_recorrencia(conexao, recorrencia_id)
    ate = await servico.horizonte_configurado(conexao, hoje)
    geracao = await servico.materializa(conexao, linha, usuario_id=usuario.id, ate=ate, hoje=hoje)

    await registra_auditoria(
        conexao,
        entidade="recorrencias",
        entidade_id=recorrencia_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes={k: atual[k] for k in ("descricao", "valor", "frequencia", "dia_vencimento")},
        depois={
            "descricao": corpo.descricao,
            "valor": corpo.valor,
            "frequencia": corpo.frequencia,
            "dia_vencimento": corpo.dia_vencimento,
        },
    )

    atualizada = await servico.exige_recorrencia(conexao, recorrencia_id)
    return servico.para_json(atualizada) | {
        "geracao": geracao.como_dicionario(),
        "ocorrencias_futuras_regeradas": removidas,
    }


# ── T081 · POST /api/recorrencias/{id}/continuar-geracao ────────────────────


@roteador.post(
    "/{recorrencia_id}/continuar-geracao",
    summary="Continua a materialização de uma série longa",
    description=(
        "Papel: gestor, operador. D-02a. Chame em laço enquanto "
        "`geracao.concluida` for `false`, mostrando progresso. O servidor retoma de "
        "`gerada_ate` — o `cursor` do corpo é conferência, não estado."
    ),
)
async def continuar_geracao(
    recorrencia_id: UUID,
    corpo: ContinuarGeracaoEntrada,
    usuario: Autenticado,
    conexao: Conexao,
) -> dict[str, Any]:
    linha = await servico.exige_recorrencia(conexao, recorrencia_id)
    ate = await servico.horizonte_configurado(conexao)
    geracao = await servico.materializa(conexao, linha, usuario_id=usuario.id, ate=ate)
    return {"geracao": geracao.como_dicionario()}


# ── T079 · desativar e excluir ──────────────────────────────────────────────


@roteador.post(
    "/{recorrencia_id}/desativar",
    summary="Para de gerar e remove as futuras não efetivadas",
    description=(
        "Papel: gestor, operador. As ocorrências **já efetivadas ficam** — o dinheiro "
        "que se moveu é histórico (`RN-05`). Só as futuras ainda não confirmadas saem."
    ),
)
async def desativar(recorrencia_id: UUID, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    linha = await servico.exige_recorrencia(conexao, recorrencia_id)
    if not linha["ativa"]:
        raise ErroRegraViolada(
            "Esta recorrência já está desativada.",
            requisito="RF-15",
            campos={"ativa": "Já desativada."},
        )

    removidas = await repositorio.remove_futuras_nao_efetivadas(
        conexao, recorrencia_id, a_partir_de=date.today(), usuario_id=usuario.id
    )
    await repositorio.desativa(conexao, recorrencia_id)
    await registra_auditoria(
        conexao,
        entidade="recorrencias",
        entidade_id=recorrencia_id,
        acao="edicao",
        usuario_id=usuario.id,
        alteracoes={
            "ativa": {"de": True, "para": False},
            "ocorrencias_futuras_removidas": {"de": None, "para": removidas},
        },
    )

    atualizada = await servico.exige_recorrencia(conexao, recorrencia_id)
    return servico.para_json(atualizada) | {"ocorrencias_futuras_removidas": removidas}


@roteador.delete(
    "/{recorrencia_id}",
    status_code=204,
    summary="Exclui a regra (soft delete)",
    description=(
        "Papel: **gestor**. A regra sai da lista; as ocorrências efetivadas continuam "
        "no histórico. Não existe exclusão definitiva (`RN-08`)."
    ),
)
async def excluir(recorrencia_id: UUID, usuario: Gestor, conexao: Conexao) -> None:
    await servico.exige_recorrencia(conexao, recorrencia_id)
    removidas = await repositorio.remove_futuras_nao_efetivadas(
        conexao, recorrencia_id, a_partir_de=date.today(), usuario_id=usuario.id
    )
    await repositorio.exclui(conexao, recorrencia_id, usuario_id=usuario.id)
    await registra_auditoria(
        conexao,
        entidade="recorrencias",
        entidade_id=recorrencia_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={"ocorrencias_futuras_removidas": {"de": None, "para": removidas}},
    )


# ── T082 · Parcelamento (`FR-028`) ──────────────────────────────────────────


@roteador_parcelamentos.post(
    "",
    status_code=201,
    summary="Cria um parcelamento e os N lançamentos",
    description=(
        "Papel: gestor, operador. `FR-028`. As primeiras parcelas levam o valor "
        "arredondado e **a última absorve a diferença** — a soma bate exatamente com "
        "`valor_total`. A descrição de cada uma mostra a posição ('2/3')."
    ),
)
async def criar_parcelamento(
    corpo: ParcelamentoEntrada,
    usuario: Autenticado,
    conexao: Conexao,
    chave: Annotated[str | None, Depends(chave_de_idempotencia)] = None,
) -> dict[str, Any]:
    ja_feito = await resposta_ja_registrada(
        conexao, chave, rota="POST /api/parcelamentos", usuario_id=str(usuario.id)
    )
    if ja_feito is not None:
        return ja_feito

    mundo_validado = mod_mundo.exige("parcelamentos", corpo.mundo)
    await servico_lancamentos.valida_classificacao(
        conexao,
        categoria_id=corpo.categoria_id,
        subcategoria_id=corpo.subcategoria_id,
        tipo=corpo.tipo,
    )
    await servico_lancamentos.valida_vinculos_de_mundo(
        conexao,
        mundo=mundo_validado,
        servico_id=corpo.servico_id,
        centro_custo_id=corpo.centro_custo_id,
    )

    parcelas = mod_parcelamento.divide(
        valor_total=corpo.valor_total,
        total_parcelas=corpo.total_parcelas,
        data_primeira=corpo.data_primeira_parcela,
        intervalo=corpo.intervalo,
    )

    novo = (
        (
            await conexao.execute(
                text("""
                    insert into parcelamentos (
                      mundo, descricao, valor_total, total_parcelas, criado_por
                    ) values (
                      cast(:mundo as mundo), :descricao, :valor_total, :total_parcelas,
                      cast(:usuario as uuid)
                    )
                    returning id
                    """),
                {
                    "mundo": mundo_validado,
                    "descricao": corpo.descricao,
                    "valor_total": corpo.valor_total,
                    "total_parcelas": corpo.total_parcelas,
                    "usuario": str(usuario.id),
                },
            )
        )
        .mappings()
        .one()
    )

    hoje = date.today()
    for parcela in parcelas:
        # Mesma régua dos lançamentos avulsos: parcela com data passada nasce
        # efetivada (`FR-024`), o resto nasce programada.
        status = "efetivado" if parcela.data <= hoje else "programado"
        await conexao.execute(
            text("""
                insert into lancamentos (
                  mundo, tipo, descricao, valor, data, status,
                  categoria_id, subcategoria_id, servico_id, centro_custo_id,
                  efetivar_automaticamente, efetivado_em, efetivado_por,
                  parcelamento_id, parcela_numero, parcela_total, criado_por
                ) values (
                  cast(:mundo as mundo), cast(:tipo as tipo_lancamento), :descricao, :valor,
                  :data, cast(:status as status_lancamento),
                  cast(:categoria_id as uuid), cast(:subcategoria_id as uuid),
                  cast(:servico_id as uuid), cast(:centro_custo_id as uuid),
                  :efetivar_automaticamente,
                  case when :status = 'efetivado' then now() end,
                  case when :status = 'efetivado' then cast(:usuario as uuid) end,
                  :parcelamento_id, :numero, :total, cast(:usuario as uuid)
                )
                """),
            {
                "mundo": mundo_validado,
                "tipo": corpo.tipo,
                "descricao": mod_parcelamento.descricao_da_parcela(corpo.descricao, parcela),
                "valor": parcela.valor,
                "data": parcela.data,
                "status": status,
                "categoria_id": str(corpo.categoria_id),
                "subcategoria_id": str(corpo.subcategoria_id) if corpo.subcategoria_id else None,
                "servico_id": str(corpo.servico_id) if corpo.servico_id else None,
                "centro_custo_id": (str(corpo.centro_custo_id) if corpo.centro_custo_id else None),
                "efetivar_automaticamente": corpo.efetivar_automaticamente,
                "parcelamento_id": str(novo["id"]),
                "numero": parcela.numero,
                "total": parcela.total,
                "usuario": str(usuario.id),
            },
        )

    await registra_auditoria(
        conexao,
        entidade="parcelamentos",
        entidade_id=novo["id"],
        acao="criacao",
        usuario_id=usuario.id,
        depois={
            "mundo": mundo_validado,
            "descricao": corpo.descricao,
            "valor_total": corpo.valor_total,
            "total_parcelas": corpo.total_parcelas,
        },
    )

    resposta = await detalhar_parcelamento(novo["id"], usuario, conexao)
    await registra_resposta(
        conexao,
        chave,
        rota="POST /api/parcelamentos",
        usuario_id=str(usuario.id),
        resposta=resposta,
    )
    return resposta


@roteador_parcelamentos.get(
    "/{parcelamento_id}",
    summary="O parcelamento e suas parcelas",
    description="Papel: gestor, operador. `pago` soma só as parcelas efetivadas (`RN-05`).",
)
async def detalhar_parcelamento(
    parcelamento_id: UUID, usuario: Autenticado, conexao: Conexao
) -> dict[str, Any]:
    cabecalho = (
        (
            await conexao.execute(
                text(
                    "select id, mundo, descricao, valor_total, total_parcelas, criado_em "
                    "from parcelamentos where id = :id"
                ),
                {"id": str(parcelamento_id)},
            )
        )
        .mappings()
        .first()
    )
    if cabecalho is None:
        raise ErroNaoEncontrado("Parcelamento não encontrado.")

    parcelas = (
        (
            await conexao.execute(
                text("""
                    select id, parcela_numero, parcela_total, descricao, valor, data, status
                    from lancamentos_ativos
                    where parcelamento_id = :id
                    order by parcela_numero
                    """),
                {"id": str(parcelamento_id)},
            )
        )
        .mappings()
        .all()
    )

    pago = sum(
        (Decimal(str(p["valor"])) for p in parcelas if p["status"] == "efetivado"),
        Decimal("0.00"),
    )
    total = Decimal(str(cabecalho["valor_total"]))

    return {
        "id": str(cabecalho["id"]),
        "mundo": cabecalho["mundo"],
        "descricao": cabecalho["descricao"],
        "valor_total": f"{total:.2f}",
        "total_parcelas": cabecalho["total_parcelas"],
        "pago": f"{pago:.2f}",
        "a_pagar": f"{total - pago:.2f}",
        "criado_em": cabecalho["criado_em"].isoformat(),
        "parcelas": [
            {
                "id": str(p["id"]),
                "numero": p["parcela_numero"],
                "total": p["parcela_total"],
                "rotulo": f"{p['parcela_numero']}/{p['parcela_total']}",
                "descricao": p["descricao"],
                "valor": f"{Decimal(str(p['valor'])):.2f}",
                "data": p["data"].isoformat(),
                "status": p["status"],
            }
            for p in parcelas
        ],
    }
