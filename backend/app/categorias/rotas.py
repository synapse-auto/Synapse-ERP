"""Categorias — leitura. contracts/cadastros.md §1, `FR-074`.

Categorias **não têm mundo** (`RF-104`, `FR-006`): existem uma vez e servem aos dois
lados. Mas a **contagem e o total do período** são por mundo — "quanto gastei em
Infraestrutura no Digital" é uma pergunta legítima, e a resposta muda com o seletor.

`especial` e `vinculo` vêm na resposta porque é deles que o Dashboard monta os cards de
Clientes e Funcionários (`FR-079`). Nunca de comparação de nome: promover uma categoria
a especial é gravar `especial = true` e o `vinculo`, sem tocar em código.

O CRUD completo (`POST`, `PUT`, arquivar com o fluxo `422`) fica em `T103`, sub-fase B4.

Skill `supabase-postgres-best-practices` acionada antes da consulta (task 🟢). Dela veio
a decisão de agregar com `filter` numa passada só, em vez de subconsulta por linha — o
índice `lancamentos_categoria_idx` é `(categoria_id, data)`, que serve ao `join` com
recorte de período.

Tarefa: T050
"""

from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import periodo as mod_periodo
from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada
from app.db import obter_conexao
from app.dominio import arquivamento as mod_arquivamento
from app.dominio import espelho_subcategoria as mod_espelho
from app.dominio import mundo as mod_mundo
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/categorias", tags=["Cadastros"])
# Separado porque o contrato coloca a edição da subcategoria em `/api/subcategorias/{id}`,
# não aninhada na categoria: a subcategoria já sabe a qual categoria pertence, e exigir os
# dois ids na URL abriria a porta para os dois discordarem.
roteador_subcategorias = APIRouter(prefix="/api/subcategorias", tags=["Cadastros"])


