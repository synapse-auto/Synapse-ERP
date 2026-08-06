"""Clientes — contracts/cadastros.md §3. `FR-080`–`FR-084`.

Papéis: leitura para gestor e operador; escrita só para gestor (cadastro estrutural).

## As três coisas que acontecem juntas ao cadastrar

Numa transação só (D-07, `FR-082`):

1. a linha em `clientes`;
2. a **subcategoria espelho em cada categoria com `vinculo = cliente`** — a de receita
   ("Clientes") e a de custo ("Custos Operacionais", `RF-58`);
3. quando `tipo_cobranca = recorrente`, a **recorrência da mensalidade** no
   `mundo_cobranca`, já materializada.

Se qualquer uma falhar, nenhuma vale. Um cliente sem subcategoria não teria onde receber
lançamento; uma subcategoria sem recorrência faria a mensalidade nunca aparecer.

## A quarta coisa, quando o cliente já era cliente antes do sistema

`cliente_desde: "2025-03"` acrescenta uma quarta operação **à mesma transação**: as
ocorrências passadas da mensalidade, do mês informado até o mês atual, nascendo
`efetivado` (`RN-05a`) e portanto entrando no saldo na hora (`RN-05`).

Não há caminho de gravação novo. A recorrência já sabe gerar do passado — a única coisa
que mudou é `data_inicio` deixar de ser fixo em `date.today()`. Consequências que vêm
de graça: o *clamp* do dia 31 em fevereiro é o mesmo, o lote inteiro vai numa ida ao
banco (`insert … select from unnest`), e o índice único `(recorrencia_id, data)` faz a
repetição não duplicar nada. A regra de qual mês é aceitável mora em
`dominio/cliente_retroativo.py`.

## O detalhe que decide se a inadimplência funciona

`efetivar_automaticamente` da recorrência vem, por padrão, de
`configuracoes.efetivacao_automatica_padrao_receita_cliente` — que é `false` de propósito
(D-05). Com ele `true`, a mensalidade se efetiva sozinha na data e o cliente **nunca**
aparece como inadimplente, por mais que não pague. A resposta devolve o valor efetivo e a
consequência em texto, para a tela poder explicar.

Tarefas: T106, T107, T108
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.clientes import repositorio
from app.comum import periodo as mod_periodo
from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada, ErroValidacao
from app.comum.idempotencia import (
    chave_de_idempotencia,
    registra_resposta,
    resposta_ja_registrada,
)
from app.comum.paginacao import Paginacao, envelope, parametros_de_paginacao
from app.db import obter_conexao
from app.dominio import arquivamento as mod_arquivamento
from app.dominio import cliente_retroativo as mod_retroativo
from app.dominio import espelho_subcategoria as mod_espelho
from app.dominio import inadimplencia as mod_inadimplencia
from app.dominio import mundo as mod_mundo
from app.dominio import recorrencia as mod_recorrencia
from app.lancamentos.servico import le_configuracao
from app.recorrencias import repositorio as repositorio_recorrencias
from app.recorrencias import servico as servico_recorrencias
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/clientes", tags=["Cadastros"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Gestor = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

VINCULO = "cliente"


class ClienteEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    empresa: str | None = None
    contato_email: str | None = None
    contato_telefone: str | None = None

    # `Literal`, não `str`: com `str` o valor ia inteiro até o `cast(... as tipo_cobranca)`
    # e o Postgres respondia `invalid input value for enum` — que sai como `500 erro_interno`
    # em vez do `400 validacao` que contracts/README.md manda. Erro de entrada tem que ser
    # recusado na borda, com o nome do campo e os valores aceitos.
    tipo_cobranca: Literal["pontual", "recorrente", "parcelada"] = Field(
        description="pontual | recorrente | parcelada."
    )
    valor_recorrente: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    dia_cobranca: int | None = Field(default=None, ge=1, le=31)
    mundo_cobranca: str | None = Field(
        default=None,
        description=(
            "**Não é o mundo do cliente** — cliente não tem mundo (D-04). É o mundo em "
            "que as ocorrências da mensalidade nascem, porque o lançamento precisa de um."
        ),
    )

    cliente_desde: str | None = Field(
        default=None,
        description=(
            "`AAAA-MM` — mês em que o cliente fechou conosco, quando isso foi **antes** "
            "do sistema. Gera as ocorrências passadas da mensalidade já `efetivado` "
            "(`RN-05a`), do mês informado até o mês atual. Mês corrente equivale a não "
            "informar. Só vale com `tipo_cobranca = recorrente`, e só no `POST`."
        ),
        examples=["2025-03"],
    )

    servico_ids: list[UUID] = Field(default_factory=list)
    observacoes: str | None = None
    efetivar_automaticamente: bool | None = Field(
        default=None,
        description=(
            "Nulo usa `configuracoes.efetivacao_automatica_padrao_receita_cliente` "
            "(`false`). Com `true`, a mensalidade se efetiva sozinha e o cliente **nunca** "
            "aparece como inadimplente (D-05)."
        ),
    )

    @model_validator(mode="after")
    def _recorrente_exige_os_tres(self) -> "ClienteEntrada":
        if self.tipo_cobranca != "recorrente":
            return self
        faltando = [
            nome
            for nome, valor in (
                ("valor_recorrente", self.valor_recorrente),
                ("dia_cobranca", self.dia_cobranca),
                ("mundo_cobranca", self.mundo_cobranca),
            )
            if valor is None
        ]
        if faltando:
            raise ValueError(
                "Cobrança recorrente precisa de valor, dia de cobrança e mundo de "
                f"cobrança. Faltou: {', '.join(faltando)}."
            )
        return self


class ArquivarEntrada(BaseModel):
    confirmar_remocao_de_futuros: bool = Field(
        default=False,
        description=(
            "Exigido quando há ocorrências futuras programadas. A primeira chamada "
            "responde `422` dizendo quantas seriam removidas."
        ),
    )


def _dinheiro(valor: Any) -> str | None:
    return None if valor is None else f"{Decimal(str(valor)):.2f}"


async def _tolerancia(conexao: AsyncConnection) -> int:
    return int(
        await le_configuracao(
            conexao,
            "inadimplencia_dias_tolerancia",
            padrao=mod_inadimplencia.PADRAO_DIAS_TOLERANCIA,
        )
    )


def _situacao_de(linha: dict[str, Any], *, tolerancia: int, hoje: date):
    em_aberto = [
        {
            "data": (
                date.fromisoformat(item["data"]) if isinstance(item["data"], str) else item["data"]
            ),
            "valor": item["valor"],
            "status": item["status"],
            "efetivar_automaticamente": item["efetivar_automaticamente"],
        }
        for item in (linha.get("em_aberto") or [])
    ]
    return mod_inadimplencia.avalia(em_aberto, tolerancia_dias=tolerancia, hoje=hoje)


def _para_json(linha: dict[str, Any], situacao, *, servicos=None) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "nome": linha["nome"],
        "empresa": linha["empresa"],
        "contato_email": linha["contato_email"],
        "contato_telefone": linha["contato_telefone"],
        "tipo_cobranca": linha["tipo_cobranca"],
        "valor_recorrente": _dinheiro(linha["valor_recorrente"]),
        "dia_cobranca": linha["dia_cobranca"],
        "mundo_cobranca": linha["mundo_cobranca"],
        "observacoes": linha["observacoes"],
        "arquivado_em": linha["arquivado_em"].isoformat() if linha["arquivado_em"] else None,
        # Derivado, nunca gravado (data-model §3.4): a receita efetivada mais antiga,
        # limitada por baixo pela data de cadastro. É o que faz "Cliente desde 03/2025"
        # aparecer sozinho depois de o histórico ser carregado.
        "cliente_desde": (
            linha["cliente_desde"].isoformat() if linha.get("cliente_desde") else None
        ),
        "servicos": [
            {"id": str(s["id"]), "nome": s["nome"], "mundo": s["mundo"]} for s in (servicos or [])
        ],
        "total_recebido_historico": _dinheiro(linha.get("total_recebido_historico") or 0),
        "total_recebido_periodo": _dinheiro(linha.get("total_recebido_periodo") or 0),
        # `RF-58` — o outro lado do cliente: o que ele custa. Vem da mesma varredura
        # dos totais de receita, e `margem_*` é subtração, não consulta.
        "total_custo_historico": _dinheiro(linha.get("total_custo_historico") or 0),
        "total_custo_periodo": _dinheiro(linha.get("total_custo_periodo") or 0),
        "margem_historico": _dinheiro(
            Decimal(str(linha.get("total_recebido_historico") or 0))
            - Decimal(str(linha.get("total_custo_historico") or 0))
        ),
        "margem_periodo": _dinheiro(
            Decimal(str(linha.get("total_recebido_periodo") or 0))
            - Decimal(str(linha.get("total_custo_periodo") or 0))
        ),
        # D-04: cliente sem lançamento não pertence a mundo nenhum e aparece nos três
        # estados do seletor. A marca existe para a tela explicar, não para escondê-lo.
        "sem_movimentacao": bool(linha.get("sem_movimentacao", False)),
        **situacao.como_dicionario(),
    }


# Janela do gráfico de receita mês a mês do perfil.
MESES_DA_SERIE_MINIMO = 12
MESES_DA_SERIE_MAXIMO = 36


def _meses_da_serie(cliente_desde: date | None, *, hoje: date) -> int:
    """Quantos meses o gráfico do perfil cobre.

    Era fixo em 12, e com histórico retroativo carregado isso passou a **esconder** o
    que a função inteira existe para mostrar: um cliente de 18 meses tinha os 6
    primeiros cortados do gráfico, sem nada na tela dizendo que faltava algo.

    A janela agora acompanha o tempo de casa, com piso de 12 (para o cliente novo não
    ganhar um gráfico de duas colunas) e teto de 36 (acima disso a série vira um borrão
    de barras de 4px — quem quer 5 anos usa Relatórios). Não custa consulta extra: o
    `generate_series` já recebia o número.
    """
    if cliente_desde is None:
        return MESES_DA_SERIE_MINIMO
    meses = mod_retroativo.meses_entre(cliente_desde, hoje) + 1
    return max(MESES_DA_SERIE_MINIMO, min(MESES_DA_SERIE_MAXIMO, meses))


async def _exige_cliente(conexao: AsyncConnection, cliente_id: UUID) -> dict[str, Any]:
    linha = await repositorio.por_id(conexao, cliente_id)
    if linha is None:
        raise ErroNaoEncontrado("Cliente não encontrado.")
    return linha


# ── T106 · GET /api/clientes ────────────────────────────────────────────────


@roteador.get(
    "",
    summary="Lista de clientes, com situação derivada e inadimplentes no topo",
    description=(
        "Papel: gestor, operador. `FR-080`, `FR-083`. **Cliente não tem mundo** (D-04): "
        "`?mundo=` filtra pela **movimentação** — clientes com lançamento naquele mundo. "
        "Cliente sem nenhum lançamento aparece nos três estados, marcado com "
        "`sem_movimentacao: true`. `situacao` é derivada de `RN-10`, nunca gravada."
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
    situacao: Annotated[str | None, Query(description="em_dia | atrasado.")] = None,
    busca: Annotated[str | None, Query()] = None,
    incluir_arquivados: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    hoje = date.today()
    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)
    tolerancia = await _tolerancia(conexao)

    condicoes, parametros = repositorio.monta_filtros(
        mundos=mundos,
        # No modo "Ambos" não há o que derivar: os dois mundos entram, e o filtro por
        # movimentação só faria trabalho extra para devolver todo mundo.
        filtrando_por_mundo=not mod_mundo.deve_quebrar_por_mundo(mundo),
        incluir_arquivados=incluir_arquivados,
        busca=busca,
    )
    linhas = await repositorio.lista(
        conexao,
        condicoes=condicoes,
        parametros=parametros,
        inicio=janela.inicio,
        fim=janela.fim,
        limite=paginacao.por_pagina,
        deslocamento=paginacao.deslocamento,
    )
    total = await repositorio.conta(conexao, condicoes=condicoes, parametros=parametros)

    itens = [
        _para_json(linha, _situacao_de(linha, tolerancia=tolerancia, hoje=hoje)) for linha in linhas
    ]
    if situacao:
        if situacao not in ("em_dia", "atrasado"):
            raise ErroValidacao(
                f"Situação '{situacao}' não existe.",
                requisito="RN-10",
                campos={"situacao": "Aceitos: em_dia, atrasado."},
            )
        itens = [item for item in itens if item["situacao"] == situacao]

    # `FR-083`: inadimplente no topo. A ordenação é feita aqui e não no SQL porque a
    # situação é derivada em Python — é o preço de `RN-10` não ser coluna, e é um preço
    # que só se paga na página, não na base inteira.
    itens.sort(key=lambda item: (item["situacao"] != "atrasado", item["nome"].lower()))

    resposta = envelope(itens, total=total, paginacao=paginacao)
    resposta["periodo"] = janela.como_dicionario()
    resposta["tolerancia_dias"] = tolerancia
    return resposta


# ── T106 · POST /api/clientes ───────────────────────────────────────────────


async def _cria_recorrencia_da_mensalidade(
    conexao: AsyncConnection,
    *,
    cliente_id: UUID,
    subcategoria_id: UUID,
    corpo: ClienteEntrada,
    usuario: UsuarioAutenticado,
    inicio_retroativo: date | None = None,
) -> dict[str, Any] | None:
    """`FR-082` — a mensalidade vira recorrência no `mundo_cobranca`.

    `inicio_retroativo` é o único parâmetro do histórico: com ele, `data_inicio` nasce
    no passado e a materialização gera de lá até o horizonte, numa ida ao banco só. Sem
    ele, `date.today()` — o comportamento de sempre.
    """
    if corpo.tipo_cobranca != "recorrente":
        return None

    # `tipo="receita"` porque a mensalidade é receita: desde `RF-58` o vínculo `cliente`
    # tem duas categorias, e a de despesa é a dos custos operacionais.
    categoria = await mod_espelho.categoria_do_vinculo(conexao, VINCULO, tipo="receita")
    automatico = corpo.efetivar_automaticamente
    if automatico is None:
        automatico = bool(
            await le_configuracao(
                conexao, "efetivacao_automatica_padrao_receita_cliente", padrao=False
            )
        )

    nova = await repositorio_recorrencias.insere(
        conexao,
        campos={
            "tipo": "receita",
            "descricao": f"Mensalidade — {corpo.nome}",
            "valor": corpo.valor_recorrente,
            "categoria_id": str(categoria["id"]),
            "subcategoria_id": str(subcategoria_id),
            "servico_id": str(corpo.servico_ids[0]) if corpo.servico_ids else None,
            "centro_custo_id": None,
            "frequencia": "mensal",
            "intervalo_dias": None,
            "dia_vencimento": corpo.dia_cobranca,
            "mes_vencimento": None,
            "data_inicio": inicio_retroativo or date.today(),
            "data_fim": None,
            "total_parcelas": None,
            "efetivar_automaticamente": automatico,
            "cliente_id": str(cliente_id),
            "funcionario_id": None,
        },
        mundo=corpo.mundo_cobranca,
        usuario_id=usuario.id,
    )

    linha = await servico_recorrencias.exige_recorrencia(conexao, nova["id"])
    ate = await servico_recorrencias.horizonte_configurado(conexao)
    geracao = await servico_recorrencias.materializa(conexao, linha, usuario_id=usuario.id, ate=ate)

    retroativo = None
    if inicio_retroativo is not None:
        # Recontagem em Python, não no banco: `monta_previa` percorre as mesmas datas
        # que acabaram de ser geradas, sem custar consulta nenhuma.
        previa = mod_recorrencia.monta_previa(servico_recorrencias.regra_de(linha), ate=ate)
        retroativo = mod_retroativo.resumo(
            desde=inicio_retroativo,
            ocorrencias=previa.retroativas_efetivadas,
            valor_unitario=_dinheiro(
                (corpo.valor_recorrente or Decimal(0)) * previa.retroativas_efetivadas
            ),
        )

    return {
        "id": str(nova["id"]),
        "rotulo": servico_recorrencias.rotulo_da_regra(linha),
        "ativa": True,
        "efetivar_automaticamente": automatico,
        "geracao": geracao.como_dicionario(),
        "retroativo": retroativo,
        # Texto de negócio, montado no servidor: a tela precisa explicar por que um
        # cliente com mensalidade automática nunca vai aparecer como inadimplente.
        "aviso_inadimplencia": (
            "Como a efetivação é automática, esta mensalidade se confirma sozinha na data "
            "e o cliente nunca vai aparecer como inadimplente."
            if automatico
            else "A efetivação é manual, então o atraso desta mensalidade gera alerta de "
            "inadimplência."
        ),
    }


@roteador.post(
    "",
    status_code=201,
    summary="Cadastra o cliente, a subcategoria espelho e a mensalidade",
    description=(
        "Papel: **gestor**. As três coisas na mesma transação (D-07, `FR-082`). "
        "`tipo_cobranca: recorrente` exige `valor_recorrente`, `dia_cobranca` e "
        "`mundo_cobranca`. `efetivar_automaticamente` nulo herda "
        "`configuracoes.efetivacao_automatica_padrao_receita_cliente` — a resposta "
        "devolve o valor efetivo e a consequência para o alerta de inadimplência (D-05). "
        '`cliente_desde: "AAAA-MM"` acrescenta uma **quarta** operação à transação: as '
        "ocorrências passadas da mensalidade, já `efetivado` (`RN-05a`), do mês "
        "informado até o mês atual. Aceita `Idempotency-Key`."
    ),
)
async def criar(
    corpo: ClienteEntrada,
    usuario: Gestor,
    conexao: Conexao,
    chave: Annotated[str | None, Depends(chave_de_idempotencia)] = None,
) -> dict[str, Any]:
    # Idempotência de verdade é aqui, não só no `on conflict` da ocorrência: sem isto,
    # a repetição que a Vercel faz depois de um timeout criaria um **segundo cliente**
    # com o histórico inteiro de novo, e o saldo contaria o passado duas vezes.
    guardada = await resposta_ja_registrada(
        conexao, chave, rota="POST /api/clientes", usuario_id=str(usuario.id)
    )
    if guardada is not None:
        return guardada

    if corpo.mundo_cobranca is not None and corpo.mundo_cobranca not in mod_mundo.MUNDOS:
        raise ErroValidacao(
            f"Mundo de cobrança '{corpo.mundo_cobranca}' não existe.",
            requisito="RN-15",
            campos={"mundo_cobranca": f"Aceitos: {', '.join(mod_mundo.MUNDOS)}."},
        )

    # O limite vem de `configuracoes` (`RNF-02`), então a validação é aqui e não no
    # `model_validator` — o Pydantic não tem conexão com o banco.
    inicio_retroativo = mod_retroativo.resolve_inicio(
        corpo.cliente_desde,
        tipo_cobranca=corpo.tipo_cobranca,
        meses_maximo=int(
            await le_configuracao(
                conexao,
                "cliente_retroativo_meses_maximo",
                padrao=mod_retroativo.PADRAO_MESES_MAXIMO,
            )
        ),
    )

    novo = (
        await conexao.execute(
            text("""
                insert into clientes (
                  nome, empresa, contato_email, contato_telefone,
                  tipo_cobranca, valor_recorrente, dia_cobranca, mundo_cobranca, observacoes
                ) values (
                  :nome, :empresa, :email, :telefone,
                  cast(:tipo as tipo_cobranca), :valor, :dia, cast(:mundo as mundo), :obs
                )
                returning id
                """),
            {
                "nome": corpo.nome,
                "empresa": corpo.empresa,
                "email": corpo.contato_email,
                "telefone": corpo.contato_telefone,
                "tipo": corpo.tipo_cobranca,
                "valor": corpo.valor_recorrente,
                "dia": corpo.dia_cobranca,
                "mundo": corpo.mundo_cobranca,
                "obs": corpo.observacoes,
            },
        )
    ).scalar_one()

    # Nasce um espelho por categoria do vínculo — em "Clientes" (receita) e em "Custos
    # Operacionais" (despesa), `RF-58`. `espelho["id"]` é o do lado da receita, que é o
    # que a mensalidade usa.
    espelho = await mod_espelho.cria(
        conexao, vinculo=VINCULO, dono_id=novo, nome=corpo.nome, tipo_principal="receita"
    )
    await repositorio.define_servicos(conexao, novo, corpo.servico_ids)
    recorrencia = await _cria_recorrencia_da_mensalidade(
        conexao,
        cliente_id=novo,
        subcategoria_id=espelho["id"],
        corpo=corpo,
        usuario=usuario,
        inicio_retroativo=inicio_retroativo,
    )

    await registra_auditoria(
        conexao,
        entidade="clientes",
        entidade_id=novo,
        acao="criacao",
        usuario_id=usuario.id,
        depois={
            "nome": corpo.nome,
            "tipo_cobranca": corpo.tipo_cobranca,
            # Fica na auditoria porque muda o saldo retroativamente: quem olhar o caixa
            # de um mês fechado e vir um número diferente precisa achar a explicação.
            "cliente_desde": corpo.cliente_desde if inicio_retroativo else None,
        },
    )

    linha = await _exige_cliente(conexao, novo)
    resposta = _para_json(
        linha,
        mod_inadimplencia.avalia([], tolerancia_dias=await _tolerancia(conexao)),
        servicos=await repositorio.servicos_do_cliente(conexao, novo),
    )
    resposta["subcategoria_id"] = str(espelho["id"])
    resposta["recorrencia"] = recorrencia

    await registra_resposta(
        conexao, chave, rota="POST /api/clientes", usuario_id=str(usuario.id), resposta=resposta
    )
    return resposta


# ── T107 · GET /api/clientes/{id} — perfil ──────────────────────────────────


@roteador.get(
    "/{cliente_id}",
    summary="Perfil do cliente",
    description=(
        "Papel: gestor, operador. `FR-081`. Total recebido, receita mensal, próximos "
        "recebimentos, situação e **quebra por mundo** — que existe justamente porque o "
        "cliente não tem mundo, mas a receita dele tem (D-04). Desde `RF-58` traz "
        "também o **custo operacional** do cliente (`custos`, `quebra_custo_por_mundo` e "
        "`custo`/`margem` mês a mês na série)."
    ),
)
async def detalhar(
    cliente_id: UUID,
    usuario: Autenticado,
    conexao: Conexao,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    hoje = date.today()
    linha = await _exige_cliente(conexao, cliente_id)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)
    tolerancia = await _tolerancia(conexao)

    abertos = await repositorio.em_aberto(conexao, cliente_id)
    situacao = mod_inadimplencia.avalia(abertos, tolerancia_dias=tolerancia, hoje=hoje)
    quebra = await repositorio.quebra_por_mundo(conexao, cliente_id)

    historico = sum(Decimal(str(v)) for v in quebra["receita"].values())
    custo_historico = sum(Decimal(str(v)) for v in quebra["custo"].values())

    # Receita e custo do período na mesma ida ao banco — o `filter` separa os dois lados
    # sem uma segunda consulta (`RF-58`, `backend/README.md` §custo).
    do_periodo = (
        (
            await conexao.execute(
                text("""
                    select
                      coalesce(sum(l.valor) filter (where l.tipo = 'receita'), 0) as receita,
                      coalesce(sum(l.valor) filter (where l.tipo = 'despesa'), 0) as custo
                    from lancamentos_ativos l
                    join subcategorias s on s.id = l.subcategoria_id
                    where s.cliente_id = :cliente
                      and l.status = 'efetivado' and l.data between :inicio and :fim
                    """),
                {"cliente": str(cliente_id), "inicio": janela.inicio, "fim": janela.fim},
            )
        )
        .mappings()
        .one()
    )
    receita_periodo = Decimal(str(do_periodo["receita"]))
    custo_periodo = Decimal(str(do_periodo["custo"]))

    recorrencia = await repositorio.recorrencia_do_cliente(conexao, cliente_id)
    proximos = await repositorio.proximos_recebimentos(conexao, cliente_id, hoje=hoje)
    movimento, movimento_total = await repositorio.lancamentos_do_cliente(
        conexao, cliente_id, inicio=janela.inicio, fim=janela.fim
    )

    perfil = _para_json(
        linha
        | {
            "total_recebido_historico": historico,
            "total_recebido_periodo": receita_periodo,
            "total_custo_historico": custo_historico,
            "total_custo_periodo": custo_periodo,
        },
        situacao,
        servicos=await repositorio.servicos_do_cliente(conexao, cliente_id),
    )
    perfil |= {
        "periodo": janela.como_dicionario(),
        "quebra_por_mundo": {k: f"{Decimal(str(v)):.2f}" for k, v in quebra["receita"].items()},
        "quebra_custo_por_mundo": {k: f"{Decimal(str(v)):.2f}" for k, v in quebra["custo"].items()},
        # `RF-58`. `margem_percentual` é `null`, não `"0.0"`, quando não houve receita
        # no período: custo sem faturamento não é margem zero — é margem que não dá para
        # calcular, e a tela mostra as duas coisas de forma diferente.
        "custos": {
            "total_historico": f"{custo_historico:.2f}",
            "total_periodo": f"{custo_periodo:.2f}",
            "margem_historico": f"{historico - custo_historico:.2f}",
            "margem_periodo": f"{receita_periodo - custo_periodo:.2f}",
            "margem_percentual_periodo": (
                f"{(receita_periodo - custo_periodo) / receita_periodo * 100:.1f}"
                if receita_periodo
                else None
            ),
        },
        # A série traz os três números do mesmo mês. `valor` continua sendo a receita —
        # o nome do campo é o que contracts/cadastros.md §3 já prometia, e mudá-lo
        # quebraria o gráfico por nada.
        "receita_mensal": [
            {
                "mes": item["mes"],
                "valor": f"{Decimal(str(item['valor'])):.2f}",
                "custo": f"{Decimal(str(item['custo'])):.2f}",
                "margem": f"{Decimal(str(item['valor'])) - Decimal(str(item['custo'])):.2f}",
            }
            for item in await repositorio.receita_mensal(
                conexao, cliente_id, meses=_meses_da_serie(linha.get("cliente_desde"), hoje=hoje)
            )
        ],
        "proximos_recebimentos": [
            {
                "lancamento_id": str(item["lancamento_id"]),
                "data": item["data"].isoformat(),
                "valor": f"{Decimal(str(item['valor'])):.2f}",
                "status": item["status"],
                "mundo": item["mundo"],
            }
            for item in proximos
        ],
        # Envelope paginado, e não lista solta: é o que contracts/cadastros.md §3
        # promete aqui (`"lancamentos": { "itens": [], "paginacao": {} }`) e o que a
        # tela lê em `c.lancamentos.itens`. O campo simplesmente não existia na
        # resposta, e o perfil do cliente quebrava com
        # `Cannot read properties of undefined (reading 'length')`.
        "lancamentos": envelope(
            [
                {
                    "id": str(item["id"]),
                    "data": item["data"].isoformat(),
                    "descricao": item["descricao"],
                    "valor": f"{Decimal(str(item['valor'])):.2f}",
                    "tipo": item["tipo"],
                    "status": item["status"],
                    "mundo": item["mundo"],
                }
                for item in movimento
            ],
            total=movimento_total,
            paginacao=Paginacao(pagina=1, por_pagina=50, ordenar=None, direcao="desc"),
        ),
        "recorrencia": (
            {
                "id": str(recorrencia["id"]),
                "mundo": recorrencia["mundo"],
                "valor": f"{Decimal(str(recorrencia['valor'])):.2f}",
                "rotulo": servico_recorrencias.rotulo_da_regra(recorrencia),
                "ativa": recorrencia["ativa"],
                "efetivar_automaticamente": recorrencia["efetivar_automaticamente"],
                "pode_gerar_inadimplencia": mod_inadimplencia.pode_ficar_inadimplente(
                    efetivar_automaticamente=recorrencia["efetivar_automaticamente"]
                ),
            }
            if recorrencia
            else None
        ),
    }
    return perfil


# ── T106 · PUT /api/clientes/{id} ───────────────────────────────────────────


@roteador.put(
    "/{cliente_id}",
    summary="Edita o cliente e mantém o espelho em dia",
    description=(
        "Papel: **gestor**. Renomear renomeia a subcategoria espelho na mesma transação "
        "(D-07) — sem isso o Dashboard continuaria mostrando o nome antigo. "
        "**Não aceita `cliente_desde`**: carregar histórico é operação de cadastro."
    ),
)
async def editar(
    cliente_id: UUID, corpo: ClienteEntrada, usuario: Gestor, conexao: Conexao
) -> dict[str, Any]:
    atual = await _exige_cliente(conexao, cliente_id)

    # Recusado em vez de ignorado em silêncio. A edição não mexe na recorrência, então
    # aceitar o campo aqui prometeria um histórico que nunca seria gerado — e o usuário
    # só descobriria conferindo o saldo. Para corrigir o passado de um cliente que já
    # existe, o caminho é a recorrência dele (`PUT /api/recorrencias/{id}`).
    if corpo.cliente_desde is not None:
        raise ErroValidacao(
            "O histórico retroativo só é carregado no cadastro do cliente.",
            requisito="RN-05a",
            campos={
                "cliente_desde": (
                    "Para mudar o passado de um cliente já cadastrado, edite a "
                    "recorrência da mensalidade."
                )
            },
        )

    await conexao.execute(
        text("""
            update clientes set
              nome = :nome, empresa = :empresa, contato_email = :email,
              contato_telefone = :telefone, tipo_cobranca = cast(:tipo as tipo_cobranca),
              valor_recorrente = :valor, dia_cobranca = :dia,
              mundo_cobranca = cast(:mundo as mundo), observacoes = :obs
            where id = :id
            """),
        {
            "id": str(cliente_id),
            "nome": corpo.nome,
            "empresa": corpo.empresa,
            "email": corpo.contato_email,
            "telefone": corpo.contato_telefone,
            "tipo": corpo.tipo_cobranca,
            "valor": corpo.valor_recorrente,
            "dia": corpo.dia_cobranca,
            "mundo": corpo.mundo_cobranca,
            "obs": corpo.observacoes,
        },
    )
    await mod_espelho.renomeia(conexao, vinculo=VINCULO, dono_id=cliente_id, nome=corpo.nome)
    await repositorio.define_servicos(conexao, cliente_id, corpo.servico_ids)

    await registra_auditoria(
        conexao,
        entidade="clientes",
        entidade_id=cliente_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes={k: atual[k] for k in ("nome", "empresa", "tipo_cobranca", "valor_recorrente")},
        depois={
            "nome": corpo.nome,
            "empresa": corpo.empresa,
            "tipo_cobranca": corpo.tipo_cobranca,
            "valor_recorrente": corpo.valor_recorrente,
        },
    )

    return await detalhar(cliente_id, usuario, conexao)


# ── T108 · arquivar e desarquivar ───────────────────────────────────────────


@roteador.post(
    "/{cliente_id}/arquivar",
    summary="Arquiva o cliente e desliga a cobrança",
    description=(
        "Papel: **gestor**. `RN-06`, `FR-084`. Arquiva o cliente **e** a subcategoria "
        "espelho, desativa a recorrência e remove as ocorrências futuras não efetivadas. "
        "Lançamentos passados ficam intactos. A resposta diz quantas ocorrências futuras "
        "saíram — sem esse número o usuário não saberia que a projeção mudou. "
        "**Cliente nunca é excluído** (constituição)."
    ),
)
async def arquivar(
    cliente_id: UUID, corpo: ArquivarEntrada, usuario: Gestor, conexao: Conexao
) -> dict[str, Any]:
    linha = await _exige_cliente(conexao, cliente_id)
    if linha["arquivado_em"] is not None:
        raise ErroRegraViolada(
            f"O cliente '{linha['nome']}' já está arquivado.",
            requisito="RN-06",
            campos={"arquivado_em": "Já arquivado."},
        )

    recorrencia = await repositorio.recorrencia_do_cliente(conexao, cliente_id)
    removidas = 0
    if recorrencia:
        removidas = await repositorio_recorrencias.remove_futuras_nao_efetivadas(
            conexao, recorrencia["id"], a_partir_de=date.today(), usuario_id=usuario.id
        )
        await repositorio_recorrencias.desativa(conexao, recorrencia["id"])

    await conexao.execute(
        text("update clientes set arquivado_em = now() where id = :id"), {"id": str(cliente_id)}
    )
    await mod_espelho.arquiva(conexao, vinculo=VINCULO, dono_id=cliente_id)

    await registra_auditoria(
        conexao,
        entidade="clientes",
        entidade_id=cliente_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={
            "arquivado_em": {"de": None, "para": "agora"},
            "ocorrencias_futuras_removidas": {"de": None, "para": removidas},
        },
    )

    atualizado = await _exige_cliente(conexao, cliente_id)
    return _para_json(
        atualizado, mod_inadimplencia.avalia([], tolerancia_dias=await _tolerancia(conexao))
    ) | mod_arquivamento.resumo_do_arquivamento(ocorrencias_removidas=removidas)


@roteador.post(
    "/{cliente_id}/desarquivar",
    summary="Traz o cliente de volta",
    description=(
        "Papel: **gestor**. Desarquiva o cliente e a subcategoria. A recorrência **não** "
        "volta sozinha: as ocorrências futuras foram removidas ao arquivar, e recriá-las "
        "sem o usuário pedir traria de volta cobranças que ele desligou. Reative a "
        "mensalidade editando o cliente."
    ),
)
async def desarquivar(cliente_id: UUID, usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    linha = await _exige_cliente(conexao, cliente_id)
    if linha["arquivado_em"] is None:
        raise ErroRegraViolada(
            f"O cliente '{linha['nome']}' não está arquivado.",
            requisito="RN-06",
            campos={"arquivado_em": "Já ativo."},
        )

    await conexao.execute(
        text("update clientes set arquivado_em = null where id = :id"), {"id": str(cliente_id)}
    )
    await mod_espelho.desarquiva(conexao, vinculo=VINCULO, dono_id=cliente_id)
    await registra_auditoria(
        conexao,
        entidade="clientes",
        entidade_id=cliente_id,
        acao="restauracao",
        usuario_id=usuario.id,
        alteracoes={"arquivado_em": {"de": "arquivado", "para": None}},
    )
    return await detalhar(cliente_id, usuario, conexao)
