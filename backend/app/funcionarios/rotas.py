"""Funcionários — contracts/cadastros.md §4. `FR-085`–`FR-089`.

Mesma forma dos clientes, com **uma diferença de modelagem que muda tudo**: funcionário
tem `mundo` (`RN-15`), obrigatório e imutável. Cliente não tem (D-04).

Consequência prática: aqui não existe filtro derivado. `?mundo=digital` é um `where`
simples, e mudar o mundo de um funcionário é `409` — o custo dele pertence a um dos dois
braços do negócio, e mover isso reescreveria o histórico dos dois.

## Bônus e vale entram sozinhos

`FR-088`: um pagamento avulso é um lançamento normal na **mesma subcategoria** do
funcionário. Não há campo nem endpoint para isso — e é de propósito. O custo do
funcionário é "tudo que foi lançado naquela subcategoria", então bônus e vale somam sem
nenhum código extra, e o perfil não precisa saber que existem.

Tarefas: T109, T110
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import periodo as mod_periodo
from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada
from app.db import obter_conexao
from app.dominio import arquivamento as mod_arquivamento
from app.dominio import espelho_subcategoria as mod_espelho
from app.dominio import mundo as mod_mundo
from app.recorrencias import repositorio as repositorio_recorrencias
from app.recorrencias import servico as servico_recorrencias
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/funcionarios", tags=["Cadastros"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Gestor = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

VINCULO = "funcionario"


class FuncionarioEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    funcao: str = Field(min_length=1, max_length=160)
    tipo_contratacao: str = Field(description="pj | freelancer.")
    valor_mensal: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    dia_pagamento: int = Field(ge=1, le=31)
    mundo: str = Field(description="digital | infra. **Imutável** depois de criado (`RN-15`).")


def _dinheiro(valor: Any) -> str:
    return f"{Decimal(str(valor or 0)):.2f}"


def _para_json(linha: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "nome": linha["nome"],
        "funcao": linha["funcao"],
        "tipo_contratacao": linha["tipo_contratacao"],
        "valor_mensal": _dinheiro(linha["valor_mensal"]),
        "dia_pagamento": linha["dia_pagamento"],
        "mundo": linha["mundo"],
        "arquivado_em": linha["arquivado_em"].isoformat() if linha["arquivado_em"] else None,
        **extra,
    }


async def _exige(conexao: AsyncConnection, funcionario_id: UUID) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text("""
                    select id, nome, funcao, tipo_contratacao, valor_mensal,
                           dia_pagamento, mundo, arquivado_em
                    from funcionarios where id = :id
                    """),
                {"id": str(funcionario_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Funcionário não encontrado.")
    return dict(linha)


# ── T109 · GET /api/funcionarios ────────────────────────────────────────────


@roteador.get(
    "",
    summary="Lista de funcionários, com custo do período",
    description=(
        "Papel: gestor, operador. `FR-085`. Funcionário **tem** mundo (`RN-15`), então "
        "`?mundo=` é filtro direto — diferente de clientes, onde é derivado (D-04)."
    ),
)
async def listar(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    incluir_arquivados: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)

    linhas = (
        (
            await conexao.execute(
                text("""
                    select f.id, f.nome, f.funcao, f.tipo_contratacao, f.valor_mensal,
                           f.dia_pagamento, f.mundo, f.arquivado_em,
                           coalesce(c.periodo, 0) as custo_periodo,
                           coalesce(c.historico, 0) as custo_historico
                    from funcionarios f
                    left join lateral (
                      select
                        sum(l.valor) filter (where l.status = 'efetivado') as historico,
                        sum(l.valor) filter (
                          where l.status = 'efetivado' and l.data between :inicio and :fim
                        ) as periodo
                      from lancamentos_ativos l
                      join subcategorias s on s.id = l.subcategoria_id
                      where s.funcionario_id = f.id and l.tipo = 'despesa'
                    ) c on true
                    where f.mundo = any(cast(:mundos as mundo[]))
                      and (:incluir_arquivados or f.arquivado_em is null)
                    order by lower(f.nome)
                    """),
                {
                    "mundos": mundos,
                    "inicio": janela.inicio,
                    "fim": janela.fim,
                    "incluir_arquivados": incluir_arquivados,
                },
            )
        )
        .mappings()
        .all()
    )

    return {
        "itens": [
            _para_json(
                dict(linha),
                custo_periodo=_dinheiro(linha["custo_periodo"]),
                custo_historico=_dinheiro(linha["custo_historico"]),
            )
            for linha in linhas
        ],
        "periodo": janela.como_dicionario(),
    }


# ── T109 · POST /api/funcionarios ───────────────────────────────────────────


@roteador.post(
    "",
    status_code=201,
    summary="Cadastra o funcionário, a subcategoria espelho e a folha",
    description=(
        "Papel: **gestor**. `FR-088`. As três coisas na mesma transação (D-07): o "
        "funcionário, a subcategoria com o nome dele e a **recorrência mensal da folha** "
        "no mundo dele. `mundo` é obrigatório e imutável (`RN-15`)."
    ),
)
async def criar(corpo: FuncionarioEntrada, usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    mundo_validado = mod_mundo.exige("funcionarios", corpo.mundo)

    novo = (
        await conexao.execute(
            text("""
                insert into funcionarios (
                  nome, funcao, tipo_contratacao, valor_mensal, dia_pagamento, mundo
                ) values (
                  :nome, :funcao, cast(:tipo as tipo_contratacao), :valor, :dia,
                  cast(:mundo as mundo)
                )
                returning id
                """),
            {
                "nome": corpo.nome,
                "funcao": corpo.funcao,
                "tipo": corpo.tipo_contratacao,
                "valor": corpo.valor_mensal,
                "dia": corpo.dia_pagamento,
                "mundo": mundo_validado,
            },
        )
    ).scalar_one()

    espelho = await mod_espelho.cria(conexao, vinculo=VINCULO, dono_id=novo, nome=corpo.nome)
    categoria = await mod_espelho.categoria_do_vinculo(conexao, VINCULO)

    recorrencia = await repositorio_recorrencias.insere(
        conexao,
        campos={
            "tipo": "despesa",
            "descricao": f"Folha — {corpo.nome}",
            "valor": corpo.valor_mensal,
            "categoria_id": str(categoria["id"]),
            "subcategoria_id": str(espelho["id"]),
            "servico_id": None,
            "centro_custo_id": None,
            "frequencia": "mensal",
            "intervalo_dias": None,
            "dia_vencimento": corpo.dia_pagamento,
            "mes_vencimento": None,
            "data_inicio": date.today(),
            "data_fim": None,
            "total_parcelas": None,
            # A folha se efetiva sozinha na data: é despesa certa, e deixá-la pendente
            # encheria a caixa de confirmações mensais sem informação nenhuma.
            "efetivar_automaticamente": True,
            "cliente_id": None,
            "funcionario_id": str(novo),
        },
        mundo=mundo_validado,
        usuario_id=usuario.id,
    )

    linha_recorrencia = await servico_recorrencias.exige_recorrencia(conexao, recorrencia["id"])
    ate = await servico_recorrencias.horizonte_configurado(conexao)
    geracao = await servico_recorrencias.materializa(
        conexao, linha_recorrencia, usuario_id=usuario.id, ate=ate
    )

    await registra_auditoria(
        conexao,
        entidade="funcionarios",
        entidade_id=novo,
        acao="criacao",
        usuario_id=usuario.id,
        depois={"nome": corpo.nome, "mundo": mundo_validado, "valor_mensal": corpo.valor_mensal},
    )

    return _para_json(
        await _exige(conexao, novo),
        subcategoria_id=str(espelho["id"]),
        recorrencia={
            "id": str(recorrencia["id"]),
            "rotulo": servico_recorrencias.rotulo_da_regra(linha_recorrencia),
            "ativa": True,
            "geracao": geracao.como_dicionario(),
        },
    )


# ── T110 · GET /api/funcionarios/{id} — perfil ──────────────────────────────


@roteador.get(
    "/{funcionario_id}",
    summary="Perfil do funcionário",
    description=(
        "Papel: gestor, operador. `FR-087`. Custo histórico e do período, pagamentos e "
        "próximos. **Bônus e vales entram sozinhos**: são lançamentos avulsos na mesma "
        "subcategoria, então somam ao custo sem código extra (`FR-088`)."
    ),
)
async def detalhar(
    funcionario_id: UUID,
    usuario: Autenticado,
    conexao: Conexao,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    hoje = date.today()
    linha = await _exige(conexao, funcionario_id)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)

    totais = (
        (
            await conexao.execute(
                text("""
                    select
                      coalesce(sum(l.valor) filter (where l.status = 'efetivado'), 0) as historico,
                      coalesce(sum(l.valor) filter (
                        where l.status = 'efetivado' and l.data between :inicio and :fim
                      ), 0) as periodo
                    from lancamentos_ativos l
                    join subcategorias s on s.id = l.subcategoria_id
                    where s.funcionario_id = :func and l.tipo = 'despesa'
                    """),
                {"func": str(funcionario_id), "inicio": janela.inicio, "fim": janela.fim},
            )
        )
        .mappings()
        .one()
    )

    pagamentos = (
        (
            await conexao.execute(
                text("""
                    select l.id, l.data, l.valor, l.status, l.descricao,
                           l.recorrencia_id is not null as da_folha
                    from lancamentos_ativos l
                    join subcategorias s on s.id = l.subcategoria_id
                    where s.funcionario_id = :func and l.tipo = 'despesa'
                    order by l.data desc
                    limit 60
                    """),
                {"func": str(funcionario_id)},
            )
        )
        .mappings()
        .all()
    )

    proximos = [p for p in pagamentos if p["data"] >= hoje and p["status"] != "efetivado"]

    return _para_json(
        linha,
        periodo=janela.como_dicionario(),
        custo_historico=_dinheiro(totais["historico"]),
        custo_periodo=_dinheiro(totais["periodo"]),
        pagamentos=[
            {
                "lancamento_id": str(p["id"]),
                "data": p["data"].isoformat(),
                "valor": _dinheiro(p["valor"]),
                "status": p["status"],
                "descricao": p["descricao"],
                # `false` marca bônus e vale — o que não veio da folha.
                "da_folha": p["da_folha"],
            }
            for p in pagamentos
        ],
        proximos_pagamentos=[
            {
                "lancamento_id": str(p["id"]),
                "data": p["data"].isoformat(),
                "valor": _dinheiro(p["valor"]),
                "status": p["status"],
            }
            for p in sorted(proximos, key=lambda item: item["data"])
        ],
    )


# ── T109 · PUT e arquivar ───────────────────────────────────────────────────


@roteador.put(
    "/{funcionario_id}",
    summary="Edita o funcionário",
    description=(
        "Papel: **gestor**. `mundo` diferente → `409 regra_violada` / `RN-15`. Renomear "
        "renomeia a subcategoria espelho na mesma transação."
    ),
)
async def editar(
    funcionario_id: UUID, corpo: FuncionarioEntrada, usuario: Gestor, conexao: Conexao
) -> dict[str, Any]:
    atual = await _exige(conexao, funcionario_id)
    mod_mundo.recusa_alteracao(atual["mundo"], corpo.mundo)

    await conexao.execute(
        text("""
            update funcionarios set
              nome = :nome, funcao = :funcao,
              tipo_contratacao = cast(:tipo as tipo_contratacao),
              valor_mensal = :valor, dia_pagamento = :dia
            where id = :id
            """),
        {
            "id": str(funcionario_id),
            "nome": corpo.nome,
            "funcao": corpo.funcao,
            "tipo": corpo.tipo_contratacao,
            "valor": corpo.valor_mensal,
            "dia": corpo.dia_pagamento,
        },
    )
    await mod_espelho.renomeia(conexao, vinculo=VINCULO, dono_id=funcionario_id, nome=corpo.nome)
    await registra_auditoria(
        conexao,
        entidade="funcionarios",
        entidade_id=funcionario_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes={k: atual[k] for k in ("nome", "funcao", "valor_mensal", "dia_pagamento")},
        depois={
            "nome": corpo.nome,
            "funcao": corpo.funcao,
            "valor_mensal": corpo.valor_mensal,
            "dia_pagamento": corpo.dia_pagamento,
        },
    )
    return await detalhar(funcionario_id, usuario, conexao)


@roteador.post(
    "/{funcionario_id}/arquivar",
    summary="Arquiva o funcionário e para a folha",
    description=(
        "Papel: **gestor**. `RN-06`. Arquiva o funcionário e a subcategoria, desativa a "
        "recorrência da folha e remove as ocorrências futuras não efetivadas. Pagamentos "
        "passados ficam. **Funcionário nunca é excluído** (constituição)."
    ),
)
async def arquivar(funcionario_id: UUID, usuario: Gestor, conexao: Conexao) -> dict[str, Any]:
    linha = await _exige(conexao, funcionario_id)
    if linha["arquivado_em"] is not None:
        raise ErroRegraViolada(
            f"O funcionário '{linha['nome']}' já está arquivado.",
            requisito="RN-06",
            campos={"arquivado_em": "Já arquivado."},
        )

    recorrencia = (
        await conexao.execute(
            text(
                "select id from recorrencias "
                "where funcionario_id = :func and excluido_em is null order by criado_em desc limit 1"
            ),
            {"func": str(funcionario_id)},
        )
    ).scalar_one_or_none()

    removidas = 0
    if recorrencia is not None:
        removidas = await repositorio_recorrencias.remove_futuras_nao_efetivadas(
            conexao, recorrencia, a_partir_de=date.today(), usuario_id=usuario.id
        )
        await repositorio_recorrencias.desativa(conexao, recorrencia)

    await conexao.execute(
        text("update funcionarios set arquivado_em = now() where id = :id"),
        {"id": str(funcionario_id)},
    )
    await mod_espelho.arquiva(conexao, vinculo=VINCULO, dono_id=funcionario_id)

    await registra_auditoria(
        conexao,
        entidade="funcionarios",
        entidade_id=funcionario_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={
            "arquivado_em": {"de": None, "para": "agora"},
            "ocorrencias_futuras_removidas": {"de": None, "para": removidas},
        },
    )

    return _para_json(
        await _exige(conexao, funcionario_id),
        **mod_arquivamento.resumo_do_arquivamento(ocorrencias_removidas=removidas),
    )
