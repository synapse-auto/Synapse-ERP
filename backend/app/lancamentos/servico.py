"""Serviço de lançamentos: orquestra domínio, banco e auditoria (Princípio IV).

Camada do meio. As regras (`RN-xx`) moram em `app/dominio/`; o SQL mora em
`repositorio.py`; aqui se decide a **ordem** das coisas e se grava a auditoria na mesma
transação da escrita.

Tarefa: T054
"""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import cache_configuracoes
from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada, ErroValidacao
from app.config import obter_configuracao
from app.dominio import cambio
from app.dominio import mundo as mod_mundo
from app.lancamentos import repositorio

TEMPO_LIMITE_CAMBIO = httpx.Timeout(4.0)


# ── Configuração (Princípio VII: parâmetro é dado, não código) ───────────────


async def le_configuracao(conexao: AsyncConnection, chave: str, padrao: Any = None) -> Any:
    """Um parâmetro de negócio, de `configuracoes`.

    A assinatura é a de sempre; o que mudou por baixo é que a tabela inteira vem numa
    consulta só e fica em memória por um minuto, em vez de uma viagem ao banco por
    chave. Motivo e limites em `app/comum/cache_configuracoes.py`.
    """
    return await cache_configuracoes.le(conexao, chave, padrao)


# ── `RN-01` — subcategoria obrigatória em categoria especial ─────────────────


async def valida_classificacao(
    conexao: AsyncConnection,
    *,
    categoria_id: UUID,
    subcategoria_id: UUID | None,
    tipo: str | None = None,
) -> dict[str, Any]:
    """`RN-01`: sem categoria não salva; categoria especial exige subcategoria.

    `tipo` confere se a categoria aceita receita, despesa ou as duas
    (`categorias.tipo`, enum `tipo_categoria`). Fica aqui, e não em cada rota, para
    criar, editar, dividir e mudar em massa aplicarem a mesma checagem — regra em
    quatro lugares é regra que vai divergir (Princípio III).
    """
    categoria = (
        (
            await conexao.execute(
                text(
                    "select id, nome, tipo, especial, vinculo, arquivada_em "
                    "from categorias where id = :id"
                ),
                {"id": str(categoria_id)},
            )
        )
        .mappings()
        .first()
    )
    if categoria is None:
        raise ErroValidacao(
            "Categoria não encontrada.", requisito="RN-01", campos={"categoria_id": "Inválida."}
        )
    if categoria["arquivada_em"] is not None:
        raise ErroValidacao(
            f"A categoria '{categoria['nome']}' está arquivada e não aceita lançamentos novos.",
            requisito="RN-06",
            campos={"categoria_id": "Escolha uma categoria ativa."},
        )

    if tipo is not None and categoria["tipo"] != "ambas" and categoria["tipo"] != tipo:
        aceita = "receitas" if categoria["tipo"] == "receita" else "despesas"
        raise ErroRegraViolada(
            f"A categoria '{categoria['nome']}' é de {aceita} e não aceita este lançamento.",
            requisito="RN-01",
            campos={"categoria_id": f"Só aceita {aceita}."},
        )

    if categoria["especial"] and subcategoria_id is None:
        # A mensagem nomeia o que falta em linguagem de negócio: em Clientes falta
        # "qual cliente", não "uma subcategoria".
        qual = "cliente" if categoria["vinculo"] == "cliente" else "funcionário"
        raise ErroRegraViolada(
            f"Escolha qual {qual} neste lançamento de {categoria['nome']}.",
            requisito="RN-01",
            campos={"subcategoria_id": f"Obrigatório em {categoria['nome']}."},
        )

    if subcategoria_id is not None:
        pertence = (
            await conexao.execute(
                text(
                    "select 1 from subcategorias "
                    "where id = :id and categoria_id = :categoria_id and arquivada_em is null"
                ),
                {"id": str(subcategoria_id), "categoria_id": str(categoria_id)},
            )
        ).first()
        if pertence is None:
            raise ErroValidacao(
                "A subcategoria escolhida não pertence a esta categoria.",
                requisito="RN-01",
                campos={"subcategoria_id": "Inválida para a categoria informada."},
            )

    return dict(categoria)


