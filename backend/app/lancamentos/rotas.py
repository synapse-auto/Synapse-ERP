"""Endpoints de lançamentos — contracts/lancamentos.md §1 e §2.

Todo endpoint declara o papel (constituição). Aqui todos são `gestor, operador`: quem
lança é a contadora, e é o trabalho diário do sistema.

Tarefas: T055–T061, T066, T067
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import ORJSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.anexos.rotas import lista_do_lancamento
from app.comum import periodo as mod_periodo
from app.comum.auditoria import registra_auditoria
from app.comum.erros import (
    ErroConflitoVersao,
    ErroDaApi,
    ErroNaoEncontrado,
    ErroRegraViolada,
    ErroValidacao,
)
from app.comum.idempotencia import chave_de_idempotencia, registra_resposta, resposta_ja_registrada
from app.comum.paginacao import Paginacao, envelope, parametros_de_paginacao
from app.db import obter_conexao
from app.dominio import cambio
from app.dominio import lixeira as mod_lixeira
from app.dominio import mundo as mod_mundo
from app.dominio import split as mod_split
from app.lancamentos import exportacao_csv, repositorio, servico
from app.lancamentos.esquemas import (
    AcoesEmMassaEntrada,
    DivisaoEntrada,
    LancamentoEdicao,
    LancamentoEntrada,
    LoteEntrada,
)
from app.rotinas import diaria as rotina_diaria
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/lancamentos", tags=["Lançamentos"])
roteador_lixeira = APIRouter(prefix="/api/lixeira", tags=["Lançamentos"])
roteador_saldo = APIRouter(prefix="/api/saldo", tags=["Consultas"])

# Teto da exportação por filtro. **Não é regra de negócio** — é o que cabe na memória e
# na duração de uma invocação da Vercel (plan.md §Constraints) montando o arquivo
# inteiro antes de responder. Acima disso a resposta manda estreitar o filtro ou usar a
# exportação completa (T137), que roda por lote com cursor. Dimensionado com folga sobre
# os 5.000 lançamentos de `SC-007`.
TETO_EXPORTACAO = 20_000

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]


async def _com_tags(conexao: AsyncConnection, linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tags = await repositorio.tags_de(conexao, [linha["id"] for linha in linhas])
    return [servico.para_json(linha, tags.get(str(linha["id"]), [])) for linha in linhas]


# ── T055 · GET /api/lancamentos ─────────────────────────────────────────────


@roteador.get(
    "",
    summary="Lista filtrada, com contador e somas do conjunto filtrado",
    description=(
        "Papel: gestor, operador. Todos os filtros são combináveis (`FR-037`). "
        "`resumo_filtrado` soma o conjunto **inteiro**, não a página (`FR-038`). "
        "`quebra_por_mundo` só vem no modo Ambos (`FR-003`)."
    ),
)
async def listar(
    usuario: Autenticado,
    conexao: Conexao,
    paginacao: Annotated[Paginacao, Depends(parametros_de_paginacao)],
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    tipo: Annotated[str | None, Query()] = None,
    categoria_id: Annotated[list[UUID] | None, Query()] = None,
    subcategoria_id: Annotated[list[UUID] | None, Query()] = None,
    servico_id: Annotated[list[UUID] | None, Query()] = None,
    centro_custo_id: Annotated[list[UUID] | None, Query()] = None,
    tag_id: Annotated[list[UUID] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
    valor_min: Annotated[Decimal | None, Query()] = None,
    valor_max: Annotated[Decimal | None, Query()] = None,
    busca: Annotated[
        str | None, Query(description="Texto livre em descrição e observações.")
    ] = None,
) -> dict[str, Any]:
    # T085: se o cron falhou hoje, a primeira leitura dispara a rotina antes de
    # responder (contracts/plataforma.md §6). Sem isso, um cron perdido viraria número
    # velho na tela sem ninguém perceber.
    await rotina_diaria.executa_se_necessario(conexao)

    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)

    condicoes, parametros = repositorio.monta_filtros(
        mundos=mundos,
        inicio=janela.inicio,
        fim=janela.fim,
        tipo=tipo,
        categoria_ids=categoria_id,
        subcategoria_ids=subcategoria_id,
        servico_ids=servico_id,
        centro_custo_ids=centro_custo_id,
        tag_ids=tag_id,
        status=status,
        valor_min=valor_min,
        valor_max=valor_max,
        busca=busca,
    )

    ordem = paginacao.clausula_ordem(repositorio.COLUNAS_ORDENAVEIS, repositorio.ORDEM_PADRAO)
    linhas = await repositorio.lista(
        conexao,
        condicoes=condicoes,
        parametros=parametros,
        ordem=ordem,
        limite=paginacao.por_pagina,
        deslocamento=paginacao.deslocamento,
    )
    agregado = await repositorio.conta_e_soma(conexao, condicoes=condicoes, parametros=parametros)

    receitas = Decimal(str(agregado["total_receitas"]))
    despesas = Decimal(str(agregado["total_despesas"]))

    resposta = envelope(
        await _com_tags(conexao, linhas), total=agregado["quantidade"], paginacao=paginacao
    )
    resposta["resumo_filtrado"] = {
        "total_receitas": f"{receitas:.2f}",
        "total_despesas": f"{despesas:.2f}",
        "resultado": f"{receitas - despesas:.2f}",
        "quantidade": agregado["quantidade"],
    }
    resposta["periodo"] = janela.como_dicionario()
    if mod_mundo.deve_quebrar_por_mundo(mundo):
        resposta["quebra_por_mundo"] = await repositorio.quebra_por_mundo(
            conexao, condicoes=condicoes, parametros=parametros
        )
    return resposta


# ── T056 · POST /api/lancamentos ────────────────────────────────────────────


async def _grava_lancamento(
    conexao: AsyncConnection,
    corpo: LancamentoEntrada,
    usuario: UsuarioAutenticado,
) -> dict[str, Any]:
    mundo_validado = mod_mundo.exige("lancamentos", corpo.mundo)
    categoria = await servico.valida_classificacao(
        conexao,
        categoria_id=corpo.categoria_id,
        subcategoria_id=corpo.subcategoria_id,
        tipo=corpo.tipo,
    )
    await servico.valida_vinculos_de_mundo(
        conexao,
        mundo=mundo_validado,
        servico_id=corpo.servico_id,
        centro_custo_id=corpo.centro_custo_id,
    )

    cotacao = None
    if corpo.moeda == "USD":
        cotacao = await servico.obtem_cotacao(conexao, corpo.data, corpo.cotacao_manual)
    campos_moeda = cambio.campos_do_lancamento(
        valor_informado=corpo.valor, moeda=corpo.moeda, cotacao=cotacao
    )

    efetivar_auto = await servico.resolve_efetivacao_automatica(
        conexao, informado=corpo.efetivar_automaticamente, tipo=corpo.tipo, categoria=categoria
    )
    status = servico.status_inicial(
        data_do_lancamento=corpo.data, efetivar_automaticamente=efetivar_auto
    )

    novo = (
        (
            await conexao.execute(
                text("""
                    insert into lancamentos (
                      mundo, tipo, descricao, valor, data, status,
                      categoria_id, subcategoria_id, servico_id, centro_custo_id,
                      observacoes, efetivar_automaticamente,
                      efetivado_em, efetivado_por,
                      moeda_origem, valor_origem, cotacao, cotacao_data, cotacao_manual,
                      criado_por
                    ) values (
                      cast(:mundo as mundo), cast(:tipo as tipo_lancamento), :descricao, :valor,
                      :data, cast(:status as status_lancamento),
                      :categoria_id, :subcategoria_id, :servico_id, :centro_custo_id,
                      :observacoes, :efetivar_automaticamente,
                      case when :status = 'efetivado' then now() end,
                      case when :status = 'efetivado' then cast(:usuario as uuid) end,
                      cast(:moeda_origem as moeda), :valor_origem, :cotacao, :cotacao_data,
                      :cotacao_manual, cast(:usuario as uuid)
                    )
                    returning id
                    """),
                {
                    "mundo": mundo_validado,
                    "tipo": corpo.tipo,
                    "descricao": corpo.descricao,
                    "data": corpo.data,
                    "status": status,
                    "categoria_id": str(corpo.categoria_id),
                    "subcategoria_id": (
                        str(corpo.subcategoria_id) if corpo.subcategoria_id else None
                    ),
                    "servico_id": str(corpo.servico_id) if corpo.servico_id else None,
                    "centro_custo_id": (
                        str(corpo.centro_custo_id) if corpo.centro_custo_id else None
                    ),
                    "observacoes": corpo.observacoes,
                    "efetivar_automaticamente": efetivar_auto,
                    "usuario": str(usuario.id),
                    **campos_moeda,
                },
            )
        )
        .mappings()
        .one()
    )

    await servico.aplica_tags(conexao, novo["id"], corpo.tag_ids)

    linha = await servico.exige_lancamento(conexao, novo["id"])
    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=novo["id"],
        acao="criacao",
        usuario_id=usuario.id,
        depois={
            "mundo": mundo_validado,
            "tipo": corpo.tipo,
            "descricao": corpo.descricao,
            "valor": campos_moeda["valor"],
            "data": corpo.data,
            "status": status,
        },
    )
    return linha


@roteador.post(
    "",
    status_code=201,
    summary="Cria um lançamento",
    description=(
        "Papel: gestor, operador. Aceita `Idempotency-Key`. `valor` é sempre positivo — o "
        "sinal vem de `tipo` (`RN-02`). Data no passado ou hoje nasce `efetivado`; futura "
        "nasce `programado` (`FR-024`). Categoria especial exige `subcategoria_id` (`RN-01`)."
    ),
)
async def criar(
    corpo: LancamentoEntrada,
    usuario: Autenticado,
    conexao: Conexao,
    chave: Annotated[str | None, Depends(chave_de_idempotencia)] = None,
) -> dict[str, Any]:
    ja_feito = await resposta_ja_registrada(
        conexao, chave, rota="POST /api/lancamentos", usuario_id=str(usuario.id)
    )
    if ja_feito is not None:
        return ja_feito

    linha = await _grava_lancamento(conexao, corpo, usuario)
    tags = await repositorio.tags_de(conexao, [linha["id"]])
    resposta = servico.para_json(linha, tags.get(str(linha["id"]), []))

    await registra_resposta(
        conexao, chave, rota="POST /api/lancamentos", usuario_id=str(usuario.id), resposta=resposta
    )
    return resposta


# ── T062 · POST /api/lancamentos/lote ───────────────────────────────────────
#
# ⚠️ Ordem de declaração importa: `/lote`, `/acoes-em-massa` e `/exportacao` vêm ANTES
# de `/{lancamento_id}`. O FastAPI casa a rota na ordem em que foi registrada — com
# `/{lancamento_id}` na frente, `GET /api/lancamentos/exportacao` tentaria ler
# "exportacao" como UUID e responderia 400 em vez de exportar.


@roteador.post(
    "/lote",
    summary="Cria vários lançamentos de uma vez (tabela editável)",
    description=(
        "Papel: gestor, operador. **Tudo ou nada** (`FR-021`): uma linha inválida "
        "recusa o lote inteiro e a resposta aponta o índice de **cada** linha com "
        "problema, para a tabela marcar todas de uma vez. Sucesso → `201`; qualquer "
        "recusa → `400` com `{criados: 0, erros: [...]}`."
    ),
    responses={
        400: {
            "description": "Nenhum lançamento foi criado. `erros` traz o índice de cada linha.",
            "content": {
                "application/json": {
                    "example": {
                        "criados": 0,
                        "erros": [
                            {
                                "indice": 3,
                                "codigo": "regra_violada",
                                "requisito": "RN-01",
                                "mensagem": "Escolha qual cliente neste lançamento de Clientes.",
                                "campos": {"subcategoria_id": "Obrigatório em Clientes."},
                            }
                        ],
                    }
                }
            },
        }
    },
)
async def criar_em_lote(
    corpo: LoteEntrada, usuario: Autenticado, conexao: Conexao
) -> ORJSONResponse:
    # Dois níveis de SAVEPOINT. O de fora desfaz o lote inteiro; o de dentro desfaz
    # UMA linha para que a seguinte ainda possa ser tentada — dentro de uma transação,
    # o Postgres recusa qualquer comando depois de um erro até voltar a um savepoint.
    # É esse segundo nível que permite devolver todas as linhas com problema numa
    # resposta só, em vez de o usuário corrigir uma, reenviar e descobrir a próxima.
    erros: list[dict[str, Any]] = []
    criados: list[dict[str, Any]] = []

    lote = await conexao.begin_nested()
    for indice, item in enumerate(corpo.lancamentos):
        linha_sp = await conexao.begin_nested()
        try:
            linha = await _grava_lancamento(conexao, item, usuario)
        except ErroDaApi as erro:
            await linha_sp.rollback()
            erros.append(
                {
                    "indice": indice,
                    "codigo": erro.codigo,
                    "requisito": erro.requisito,
                    "mensagem": erro.mensagem,
                    "campos": erro.campos,
                }
            )
        else:
            await linha_sp.commit()
            criados.append(servico.para_json(linha))

    if erros:
        await lote.rollback()
        return ORJSONResponse(status_code=400, content={"criados": 0, "erros": erros})

    await lote.commit()
    ids = [UUID(item["id"]) for item in criados]
    tags = await repositorio.tags_de(conexao, ids)
    for item in criados:
        item["tags"] = tags.get(item["id"], [])

    return ORJSONResponse(
        status_code=201, content={"criados": len(criados), "erros": [], "itens": criados}
    )


# ── T063 · POST /api/lancamentos/acoes-em-massa ─────────────────────────────


@roteador.post(
    "/acoes-em-massa",
    summary="Aplica uma ação a vários lançamentos selecionados",
    description=(
        "Papel: gestor, operador. `FR-040`. Ações: `excluir`, `mudar_categoria`, "
        "`mudar_status`, `adicionar_tags`, `remover_tags`. **Tudo ou nada**: se um "
        "lançamento recusar, nenhum é alterado. Exportar em massa não passa por aqui — "
        "é `GET /api/lancamentos/exportacao`, que já respeita os filtros da tela."
    ),
)
async def acoes_em_massa(
    corpo: AcoesEmMassaEntrada, usuario: Autenticado, conexao: Conexao
) -> dict[str, Any]:
    ids = [str(x) for x in dict.fromkeys(corpo.lancamento_ids)]  # sem repetir, mantendo a ordem

    encontrados = (
        (
            await conexao.execute(
                text("""
                    select l.id, l.mundo, l.tipo, l.status, l.descricao, l.categoria_id
                    from lancamentos_ativos l where l.id = any(cast(:ids as uuid[]))
                    """),
                {"ids": ids},
            )
        )
        .mappings()
        .all()
    )
    if len(encontrados) != len(ids):
        # Recusa em vez de aplicar no que sobrou: "12 de 15 alterados" numa ação em
        # massa deixa o usuário sem saber quais três ficaram de fora.
        raise ErroNaoEncontrado(
            f"{len(ids) - len(encontrados)} dos lançamentos selecionados não existem mais. "
            "Atualize a lista e selecione de novo."
        )

    if corpo.acao == "excluir":
        for linha in encontrados:
            await excluir(linha["id"], usuario, conexao)
        return {"acao": corpo.acao, "afetados": len(encontrados)}

    if corpo.acao == "mudar_categoria":
        # `RN-01` uma vez por TIPO presente na seleção, não uma vez por lançamento:
        # a categoria de destino é a mesma para todos, e o que varia entre eles é só
        # se é receita ou despesa. Categoria especial sem `subcategoria_id` cai aqui
        # na primeira volta e a seleção inteira é recusada.
        for tipo_selecionado in {linha["tipo"] for linha in encontrados}:
            await servico.valida_classificacao(
                conexao,
                categoria_id=corpo.parametros.categoria_id,  # type: ignore[arg-type]
                subcategoria_id=corpo.parametros.subcategoria_id,
                tipo=tipo_selecionado,
            )
        await conexao.execute(
            text("""
                update lancamentos
                set categoria_id = :categoria_id, subcategoria_id = :subcategoria_id,
                    versao = versao + 1, atualizado_por = cast(:usuario as uuid)
                where id = any(cast(:ids as uuid[]))
                """),
            {
                "ids": ids,
                "categoria_id": str(corpo.parametros.categoria_id),
                "subcategoria_id": (
                    str(corpo.parametros.subcategoria_id)
                    if corpo.parametros.subcategoria_id
                    else None
                ),
                "usuario": str(usuario.id),
            },
        )
        for linha in encontrados:
            await registra_auditoria(
                conexao,
                entidade="lancamentos",
                entidade_id=linha["id"],
                acao="edicao",
                usuario_id=usuario.id,
                alteracoes={
                    "categoria_id": {
                        "de": str(linha["categoria_id"]),
                        "para": str(corpo.parametros.categoria_id),
                    }
                },
            )
        return {"acao": corpo.acao, "afetados": len(encontrados)}

    if corpo.acao == "mudar_status":
        destino = corpo.parametros.status
        for linha in encontrados:
            if linha["status"] == "cancelado" and destino == "efetivado":
                raise ErroRegraViolada(
                    (
                        f"'{linha['descricao']}' está cancelado e não pode ser efetivado. "
                        "Tire-o da seleção ou reabra o lançamento antes."
                    ),
                    requisito="RN-03",
                    campos={"lancamento_ids": "Há lançamento cancelado na seleção."},
                )
        if destino == "efetivado":
            await conexao.execute(
                text("""
                    update lancamentos
                    set status = 'efetivado', efetivado_em = now(),
                        efetivado_por = cast(:usuario as uuid),
                        versao = versao + 1, atualizado_por = cast(:usuario as uuid)
                    where id = any(cast(:ids as uuid[])) and status <> 'efetivado'
                    """),
                {"ids": ids, "usuario": str(usuario.id)},
            )
        else:
            await conexao.execute(
                text("""
                    update lancamentos
                    set status = 'cancelado', versao = versao + 1,
                        atualizado_por = cast(:usuario as uuid)
                    where id = any(cast(:ids as uuid[])) and status <> 'cancelado'
                    """),
                {"ids": ids, "usuario": str(usuario.id)},
            )
        for linha in encontrados:
            await registra_auditoria(
                conexao,
                entidade="lancamentos",
                entidade_id=linha["id"],
                acao="edicao",
                usuario_id=usuario.id,
                alteracoes={"status": {"de": linha["status"], "para": destino}},
            )
        return {"acao": corpo.acao, "afetados": len(encontrados)}

    tag_ids = [str(x) for x in corpo.parametros.tag_ids]
    existentes = (
        await conexao.execute(
            text("select count(*) from tags where id = any(cast(:ids as uuid[]))"),
            {"ids": tag_ids},
        )
    ).scalar_one()
    if existentes != len(set(tag_ids)):
        raise ErroValidacao(
            "Uma ou mais tags não existem.", campos={"tag_ids": "Verifique as tags escolhidas."}
        )

    if corpo.acao == "adicionar_tags":
        await conexao.execute(
            text("""
                insert into lancamentos_tags (lancamento_id, tag_id)
                select l.id, t.id
                from unnest(cast(:ids as uuid[])) as l(id)
                cross join unnest(cast(:tags as uuid[])) as t(id)
                on conflict do nothing
                """),
            {"ids": ids, "tags": tag_ids},
        )
    else:
        await conexao.execute(
            text("""
                delete from lancamentos_tags
                where lancamento_id = any(cast(:ids as uuid[]))
                  and tag_id = any(cast(:tags as uuid[]))
                """),
            {"ids": ids, "tags": tag_ids},
        )

    for linha in encontrados:
        await registra_auditoria(
            conexao,
            entidade="lancamentos",
            entidade_id=linha["id"],
            acao="edicao",
            usuario_id=usuario.id,
            alteracoes={corpo.acao: {"de": None, "para": tag_ids}},
        )
    return {"acao": corpo.acao, "afetados": len(encontrados)}


# ── T065 · GET /api/lancamentos/exportacao ──────────────────────────────────


@roteador.get(
    "/exportacao",
    summary="Exporta a lista filtrada em CSV",
    description=(
        "Papel: gestor, operador. `FR-045`. Aceita **os mesmos filtros** de "
        "`GET /api/lancamentos` — o arquivo é exatamente o que está na tela, não a "
        "base inteira. Para a base inteira existe `POST /api/exportacoes/completa`.\n\n"
        "`id` (repetível) restringe aos lançamentos escolhidos: é o 'exportar' da barra "
        "de ações em massa (`FR-040`). Sem ele, aquele botão exportava a lista filtrada "
        "inteira e ignorava a seleção em silêncio."
    ),
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "Arquivo CSV."}},
)
async def exportar(
    usuario: Autenticado,
    conexao: Conexao,
    formato: Annotated[str, Query(description="Hoje só `csv`.")] = "csv",
    mundo: Annotated[str | None, Query()] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    tipo: Annotated[str | None, Query()] = None,
    categoria_id: Annotated[list[UUID] | None, Query()] = None,
    subcategoria_id: Annotated[list[UUID] | None, Query()] = None,
    servico_id: Annotated[list[UUID] | None, Query()] = None,
    centro_custo_id: Annotated[list[UUID] | None, Query()] = None,
    tag_id: Annotated[list[UUID] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
    valor_min: Annotated[Decimal | None, Query()] = None,
    valor_max: Annotated[Decimal | None, Query()] = None,
    busca: Annotated[str | None, Query()] = None,
    id: Annotated[  # noqa: A002 — o nome do parâmetro é público, vem do contrato
        list[UUID] | None,
        Query(description="Repetível. Exporta só estes lançamentos (`FR-040`)."),
    ] = None,
) -> Response:
    if formato != "csv":
        raise ErroValidacao(
            f"Formato '{formato}' não é exportável aqui.",
            requisito="FR-045",
            campos={"formato": "Use csv."},
        )

    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)
    condicoes, parametros = repositorio.monta_filtros(
        mundos=mundos,
        inicio=janela.inicio,
        fim=janela.fim,
        tipo=tipo,
        categoria_ids=categoria_id,
        subcategoria_ids=subcategoria_id,
        servico_ids=servico_id,
        centro_custo_ids=centro_custo_id,
        tag_ids=tag_id,
        status=status,
        valor_min=valor_min,
        valor_max=valor_max,
        busca=busca,
        ids=id,
    )

    agregado = await repositorio.conta_e_soma(conexao, condicoes=condicoes, parametros=parametros)
    if agregado["quantidade"] > TETO_EXPORTACAO:
        raise ErroValidacao(
            (
                f"São {agregado['quantidade']} lançamentos, acima do limite de "
                f"{TETO_EXPORTACAO} desta exportação. Estreite o período ou os filtros — "
                "ou use a exportação completa, que roda em segundo plano."
            ),
            requisito="FR-045",
            campos={"filtros": "Resultado grande demais para um arquivo só."},
        )

    linhas = await repositorio.para_exportacao(
        conexao, condicoes=condicoes, parametros=parametros, limite=TETO_EXPORTACAO
    )
    csv = exportacao_csv.monta(linhas)
    nome = exportacao_csv.nome_do_arquivo(janela.inicio, janela.fim, mundo)

    return Response(
        content=csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


# ── T057 · GET /api/lancamentos/{id} ────────────────────────────────────────


@roteador.get(
    "/{lancamento_id}",
    summary="Detalhe, com histórico e ações disponíveis",
    description=(
        "Papel: gestor, operador. `acoes_disponiveis` é calculado no servidor a partir do "
        "status — o frontend não decide quando mostrar 'confirmar recebimento' (`FR-042`)."
    ),
)
async def detalhar(lancamento_id: UUID, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    linha = await servico.exige_lancamento(conexao, lancamento_id)
    tags = await repositorio.tags_de(conexao, [linha["id"]])
    detalhe = servico.para_json(linha, tags.get(str(linha["id"]), []))

    partes = (
        (
            await conexao.execute(
                text("""
                    select l.id, l.descricao, l.valor, c.nome as categoria_nome, c.cor as categoria_cor
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    where l.lancamento_pai_id = :id
                    order by l.criado_em
                    """),
                {"id": str(lancamento_id)},
            )
        )
        .mappings()
        .all()
    )

    historico = (
        (
            await conexao.execute(
                text("""
                    select a.acao, a.alteracoes, a.criado_em, u.id as usuario_id, u.nome as usuario_nome
                    from auditoria a
                    join usuarios u on u.id = a.usuario_id
                    where a.entidade = 'lancamentos' and a.entidade_id = :id
                    order by a.criado_em desc
                    """),
                {"id": str(lancamento_id)},
            )
        )
        .mappings()
        .all()
    )

    detalhe["partes_split"] = [
        {
            "id": str(p["id"]),
            "descricao": p["descricao"],
            "valor": f"{p['valor']:.2f}",
            "categoria": {"nome": p["categoria_nome"], "cor": p["categoria_cor"]},
        }
        for p in partes
    ]
    detalhe["lancamento_pai"] = (
        str(linha["lancamento_pai_id"]) if linha["lancamento_pai_id"] else None
    )
    detalhe["historico"] = [
        {
            "acao": h["acao"],
            "usuario": {"id": str(h["usuario_id"]), "nome": h["usuario_nome"]},
            "criado_em": h["criado_em"].isoformat(),
            "alteracoes": (h["alteracoes"] or {}).get("campos", {}),
            "alteracao_historica": (h["alteracoes"] or {}).get("alteracao_historica", False),
        }
        for h in historico
    ]
    # `RF-013a`: parte de split não tem anexo próprio — mostra o do pai, que é o mesmo
    # comprovante. Vai no detalhe em vez de um endpoint separado porque `FR-041` pede
    # os anexos junto do resto, e endpoint que `contracts/` não declara é divergência
    # (T208).
    detalhe["anexos"] = await lista_do_lancamento(
        conexao, lancamento_id, lancamento_pai_id=linha["lancamento_pai_id"]
    )
    detalhe["acoes_disponiveis"] = servico.acoes_disponiveis(linha)
    return detalhe


# ── T058 · PUT /api/lancamentos/{id} ────────────────────────────────────────


@roteador.put(
    "/{lancamento_id}",
    summary="Edita, com controle de versão",
    description=(
        "Papel: gestor, operador. `versao` divergente → `409 conflito_versao` com o que "
        "mudou desde a leitura (data-model §5.6). Mudar `mundo` → `409` / `RN-15`."
    ),
)
async def editar(
    lancamento_id: UUID, corpo: LancamentoEdicao, usuario: Autenticado, conexao: Conexao
) -> dict[str, Any]:
    atual = await servico.exige_lancamento(conexao, lancamento_id)
    mod_lixeira.exige_nao_excluido(atual["excluido_em"])

    # RN-15 antes de tudo: mundo diferente é recusa, não edição parcial.
    mod_mundo.recusa_alteracao(atual["mundo"], corpo.mundo)

    if corpo.versao != atual["versao"]:
        raise ErroConflitoVersao(
            (
                "Este lançamento foi alterado por outra pessoa enquanto você editava. "
                "Recarregue para ver a versão atual antes de salvar."
            ),
            versao_atual=atual["versao"],
            mudancas={
                "valor": f"{atual['valor']:.2f}",
                "descricao": atual["descricao"],
                "status": atual["status"],
            },
        )

    categoria = await servico.valida_classificacao(
        conexao,
        categoria_id=corpo.categoria_id,
        subcategoria_id=corpo.subcategoria_id,
        tipo=corpo.tipo,
    )
    await servico.valida_vinculos_de_mundo(
        conexao,
        mundo=atual["mundo"],
        servico_id=corpo.servico_id,
        centro_custo_id=corpo.centro_custo_id,
    )

    cotacao = None
    if corpo.moeda == "USD":
        cotacao = await servico.obtem_cotacao(conexao, corpo.data, corpo.cotacao_manual)
    campos_moeda = cambio.campos_do_lancamento(
        valor_informado=corpo.valor, moeda=corpo.moeda, cotacao=cotacao
    )

    efetivar_auto = await servico.resolve_efetivacao_automatica(
        conexao, informado=corpo.efetivar_automaticamente, tipo=corpo.tipo, categoria=categoria
    )

    await conexao.execute(
        text("""
            update lancamentos set
              tipo = cast(:tipo as tipo_lancamento), descricao = :descricao, valor = :valor,
              data = :data, categoria_id = :categoria_id, subcategoria_id = :subcategoria_id,
              servico_id = :servico_id, centro_custo_id = :centro_custo_id,
              observacoes = :observacoes, efetivar_automaticamente = :efetivar_automaticamente,
              moeda_origem = cast(:moeda_origem as moeda), valor_origem = :valor_origem,
              cotacao = :cotacao, cotacao_data = :cotacao_data, cotacao_manual = :cotacao_manual,
              versao = versao + 1, atualizado_por = cast(:usuario as uuid)
            where id = :id
            """),
        {
            "id": str(lancamento_id),
            "tipo": corpo.tipo,
            "descricao": corpo.descricao,
            "data": corpo.data,
            "categoria_id": str(corpo.categoria_id),
            "subcategoria_id": str(corpo.subcategoria_id) if corpo.subcategoria_id else None,
            "servico_id": str(corpo.servico_id) if corpo.servico_id else None,
            "centro_custo_id": str(corpo.centro_custo_id) if corpo.centro_custo_id else None,
            "observacoes": corpo.observacoes,
            "efetivar_automaticamente": efetivar_auto,
            "usuario": str(usuario.id),
            **campos_moeda,
        },
    )
    await servico.aplica_tags(conexao, lancamento_id, corpo.tag_ids)

    depois = await servico.exige_lancamento(conexao, lancamento_id)
    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=lancamento_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes={k: atual[k] for k in ("descricao", "valor", "data", "tipo", "categoria_id")},
        depois={k: depois[k] for k in ("descricao", "valor", "data", "tipo", "categoria_id")},
        alteracao_historica=(atual["status"] == "efetivado" and atual["data"] < date.today()),
    )

    tags = await repositorio.tags_de(conexao, [lancamento_id])
    return servico.para_json(depois, tags.get(str(lancamento_id), []))


# ── T059 · DELETE + lixeira ─────────────────────────────────────────────────


@roteador.delete(
    "/{lancamento_id}",
    status_code=204,
    summary="Exclui (soft delete)",
    description=(
        "Papel: gestor, operador. Vai para a lixeira (`RN-08`); a linha nunca sai do banco. "
        "Só a ocorrência, nunca a série. Excluir uma parte de split é recusado — quebraria "
        "`RN-11`."
    ),
)
async def excluir(lancamento_id: UUID, usuario: Autenticado, conexao: Conexao) -> None:
    linha = await servico.exige_lancamento(conexao, lancamento_id)

    if linha["lancamento_pai_id"] is not None:
        raise ErroRegraViolada(
            (
                "Esta é uma parte de um lançamento dividido. Excluí-la faria a soma das "
                "partes deixar de fechar com o valor original."
            ),
            requisito="RN-11",
            campos={"lancamento": "Ajuste as outras partes ou exclua o lançamento original."},
        )

    # Excluir o pai leva as partes junto: deixá-las órfãs violaria RN-06 e elas
    # continuariam somando nos totais sem o pai existir.
    await conexao.execute(
        text("""
            update lancamentos set excluido_em = now(), excluido_por = cast(:usuario as uuid)
            where (id = :id or lancamento_pai_id = :id) and excluido_em is null
            """),
        {"id": str(lancamento_id), "usuario": str(usuario.id)},
    )
    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=lancamento_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={"excluido_em": {"de": None, "para": "agora"}},
    )


@roteador_lixeira.get(
    "",
    summary="Lançamentos na lixeira, com dias restantes",
    description="Papel: gestor, operador. `RN-08`, `FR-017`.",
)
async def listar_lixeira(usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    retencao = int(await servico.le_configuracao(conexao, "lixeira_retencao_dias", padrao=90))

    linhas = (
        (
            await conexao.execute(
                text("""
                    select l.id, l.mundo, l.tipo, l.descricao, l.valor, l.data, l.status,
                           l.excluido_em, c.nome as categoria_nome, c.cor as categoria_cor,
                           u.nome as excluido_por_nome
                    from lancamentos l
                    join categorias c on c.id = l.categoria_id
                    left join usuarios u on u.id = l.excluido_por
                    where l.excluido_em is not null
                    order by l.excluido_em desc
                    """)
            )
        )
        .mappings()
        .all()
    )

    return {
        "itens": [
            {
                "id": str(linha["id"]),
                "mundo": linha["mundo"],
                "tipo": linha["tipo"],
                "descricao": linha["descricao"],
                "valor": f"{linha['valor']:.2f}",
                "data": linha["data"].isoformat(),
                "categoria": {"nome": linha["categoria_nome"], "cor": linha["categoria_cor"]},
                "excluido_em": linha["excluido_em"].isoformat(),
                "excluido_por": linha["excluido_por_nome"],
                "dias_restantes": mod_lixeira.dias_restantes(
                    linha["excluido_em"], retencao_dias=retencao
                ),
                "pode_restaurar": mod_lixeira.pode_restaurar(
                    linha["excluido_em"], retencao_dias=retencao
                ),
            }
            for linha in linhas
        ],
        "retencao_dias": retencao,
    }


@roteador_lixeira.post(
    "/{lancamento_id}/restaurar",
    summary="Restaura da lixeira",
    description="Papel: gestor, operador. Fora do prazo → `409` / `RN-08`.",
)
async def restaurar(lancamento_id: UUID, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    linha = await servico.exige_lancamento(conexao, lancamento_id, incluir_excluido=True)
    if linha["excluido_em"] is None:
        raise ErroNaoEncontrado("Este lançamento não está na lixeira.")

    retencao = int(await servico.le_configuracao(conexao, "lixeira_retencao_dias", padrao=90))
    mod_lixeira.exige_pode_restaurar(linha["excluido_em"], retencao_dias=retencao)

    await conexao.execute(
        text(
            "update lancamentos set excluido_em = null, excluido_por = null "
            "where id = :id or lancamento_pai_id = :id"
        ),
        {"id": str(lancamento_id)},
    )
    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=lancamento_id,
        acao="restauracao",
        usuario_id=usuario.id,
        alteracoes={"excluido_em": {"de": linha["excluido_em"].isoformat(), "para": None}},
    )

    restaurado = await servico.exige_lancamento(conexao, lancamento_id)
    return servico.para_json(restaurado)


# ── T060 · efetivar · cancelar · duplicar ───────────────────────────────────


@roteador.post(
    "/{lancamento_id}/efetivar",
    summary="Confirma o recebimento/pagamento em 1 clique",
    description="Papel: gestor, operador. `FR-030`, `FR-042`. Já efetivado → `409`.",
)
async def efetivar(lancamento_id: UUID, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    linha = await servico.exige_lancamento(conexao, lancamento_id)
    mod_lixeira.exige_nao_excluido(linha["excluido_em"])

    if linha["status"] == "efetivado":
        raise ErroRegraViolada(
            "Este lançamento já está efetivado.",
            requisito="RN-03",
            campos={"status": "Já efetivado."},
        )
    if linha["status"] == "cancelado":
        raise ErroRegraViolada(
            "Um lançamento cancelado não pode ser efetivado.",
            requisito="RN-03",
            campos={"status": "Cancelado."},
        )

    await conexao.execute(
        text("""
            update lancamentos set status = 'efetivado', efetivado_em = now(),
                   efetivado_por = cast(:usuario as uuid), versao = versao + 1,
                   atualizado_por = cast(:usuario as uuid)
            where id = :id
            """),
        {"id": str(lancamento_id), "usuario": str(usuario.id)},
    )
    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=lancamento_id,
        acao="edicao",
        usuario_id=usuario.id,
        alteracoes={"status": {"de": linha["status"], "para": "efetivado"}},
    )
    return servico.para_json(await servico.exige_lancamento(conexao, lancamento_id))


@roteador.post(
    "/{lancamento_id}/cancelar",
    summary="Cancela, preservando o histórico",
    description="Papel: gestor, operador. `RN-03`: sai dos totais, a linha continua.",
)
async def cancelar(lancamento_id: UUID, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    linha = await servico.exige_lancamento(conexao, lancamento_id)
    mod_lixeira.exige_nao_excluido(linha["excluido_em"])

    if linha["status"] == "cancelado":
        raise ErroRegraViolada(
            "Este lançamento já está cancelado.", requisito="RN-03", campos={"status": "Cancelado."}
        )

    await conexao.execute(
        text(
            "update lancamentos set status = 'cancelado', versao = versao + 1, "
            "atualizado_por = cast(:usuario as uuid) where id = :id"
        ),
        {"id": str(lancamento_id), "usuario": str(usuario.id)},
    )
    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=lancamento_id,
        acao="edicao",
        usuario_id=usuario.id,
        alteracoes={"status": {"de": linha["status"], "para": "cancelado"}},
    )
    return servico.para_json(await servico.exige_lancamento(conexao, lancamento_id))


@roteador.post(
    "/{lancamento_id}/duplicar",
    status_code=201,
    summary="Duplica com a data de hoje",
    description=(
        "Papel: gestor, operador. `FR-018`. Cópia com `data` = hoje, status recalculado, "
        "**sem anexos e sem vínculo de série** — a cópia é um lançamento novo, não outra "
        "ocorrência da mesma recorrência."
    ),
)
async def duplicar(lancamento_id: UUID, usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    origem = await servico.exige_lancamento(conexao, lancamento_id)

    novo = (
        (
            await conexao.execute(
                text("""
                    insert into lancamentos (
                      mundo, tipo, descricao, valor, data, status,
                      categoria_id, subcategoria_id, servico_id, centro_custo_id,
                      observacoes, efetivar_automaticamente,
                      efetivado_em, efetivado_por,
                      moeda_origem, valor_origem, cotacao, cotacao_data, cotacao_manual,
                      criado_por
                    )
                    select mundo, tipo, descricao, valor, current_date, 'efetivado',
                           categoria_id, subcategoria_id, servico_id, centro_custo_id,
                           observacoes, efetivar_automaticamente,
                           now(), cast(:usuario as uuid),
                           moeda_origem, valor_origem, cotacao, cotacao_data, cotacao_manual,
                           cast(:usuario as uuid)
                    from lancamentos where id = :id
                    returning id
                    """),
                {"id": str(lancamento_id), "usuario": str(usuario.id)},
            )
        )
        .mappings()
        .one()
    )

    tags_origem = await repositorio.tags_de(conexao, [origem["id"]])
    await servico.aplica_tags(
        conexao, novo["id"], [UUID(t["id"]) for t in tags_origem.get(str(origem["id"]), [])]
    )

    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=novo["id"],
        acao="criacao",
        usuario_id=usuario.id,
        alteracoes={"duplicado_de": {"de": None, "para": str(lancamento_id)}},
    )

    linha = await servico.exige_lancamento(conexao, novo["id"])
    tags = await repositorio.tags_de(conexao, [linha["id"]])
    return servico.para_json(linha, tags.get(str(linha["id"]), []))


# ── T061 · dividir (RN-11) ──────────────────────────────────────────────────


@roteador.post(
    "/{lancamento_id}/dividir",
    status_code=201,
    summary="Divide em partes com categorias diferentes",
    description=(
        "Papel: gestor, operador. `FR-019`, `FR-020`, `RN-11`. A soma das partes precisa "
        "fechar exatamente com o valor do lançamento; a diferença vem na mensagem. Depois "
        "da divisão **o pai sai dos totais** — só as partes contam."
    ),
)
async def dividir(
    lancamento_id: UUID, corpo: DivisaoEntrada, usuario: Autenticado, conexao: Conexao
) -> dict[str, Any]:
    pai = await servico.exige_lancamento(conexao, lancamento_id)
    mod_lixeira.exige_nao_excluido(pai["excluido_em"])

    mod_split.valida_pode_dividir(
        e_parte_de_split=pai["lancamento_pai_id"] is not None, tem_partes=pai["tem_partes"]
    )
    mod_split.valida_soma(Decimal(str(pai["valor"])), [parte.valor for parte in corpo.partes])

    for parte in corpo.partes:
        # A parte herda o `tipo` do pai (contracts §1), então é o tipo dele que a
        # categoria da parte precisa aceitar.
        await servico.valida_classificacao(
            conexao,
            categoria_id=parte.categoria_id,
            subcategoria_id=parte.subcategoria_id,
            tipo=pai["tipo"],
        )
        await servico.valida_vinculos_de_mundo(
            conexao, mundo=pai["mundo"], servico_id=None, centro_custo_id=parte.centro_custo_id
        )
        # As partes herdam mundo, data, tipo e status do pai (contracts §1). Anexos
        # ficam no pai e são lidos por herança (RF-013a).
        await conexao.execute(
            text("""
                insert into lancamentos (
                  mundo, tipo, descricao, valor, data, status,
                  categoria_id, subcategoria_id, centro_custo_id,
                  efetivar_automaticamente, efetivado_em, efetivado_por,
                  lancamento_pai_id, criado_por
                )
                select mundo, tipo, :descricao, :valor, data, status,
                       :categoria_id, :subcategoria_id, :centro_custo_id,
                       efetivar_automaticamente, efetivado_em, efetivado_por,
                       :pai, cast(:usuario as uuid)
                from lancamentos where id = :pai
                """),
            {
                "pai": str(lancamento_id),
                "descricao": parte.descricao,
                "valor": parte.valor,
                "categoria_id": str(parte.categoria_id),
                "subcategoria_id": str(parte.subcategoria_id) if parte.subcategoria_id else None,
                "centro_custo_id": str(parte.centro_custo_id) if parte.centro_custo_id else None,
                "usuario": str(usuario.id),
            },
        )

    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=lancamento_id,
        acao="edicao",
        usuario_id=usuario.id,
        alteracoes={"dividido_em": {"de": None, "para": len(corpo.partes)}},
    )

    return await detalhar(lancamento_id, usuario, conexao)


# ── T066 · GET /api/saldo (RN-05, RN-16) ────────────────────────────────────


@roteador_saldo.get(
    "",
    summary="Saldo do caixa, com quebra por mundo",
    description=(
        "Papel: gestor, operador. `RN-05`: só `efetivado` entra. `RN-16`: separado por "
        "mundo, consolidado no modo Ambos. **Não existe saldo inicial** (`FR-114`) — o "
        "saldo é exclusivamente o resultado dos lançamentos efetivados, então enquanto o "
        "histórico não estiver carregado o número fica menor que a realidade."
    ),
)
async def obter_saldo(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
) -> dict[str, Any]:
    await rotina_diaria.executa_se_necessario(conexao)  # T085

    mundos = mod_mundo.resolve_filtro(mundo)
    por_mundo_bruto = await repositorio.saldo_por_mundo(conexao, mundos)

    por_mundo: dict[str, str] = {}
    total = Decimal("0.00")
    for nome in mod_mundo.MUNDOS:
        dados = por_mundo_bruto.get(nome)
        saldo_do_mundo = (
            Decimal(str(dados["receitas"])) - Decimal(str(dados["despesas"]))
            if dados
            else Decimal("0.00")
        )
        # O mundo aparece na quebra mesmo zerado — sumir esconderia o mundo sem
        # movimento no modo Ambos (edge case da spec).
        por_mundo[nome] = f"{saldo_do_mundo:.2f}"
        if nome in mundos:
            total += saldo_do_mundo

    resposta: dict[str, Any] = {"saldo": f"{total:.2f}", "sem_saldo_inicial": True}
    if mod_mundo.deve_quebrar_por_mundo(mundo):
        resposta["por_mundo"] = por_mundo
    return resposta