@roteador.get(
    "",
    summary="Lista as categorias com contagem e total do período",
    description=(
        "Papel: gestor, operador. A categoria não tem mundo (`FR-006`), mas a contagem e "
        "o total respeitam o mundo e o período ativos (`FR-074`)."
    ),
)
async def listar(
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[str | None, Query()] = None,
    data_fim: Annotated[str | None, Query()] = None,
    # O nome vem de contracts/cadastros.md §1 e é o mesmo dos outros cadastros:
    # `incluir_arquivados`. Estava escrito `incluir_arquivadas` (concordando com
    # "categoria"), e como o FastAPI **ignora** parâmetro de consulta desconhecido, o
    # que o frontend mandava caía no vazio: a caixa "Mostrar arquivadas" da tela de
    # Categorias não fazia nada, sem erro nenhum. Corrigido em 2026-08-03.
    incluir_arquivados: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    from datetime import date as tipo_data

    janela = mod_periodo.resolve(
        periodo,
        data_inicio=tipo_data.fromisoformat(data_inicio) if data_inicio else None,
        data_fim=tipo_data.fromisoformat(data_fim) if data_fim else None,
    )
    mundos = mod_mundo.resolve_filtro(mundo)

    linhas = (
        (
            await conexao.execute(
                text("""
                    select
                      c.id, c.nome, c.cor, c.icone, c.tipo, c.especial, c.vinculo,
                      c.ordem, c.arquivada_em,
                      -- `total_periodo` acompanha `quantidade`: os dois contam o mesmo
                      -- recorte (período, mundo, não-cancelado), senão a tela mostraria
                      -- "3 lanç." ao lado de um total que não é o desses três.
                      count(l.id) filter (where l.id is not null) as quantidade,
                      coalesce(sum(l.valor), 0)                   as total_periodo
                    from categorias c
                    left join lancamentos_ativos l
                      on l.categoria_id = c.id
                     and l.data between :inicio and :fim
                     and l.mundo = any(cast(:mundos as mundo[]))
                     and l.status <> 'cancelado'
                     -- RN-11: o pai de um split não conta; só as partes
                     and not exists (
                       select 1 from lancamentos p where p.lancamento_pai_id = l.id
                                                     and p.excluido_em is null
                     )
                    where (:incluir_arquivados or c.arquivada_em is null)
                    group by c.id
                    order by c.ordem, lower(c.nome)
                    """),
                {
                    "inicio": janela.inicio,
                    "fim": janela.fim,
                    "mundos": mundos,
                    "incluir_arquivados": incluir_arquivados,
                },
            )
        )
        .mappings()
        .all()
    )

    # As subcategorias vêm numa segunda consulta, com o **mesmo** recorte de mundo e
    # período do `left join` acima — senão o `uso` da filha contaria um universo e o da
    # mãe outro, e as duas linhas da tela discordariam sem ninguém saber por quê.
    #
    # Uma consulta a mais, não uma por categoria: são nove categorias e dezenas de
    # subcategorias no total, e agrupar aqui é mais barato que `N+1` idas ao banco.
    subcategorias = (
        (
            await conexao.execute(
                text("""
                    select
                      s.id, s.categoria_id, s.nome, s.cor, s.ordem,
                      s.cliente_id, s.funcionario_id, s.arquivada_em,
                      count(l.id) filter (where l.id is not null) as quantidade,
                      coalesce(sum(l.valor), 0)                   as total
                    from subcategorias s
                    left join lancamentos_ativos l
                      on l.subcategoria_id = s.id
                     and l.data between :inicio and :fim
                     and l.mundo = any(cast(:mundos as mundo[]))
                     and l.status <> 'cancelado'
                     and not exists (
                       select 1 from lancamentos p where p.lancamento_pai_id = l.id
                                                     and p.excluido_em is null
                     )
                    where (:incluir_arquivados or s.arquivada_em is null)
                    group by s.id
                    order by s.ordem, lower(s.nome)
                    """),
                {
                    "inicio": janela.inicio,
                    "fim": janela.fim,
                    "mundos": mundos,
                    "incluir_arquivados": incluir_arquivados,
                },
            )
        )
        .mappings()
        .all()
    )

    por_categoria: dict[str, list[dict[str, Any]]] = {}
    for filha in subcategorias:
        por_categoria.setdefault(str(filha["categoria_id"]), []).append(
            {
                "id": str(filha["id"]),
                "nome": filha["nome"],
                "cor": filha["cor"],
                "ordem": filha["ordem"],
                "cliente_id": str(filha["cliente_id"]) if filha["cliente_id"] else None,
                "funcionario_id": (
                    str(filha["funcionario_id"]) if filha["funcionario_id"] else None
                ),
                "arquivada_em": (
                    filha["arquivada_em"].isoformat() if filha["arquivada_em"] else None
                ),
                "uso": {
                    "quantidade_lancamentos": filha["quantidade"],
                    "total_movimentado": f"{filha['total']:.2f}",
                },
            }
        )

    return {
        "itens": [
            {
                "id": str(linha["id"]),
                "nome": linha["nome"],
                "cor": linha["cor"],
                "icone": linha["icone"],
                "tipo": linha["tipo"],
                "especial": linha["especial"],
                "vinculo": linha["vinculo"],
                "ordem": linha["ordem"],
                "arquivada_em": (
                    linha["arquivada_em"].isoformat() if linha["arquivada_em"] else None
                ),
                # `uso` e `subcategorias` são o que contracts/cadastros.md §1 promete, e
                # é deles que a tela vive: `c.uso.quantidade_lancamentos` e
                # `c.subcategorias.length`. A resposta antiga trazia `quantidade`,
                # `total_efetivado` e `total_periodo` soltos, sem subcategoria nenhuma —
                # a tela de Categorias quebrava em
                # `Cannot read properties of undefined (reading 'length')`.
                #
                # Dinheiro sai como string decimal na fronteira (contracts/README.md).
                "uso": {
                    "quantidade_lancamentos": linha["quantidade"],
                    "total_movimentado": f"{linha['total_periodo']:.2f}",
                },
                "subcategorias": por_categoria.get(str(linha["id"]), []),
            }
            for linha in linhas
        ],
        "periodo": janela.como_dicionario(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CRUD de gestor — T103 (categorias) e T104 (subcategorias), sub-fase B4
#
# A parte que exige cuidado é o arquivamento: `RN-06` diz que nunca pode existir
# lançamento órfão, e a categoria é obrigatória em todo lançamento. Por isso arquivar
# uma categoria com movimento responde `422` pedindo uma escolha — mover os lançamentos
# ou manter o vínculo somente-leitura — em vez de decidir sozinho. A regra mora em
# `dominio/arquivamento.py`.
# ─────────────────────────────────────────────────────────────────────────────


class CategoriaEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    cor: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    icone: str = Field(min_length=1, max_length=60, description="Nome do ícone Lucide.")
    tipo: Literal["receita", "despesa", "ambas"]
    especial: bool = False
    vinculo: Literal["cliente", "funcionario"] | None = None
    ordem: int = 0

    @model_validator(mode="after")
    def _especial_exige_vinculo(self) -> "CategoriaEntrada":
        if self.especial and self.vinculo is None:
            raise ValueError(
                "Categoria especial precisa dizer se o vínculo é cliente ou funcionário."
            )
        if not self.especial and self.vinculo is not None:
            raise ValueError("Só categoria especial tem vínculo.")
        return self


class ArquivarCategoriaEntrada(BaseModel):
    destino_lancamentos: UUID | None = Field(
        default=None, description="Move os lançamentos para esta categoria."
    )
    manter_somente_leitura: bool = Field(
        default=False,
        description=(
            "Os lançamentos ficam onde estão e a categoria some dos formulários novos. "
            "Preserva o fechamento dos meses passados."
        ),
    )


class SubcategoriaEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    cor: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    ordem: int = 0


async def _exige_categoria(conexao: AsyncConnection, categoria_id: UUID) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text(
                    "select id, nome, cor, icone, tipo, especial, vinculo, ordem, arquivada_em "
                    "from categorias where id = :id"
                ),
                {"id": str(categoria_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Categoria não encontrada.")
    return dict(linha)


def _categoria_json(linha: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "nome": linha["nome"],
        "cor": linha["cor"],
        "icone": linha["icone"],
        "tipo": linha["tipo"],
        "especial": linha["especial"],
        "vinculo": linha["vinculo"],
        "ordem": linha["ordem"],
        "arquivada_em": linha["arquivada_em"].isoformat() if linha["arquivada_em"] else None,
        **extra,
    }


@roteador.post(
    "",
    status_code=201,
    summary="Cria uma categoria",
    description=(
        "Papel: **gestor**. Categoria **não aceita `mundo`** (`FR-006`): existe uma vez e "
        "serve aos dois lados. `especial: true` exige `vinculo`."
    ),
)
async def criar(
    corpo: CategoriaEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    nova = (
        await conexao.execute(
            text("""
                insert into categorias (nome, cor, icone, tipo, especial, vinculo, ordem)
                values (:nome, :cor, :icone, cast(:tipo as tipo_categoria), :especial,
                        cast(:vinculo as vinculo_subcategoria), :ordem)
                returning id
                """),
            {
                "nome": corpo.nome,
                "cor": corpo.cor,
                "icone": corpo.icone,
                "tipo": corpo.tipo,
                "especial": corpo.especial,
                "vinculo": corpo.vinculo,
                "ordem": corpo.ordem,
            },
        )
    ).scalar_one()

    await registra_auditoria(
        conexao,
        entidade="categorias",
        entidade_id=nova,
        acao="criacao",
        usuario_id=usuario.id,
        depois={"nome": corpo.nome, "tipo": corpo.tipo, "especial": corpo.especial},
    )
    return _categoria_json(await _exige_categoria(conexao, nova))


@roteador.put(
    "/{categoria_id}",
    summary="Edita a categoria — inclusive para promovê-la a especial",
    description=(
        "Papel: **gestor**. **Promover a especial é só isto** (`FR-079`): `especial: true` "
        "mais o `vinculo`. Não há deploy envolvido, porque nada no código compara nome de "
        "categoria. A resposta lista as subcategorias que ficaram sem dono, para o gestor "
        "saber o que precisa vincular."
    ),
)
async def editar(
    categoria_id: UUID,
    corpo: CategoriaEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    atual = await _exige_categoria(conexao, categoria_id)

    # `vinculo` é único entre as categorias ativas (índice `categorias_vinculo_uidx`), e
    # tem que ser: `dominio/espelho_subcategoria.py` precisa saber em **qual** categoria
    # criar a subcategoria espelho quando um cliente é cadastrado. Com duas categorias
    # `vinculo = 'cliente'`, a pergunta não tem resposta.
    #
    # Sem esta checagem o `update` batia direto no índice e o usuário recebia
    # `500 erro_interno` — "Algo deu errado do nosso lado" para uma ação previsível, com
    # a explicação só no log. Agora a recusa diz **qual** categoria já ocupa o vínculo,
    # que é a informação necessária para resolver (`FR-079`, contracts/README.md §Erros).
    if corpo.vinculo and corpo.vinculo != atual["vinculo"]:
        ocupante = (
            (
                await conexao.execute(
                    text("""
                        select nome from categorias
                        where vinculo = cast(:vinculo as vinculo_subcategoria)
                          and arquivada_em is null and id <> :id
                        """),
                    {"vinculo": corpo.vinculo, "id": str(categoria_id)},
                )
            )
            .scalars()
            .first()
        )
        if ocupante is not None:
            raise ErroRegraViolada(
                (
                    f"A categoria '{ocupante}' já é a categoria especial de "
                    f"{corpo.vinculo}. Só pode existir uma."
                ),
                requisito="FR-079",
                campos={
                    "vinculo": (
                        f"Arquive ou mude o vínculo de '{ocupante}' antes de promover esta."
                    )
                },
            )

    await conexao.execute(
        text("""
            update categorias set
              nome = :nome, cor = :cor, icone = :icone,
              tipo = cast(:tipo as tipo_categoria), especial = :especial,
              vinculo = cast(:vinculo as vinculo_subcategoria), ordem = :ordem
            where id = :id
            """),
        {
            "id": str(categoria_id),
            "nome": corpo.nome,
            "cor": corpo.cor,
            "icone": corpo.icone,
            "tipo": corpo.tipo,
            "especial": corpo.especial,
            "vinculo": corpo.vinculo,
            "ordem": corpo.ordem,
        },
    )

    pendentes: list[dict[str, Any]] = []
    if corpo.especial and not atual["especial"]:
        # Ao promover, as subcategorias que já existiam não têm dono. Não são apagadas
        # nem vinculadas por adivinhação — são **apontadas**, para o gestor decidir.
        linhas = (
            (
                await conexao.execute(
                    text("""
                        select id, nome from subcategorias
                        where categoria_id = :id
                          and cliente_id is null and funcionario_id is null
                          and arquivada_em is null
                        order by lower(nome)
                        """),
                    {"id": str(categoria_id)},
                )
            )
            .mappings()
            .all()
        )
        pendentes = [{"id": str(item["id"]), "nome": item["nome"]} for item in linhas]

    await registra_auditoria(
        conexao,
        entidade="categorias",
        entidade_id=categoria_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes={k: atual[k] for k in ("nome", "cor", "icone", "tipo", "especial", "vinculo")},
        depois={
            "nome": corpo.nome,
            "cor": corpo.cor,
            "icone": corpo.icone,
            "tipo": corpo.tipo,
            "especial": corpo.especial,
            "vinculo": corpo.vinculo,
        },
    )

    return _categoria_json(
        await _exige_categoria(conexao, categoria_id),
        subcategorias_pendentes_de_vinculo=pendentes,
    )


@roteador.post(
    "/{categoria_id}/arquivar",
    summary="Arquiva a categoria, sem deixar lançamento órfão",
    description=(
        "Papel: **gestor**. `RN-06`, `FR-075`. Com lançamentos e sem escolha → `422` com "
        "a contagem. Escolha `destino_lancamentos` (move o histórico) **ou** "
        "`manter_somente_leitura` (o histórico fica e a categoria some dos formulários). "
        "Categoria **especial** não se arquiva por aqui — arquive os clientes ou "
        "funcionários e ela fica vazia sozinha."
    ),
)
async def arquivar(
    categoria_id: UUID,
    corpo: ArquivarCategoriaEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    atual = await _exige_categoria(conexao, categoria_id)
    if atual["arquivada_em"] is not None:
        raise ErroRegraViolada(
            f"A categoria '{atual['nome']}' já está arquivada.",
            requisito="RN-06",
            campos={"arquivada_em": "Já arquivada."},
        )

    mod_arquivamento.recusa_arquivar_especial(
        nome=atual["nome"], especial=atual["especial"], vinculo=atual["vinculo"]
    )
    mod_arquivamento.recusa_mover_para_si_mesma(
        origem=str(categoria_id),
        destino=str(corpo.destino_lancamentos) if corpo.destino_lancamentos else None,
    )

    uso = (
        (
            await conexao.execute(
                text("""
                    select count(*) as quantidade, coalesce(sum(valor), 0) as valor_total
                    from lancamentos_ativos where categoria_id = :id
                    """),
                {"id": str(categoria_id)},
            )
        )
        .mappings()
        .one()
    )

    destino = mod_arquivamento.exige_destino(
        nome=atual["nome"],
        quantidade_lancamentos=uso["quantidade"],
        valor_total=Decimal(str(uso["valor_total"])),
        destino_lancamentos=(str(corpo.destino_lancamentos) if corpo.destino_lancamentos else None),
        manter_somente_leitura=corpo.manter_somente_leitura,
    )

    movidos = 0
    if destino.move:
        await _exige_categoria(conexao, UUID(destino.mover_para))
        resultado = await conexao.execute(
            text("""
                update lancamentos set categoria_id = cast(:destino as uuid),
                       atualizado_por = cast(:usuario as uuid)
                where categoria_id = :origem and excluido_em is null
                """),
            {
                "origem": str(categoria_id),
                "destino": destino.mover_para,
                "usuario": str(usuario.id),
            },
        )
        movidos = resultado.rowcount or 0

    await conexao.execute(
        text("update categorias set arquivada_em = now() where id = :id"),
        {"id": str(categoria_id)},
    )
    await registra_auditoria(
        conexao,
        entidade="categorias",
        entidade_id=categoria_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={
            "arquivada_em": {"de": None, "para": "agora"},
            "lancamentos_movidos": {"de": None, "para": movidos},
        },
    )

    return _categoria_json(
        await _exige_categoria(conexao, categoria_id),
        **mod_arquivamento.resumo_do_arquivamento(
            ocorrencias_removidas=0, lancamentos_movidos=movidos
        ),
    )


@roteador.post(
    "/{categoria_id}/desarquivar",
    summary="Traz a categoria de volta aos formulários",
    description="Papel: **gestor**. `RN-06`.",
)
async def desarquivar(
    categoria_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    atual = await _exige_categoria(conexao, categoria_id)
    if atual["arquivada_em"] is None:
        raise ErroRegraViolada(
            f"A categoria '{atual['nome']}' não está arquivada.",
            requisito="RN-06",
            campos={"arquivada_em": "Já ativa."},
        )
    await conexao.execute(
        text("update categorias set arquivada_em = null where id = :id"),
        {"id": str(categoria_id)},
    )
    await registra_auditoria(
        conexao,
        entidade="categorias",
        entidade_id=categoria_id,
        acao="restauracao",
        usuario_id=usuario.id,
        alteracoes={"arquivada_em": {"de": "arquivada", "para": None}},
    )
    return _categoria_json(await _exige_categoria(conexao, categoria_id))


# ── T104 · Subcategorias — contracts/cadastros.md §2 ────────────────────────


@roteador.post(
    "/{categoria_id}/subcategorias",
    status_code=201,
    summary="Cria uma subcategoria",
    description=(
        "Papel: **gestor**. Em categoria **com `vinculo`** isto é recusado com `409` / "
        "`RF-055`: ali a subcategoria nasce do cadastro do cliente ou do funcionário "
        "(D-07), e a mensagem diz onde cadastrar. Uma subcategoria criada à mão numa "
        "categoria especial seria um cliente sem perfil, sem cobrança e sem inadimplência."
    ),
)
async def criar_subcategoria(
    categoria_id: UUID,
    corpo: SubcategoriaEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    await _exige_categoria(conexao, categoria_id)
    await mod_espelho.recusa_criacao_manual(conexao, categoria_id)

    nova = (
        (
            await conexao.execute(
                text("""
                    insert into subcategorias (categoria_id, nome, cor, ordem)
                    values (:categoria, :nome, :cor, :ordem)
                    returning id, nome, cor, ordem, arquivada_em
                    """),
                {
                    "categoria": str(categoria_id),
                    "nome": corpo.nome,
                    "cor": corpo.cor,
                    "ordem": corpo.ordem,
                },
            )
        )
        .mappings()
        .one()
    )

    await registra_auditoria(
        conexao,
        entidade="subcategorias",
        entidade_id=nova["id"],
        acao="criacao",
        usuario_id=usuario.id,
        depois={"nome": corpo.nome, "categoria_id": categoria_id},
    )
    return {
        "id": str(nova["id"]),
        "categoria_id": str(categoria_id),
        "nome": nova["nome"],
        "cor": nova["cor"],
        "ordem": nova["ordem"],
        "cliente_id": None,
        "funcionario_id": None,
        "arquivada_em": None,
    }


@roteador.get(
    "/{categoria_id}",
    summary="Uma categoria, com as subcategorias",
    description="Papel: gestor, operador.",
)
async def detalhar(
    categoria_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    linha = await _exige_categoria(conexao, categoria_id)
    subcategorias = (
        (
            await conexao.execute(
                text("""
                    select id, nome, cor, ordem, cliente_id, funcionario_id, arquivada_em
                    from subcategorias where categoria_id = :id
                    order by ordem, lower(nome)
                    """),
                {"id": str(categoria_id)},
            )
        )
        .mappings()
        .all()
    )
    return _categoria_json(
        linha,
        subcategorias=[
            {
                "id": str(item["id"]),
                "nome": item["nome"],
                "cor": item["cor"],
                "ordem": item["ordem"],
                "cliente_id": str(item["cliente_id"]) if item["cliente_id"] else None,
                "funcionario_id": (str(item["funcionario_id"]) if item["funcionario_id"] else None),
                "arquivada_em": (
                    item["arquivada_em"].isoformat() if item["arquivada_em"] else None
                ),
            }
            for item in subcategorias
        ],
    )


async def _exige_subcategoria(conexao: AsyncConnection, subcategoria_id: UUID) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text("""
                    select id, categoria_id, nome, cor, ordem,
                           cliente_id, funcionario_id, arquivada_em
                    from subcategorias where id = :id
                    """),
                {"id": str(subcategoria_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Subcategoria não encontrada.")
    return dict(linha)


def _subcategoria_json(linha: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "categoria_id": str(linha["categoria_id"]),
        "nome": linha["nome"],
        "cor": linha["cor"],
        "ordem": linha["ordem"],
        "cliente_id": str(linha["cliente_id"]) if linha["cliente_id"] else None,
        "funcionario_id": str(linha["funcionario_id"]) if linha["funcionario_id"] else None,
        "arquivada_em": linha["arquivada_em"].isoformat() if linha["arquivada_em"] else None,
    }


@roteador_subcategorias.put(
    "/{subcategoria_id}",
    summary="Edita a subcategoria",
    description=(
        "Papel: **gestor**. Subcategoria **espelho** (com `cliente_id` ou "
        "`funcionario_id`) não se renomeia por aqui: o nome vem do cadastro, e mudá-lo "
        "só de um lado faria a tela de clientes e o Dashboard mostrarem nomes diferentes "
        "(D-07). Renomeie o cliente ou o funcionário."
    ),
)
async def editar_subcategoria(
    subcategoria_id: UUID,
    corpo: SubcategoriaEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    atual = await _exige_subcategoria(conexao, subcategoria_id)

    if atual["cliente_id"] or atual["funcionario_id"]:
        quem = "cliente" if atual["cliente_id"] else "funcionário"
        raise ErroRegraViolada(
            (
                f"'{atual['nome']}' espelha um {quem}. Renomeie o cadastro do {quem} — a "
                "subcategoria acompanha sozinha."
            ),
            requisito="D-07",
            campos={"nome": f"O nome vem do cadastro do {quem}."},
        )

    depois = (
        (
            await conexao.execute(
                text("""
                    update subcategorias set nome = :nome, cor = :cor, ordem = :ordem
                    where id = :id
                    returning id, categoria_id, nome, cor, ordem,
                              cliente_id, funcionario_id, arquivada_em
                    """),
                {
                    "id": str(subcategoria_id),
                    "nome": corpo.nome,
                    "cor": corpo.cor,
                    "ordem": corpo.ordem,
                },
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="subcategorias",
        entidade_id=subcategoria_id,
        acao="edicao",
        usuario_id=usuario.id,
        antes={k: atual[k] for k in ("nome", "cor", "ordem")},
        depois={"nome": corpo.nome, "cor": corpo.cor, "ordem": corpo.ordem},
    )
    return _subcategoria_json(dict(depois))


@roteador_subcategorias.post(
    "/{subcategoria_id}/arquivar",
    summary="Arquiva a subcategoria",
    description=(
        "Papel: **gestor**. `RN-06`: some dos formulários novos, os lançamentos antigos "
        "continuam apontando para ela. Subcategoria espelho é arquivada ao arquivar o "
        "cliente ou o funcionário — aqui é recusada, para os dois não divergirem."
    ),
)
async def arquivar_subcategoria(
    subcategoria_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Annotated[AsyncConnection, Depends(obter_conexao)],
) -> dict[str, Any]:
    atual = await _exige_subcategoria(conexao, subcategoria_id)

    if atual["cliente_id"] or atual["funcionario_id"]:
        quem = "cliente" if atual["cliente_id"] else "funcionário"
        raise ErroRegraViolada(
            f"'{atual['nome']}' espelha um {quem}. Arquive o cadastro do {quem}.",
            requisito="D-07",
            campos={"subcategoria": f"Arquive o {quem}."},
        )
    if atual["arquivada_em"] is not None:
        raise ErroRegraViolada(
            f"A subcategoria '{atual['nome']}' já está arquivada.",
            requisito="RN-06",
            campos={"arquivada_em": "Já arquivada."},
        )

    depois = (
        (
            await conexao.execute(
                text("""
                    update subcategorias set arquivada_em = now() where id = :id
                    returning id, categoria_id, nome, cor, ordem,
                              cliente_id, funcionario_id, arquivada_em
                    """),
                {"id": str(subcategoria_id)},
            )
        )
        .mappings()
        .one()
    )
    await registra_auditoria(
        conexao,
        entidade="subcategorias",
        entidade_id=subcategoria_id,
        acao="exclusao",
        usuario_id=usuario.id,
        alteracoes={"arquivada_em": {"de": None, "para": "agora"}},
    )
    return _subcategoria_json(dict(depois))