async def valida_vinculos_de_mundo(
    conexao: AsyncConnection,
    *,
    mundo: str,
    servico_id: UUID | None,
    centro_custo_id: UUID | None,
) -> None:
    """Serviço e centro de custo têm mundo — têm que ser do mesmo mundo do lançamento.

    Sem isto daria para lançar no Digital marcando "Energia Solar", que é do Infra, e o
    relatório por serviço passaria a misturar os dois mundos (`SC-005`).
    """
    if servico_id is not None:
        linha = (
            (
                await conexao.execute(
                    text("select nome, mundo, ativo from servicos where id = :id"),
                    {"id": str(servico_id)},
                )
            )
            .mappings()
            .first()
        )
        if linha is None:
            raise ErroValidacao("Serviço não encontrado.", campos={"servico_id": "Inválido."})
        if linha["mundo"] != mundo:
            raise ErroRegraViolada(
                (
                    f"O serviço '{linha['nome']}' é de {mod_mundo.ROTULOS[linha['mundo']]} e "
                    f"não pode ser usado num lançamento de {mod_mundo.ROTULOS[mundo]}."
                ),
                requisito="RN-15",
                campos={"servico_id": "Serviço de outro mundo."},
            )

    if centro_custo_id is not None:
        linha = (
            (
                await conexao.execute(
                    text("select nome, mundo, arquivado_em from centros_custo where id = :id"),
                    {"id": str(centro_custo_id)},
                )
            )
            .mappings()
            .first()
        )
        if linha is None:
            raise ErroValidacao(
                "Centro de custo não encontrado.", campos={"centro_custo_id": "Inválido."}
            )
        if linha["mundo"] != mundo:
            raise ErroRegraViolada(
                (f"O centro de custo '{linha['nome']}' é de {mod_mundo.ROTULOS[linha['mundo']]}."),
                requisito="RN-15",
                campos={"centro_custo_id": "Centro de custo de outro mundo."},
            )


# ── `RN-03` / `RN-04` — status inicial ──────────────────────────────────────


def status_inicial(*, data_do_lancamento: date, efetivar_automaticamente: bool) -> str:
    """`FR-024`: data no passado ou hoje nasce `efetivado`; futura nasce `programado`.

    Quem nasce no passado é `efetivado` **independente** do checkbox — o dinheiro já se
    moveu. O checkbox decide o que acontece quando a data futura chega (`RN-04`), e é
    por isso que `atrasado` só existe com ele desligado.
    """
    if data_do_lancamento <= date.today():
        return "efetivado"
    return "programado"


async def resolve_efetivacao_automatica(
    conexao: AsyncConnection,
    *,
    informado: bool | None,
    tipo: str,
    categoria: dict[str, Any],
) -> bool:
    """O padrão vem de `configuracoes`, nunca fixo no código (`RNF-02`, D-05).

    Receita de categoria de cliente tem padrão próprio, e ele é `false` de propósito:
    o alerta de inadimplência (`RN-10`) só existe se a efetivação for manual, porque só
    assim o lançamento pode ficar `atrasado`.
    """
    if informado is not None:
        return informado

    e_receita_de_cliente = tipo == "receita" and categoria.get("vinculo") == "cliente"
    chave = (
        "efetivacao_automatica_padrao_receita_cliente"
        if e_receita_de_cliente
        else "efetivacao_automatica_padrao"
    )
    return bool(await le_configuracao(conexao, chave, padrao=True))


# ── `RN-12` — as fontes de câmbio de verdade ────────────────────────────────


async def _do_cache(conexao: AsyncConnection, data: date) -> cambio.Cotacao | None:
    linha = (
        (
            await conexao.execute(
                text(
                    "select data, taxa, fonte from cotacoes_cambio "
                    "where data = :data and par = :par"
                ),
                {"data": data, "par": cambio.PAR},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        return None
    return cambio.Cotacao(data=linha["data"], taxa=linha["taxa"], fonte=linha["fonte"])


async def _awesomeapi(data: date) -> cambio.Cotacao | None:
    """https://docs.awesomeapi.com.br — cotação por dia."""
    inicio = data.strftime("%Y%m%d")
    url = f"https://economia.awesomeapi.com.br/json/daily/USD-BRL/1?start_date={inicio}&end_date={inicio}"
    async with httpx.AsyncClient(timeout=TEMPO_LIMITE_CAMBIO) as cliente:
        resposta = await cliente.get(url)
        resposta.raise_for_status()
        dados = resposta.json()
    if not dados:
        return None
    return cambio.Cotacao(data=data, taxa=Decimal(str(dados[0]["bid"])), fonte="awesomeapi")


async def _bcb_ptax(data: date) -> cambio.Cotacao | None:
    """PTAX do Banco Central. Não publica em fim de semana e feriado — daí o `None`."""
    dia = data.strftime("%m-%d-%Y")
    url = (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        f"CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{dia}'&$format=json"
    )
    async with httpx.AsyncClient(timeout=TEMPO_LIMITE_CAMBIO) as cliente:
        resposta = await cliente.get(url)
        resposta.raise_for_status()
        dados = resposta.json().get("value") or []
    if not dados:
        return None
    return cambio.Cotacao(data=data, taxa=Decimal(str(dados[0]["cotacaoCompra"])), fonte="bcb_ptax")


_FONTES = {"awesomeapi": _awesomeapi, "bcb_ptax": _bcb_ptax}


async def obtem_cotacao(
    conexao: AsyncConnection, data: date, cotacao_manual: Decimal | None
) -> cambio.Cotacao:
    """Monta as fontes de `configuracoes` e delega a ordem de busca ao domínio."""
    configuracao = obter_configuracao()
    nome_primaria = configuracao.cambio_fonte_primaria or await le_configuracao(
        conexao, "cambio_fonte_primaria", padrao="awesomeapi"
    )
    nome_alternativa = await le_configuracao(conexao, "cambio_fonte_alternativa", padrao="bcb_ptax")

    async def do_cache(quando: date) -> cambio.Cotacao | None:
        return await _do_cache(conexao, quando)

    cotacao = await cambio.obtem_cotacao(
        data,
        buscar_no_cache=do_cache,
        fonte_primaria=_FONTES.get(str(nome_primaria)),
        fonte_alternativa=_FONTES.get(str(nome_alternativa)),
        cotacao_manual=cotacao_manual,
    )

    # Guarda no cache o que veio de fora. A manual não entra: é do lançamento, não uma
    # cotação de mercado que outros lançamentos devam herdar.
    if not cotacao.manual and cotacao.fonte != "cache":
        await conexao.execute(
            text("""
                insert into cotacoes_cambio (data, par, taxa, fonte)
                values (:data, :par, :taxa, :fonte)
                on conflict (data, par) do nothing
                """),
            {"data": cotacao.data, "par": cambio.PAR, "taxa": cotacao.taxa, "fonte": cotacao.fonte},
        )

    return cotacao


# ── Tags ────────────────────────────────────────────────────────────────────


async def aplica_tags(conexao: AsyncConnection, lancamento_id: UUID, tag_ids: list[UUID]) -> None:
    await conexao.execute(
        text("delete from lancamentos_tags where lancamento_id = :id"),
        {"id": str(lancamento_id)},
    )
    if not tag_ids:
        return
    existentes = (
        await conexao.execute(
            text("select count(*) from tags where id = any(cast(:ids as uuid[]))"),
            {"ids": [str(x) for x in tag_ids]},
        )
    ).scalar_one()
    if existentes != len(set(tag_ids)):
        raise ErroValidacao(
            "Uma ou mais tags não existem.", campos={"tag_ids": "Verifique as tags escolhidas."}
        )
    await conexao.execute(
        text(
            "insert into lancamentos_tags (lancamento_id, tag_id) "
            "select :id, unnest(cast(:ids as uuid[])) on conflict do nothing"
        ),
        {"id": str(lancamento_id), "ids": [str(x) for x in tag_ids]},
    )


# ── Busca com erro em PT-BR ─────────────────────────────────────────────────


async def exige_lancamento(
    conexao: AsyncConnection, lancamento_id: UUID, *, incluir_excluido: bool = False
) -> dict[str, Any]:
    linha = await repositorio.por_id(conexao, lancamento_id, incluir_excluido=incluir_excluido)
    if linha is None:
        raise ErroNaoEncontrado("Lançamento não encontrado.")
    return linha


# ── Serialização para a fronteira ───────────────────────────────────────────


def _dinheiro(valor: Any) -> str | None:
    return None if valor is None else f"{Decimal(str(valor)):.2f}"


def _origem(linha: dict[str, Any]) -> dict[str, Any]:
    """`FR-043`: de onde este lançamento veio."""
    if linha["recorrencia_id"]:
        return {"tipo": "recorrencia", "id": str(linha["recorrencia_id"]), "rotulo": "Recorrente"}
    if linha["parcelamento_id"]:
        posicao = f"{linha['parcela_numero']}/{linha['parcela_total']}"
        return {
            "tipo": "parcelamento",
            "id": str(linha["parcelamento_id"]),
            "rotulo": f"Parcela {posicao}",
        }
    if linha["lancamento_pai_id"]:
        return {
            "tipo": "split",
            "id": str(linha["lancamento_pai_id"]),
            "rotulo": "Parte de um lançamento dividido",
        }
    return {"tipo": "manual", "id": None, "rotulo": None}


def para_json(linha: dict[str, Any], tags: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Formato da lista — contracts/lancamentos.md §1."""
    return {
        "id": str(linha["id"]),
        "mundo": linha["mundo"],
        "tipo": linha["tipo"],
        "descricao": linha["descricao"],
        "valor": _dinheiro(linha["valor"]),
        "data": linha["data"].isoformat(),
        "status": linha["status"],
        "efetivar_automaticamente": linha["efetivar_automaticamente"],
        "categoria": {
            "id": str(linha["categoria_id"]),
            "nome": linha["categoria_nome"],
            "cor": linha["categoria_cor"],
            "icone": linha["categoria_icone"],
            "especial": linha["categoria_especial"],
            "vinculo": linha["categoria_vinculo"],
        },
        "subcategoria": (
            {
                "id": str(linha["subcategoria_id"]),
                "nome": linha["subcategoria_nome"],
                "cor": linha["subcategoria_cor"],
                "cliente_id": (
                    str(linha["subcategoria_cliente_id"])
                    if linha["subcategoria_cliente_id"]
                    else None
                ),
            }
            if linha["subcategoria_id"]
            else None
        ),
        "servico": (
            {
                "id": str(linha["servico_id"]),
                "nome": linha["servico_nome"],
                "mundo": linha["servico_mundo"],
            }
            if linha["servico_id"]
            else None
        ),
        "centro_custo": (
            {
                "id": str(linha["centro_custo_id"]),
                "nome": linha["centro_custo_nome"],
                "mundo": linha["centro_custo_mundo"],
            }
            if linha["centro_custo_id"]
            else None
        ),
        "tags": tags or [],
        "moeda_origem": linha["moeda_origem"],
        "valor_origem": _dinheiro(linha["valor_origem"]),
        "cotacao": None if linha["cotacao"] is None else f"{linha['cotacao']:.6f}",
        "cotacao_manual": linha["cotacao_manual"],
        "observacoes": linha["observacoes"],
        "origem": _origem(linha),
        "tem_anexos": linha["quantidade_anexos"] > 0,
        "quantidade_anexos": linha["quantidade_anexos"],
        "tem_partes": linha["tem_partes"],
        "versao": linha["versao"],
    }


def acoes_disponiveis(linha: dict[str, Any]) -> list[str]:
    """`FR-042`: quem decide se aparece "confirmar recebimento" é o servidor.

    Deixar o frontend calcular isso a partir do status espalharia regra de negócio pela
    tela, que é o que o Princípio III proíbe.
    """
    acoes = ["duplicar"]
    status = linha["status"]

    if status != "cancelado":
        acoes.insert(0, "editar")
        acoes.append("excluir")
    if status in ("pendente", "atrasado", "programado"):
        acoes.append("confirmar_efetivacao")
    if status != "cancelado":
        acoes.append("cancelar")
    if not linha["tem_partes"] and not linha["lancamento_pai_id"] and status != "cancelado":
        acoes.append("dividir")

    return acoes
