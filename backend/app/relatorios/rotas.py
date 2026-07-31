"""Relatórios — contracts/consultas.md §3. `FR-090`–`FR-095`.

Papel: gestor, operador nos quatro. São leitura, e a spec diz que operador lê tudo.

## `formato` muda o envelope, nunca o conteúdo

`json` (padrão), `csv` ou `pdf`. O contrato é explícito: com `csv`/`pdf` a resposta é o
arquivo **com os mesmos dados do `json`** — nunca um recorte diferente. Por isso o
endpoint monta a resposta uma vez e passa o resultado pronto para o exportador, em vez de
cada formato consultar o banco por conta.

## O limiar de destaque não aparece no código

`variacao-categorias` marca `destacar: true` comparando com
`configuracoes.variacao_destaque_percentual`. O número 20 não existe em lugar nenhum do
frontend nem deste arquivo (`FR-092`, `RNF-02`) — ele vem no corpo da resposta, em
`limiar_destaque_percentual`, para a tela poder explicar o critério.

Tarefas: T115–T121
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import periodo as mod_periodo
from app.comum.erros import ErroValidacao
from app.db import obter_conexao
from app.dominio import inadimplencia as mod_inadimplencia
from app.dominio import mundo as mod_mundo
from app.lancamentos.servico import le_configuracao
from app.relatorios import exportacao_csv, exportacao_pdf, repositorio
from app.rotinas import diaria as rotina_diaria
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/relatorios", tags=["Relatórios"])
# Separado porque o contrato coloca a exportação completa fora de `/relatorios`: ela não
# é um relatório, é a cópia integral da base.
roteador_exportacoes = APIRouter(prefix="/api/exportacoes", tags=["Relatórios"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

FORMATOS = ("json", "csv", "pdf")

MESES_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


def _d(valor: Any) -> Decimal:
    return Decimal(str(valor or 0))


def _dinheiro(valor: Any) -> str:
    return f"{_d(valor):.2f}"


def _percentual(parte: Decimal, total: Decimal) -> str | None:
    """`null` quando o total é zero — "não dá para calcular" não é "zero por cento"."""
    if total == 0:
        return None
    return f"{(parte / total * 100):.1f}"


def _valida_formato(formato: str) -> str:
    if formato not in FORMATOS:
        raise ErroValidacao(
            f"Formato '{formato}' não existe.",
            requisito="FR-094",
            campos={"formato": f"Aceitos: {', '.join(FORMATOS)}."},
        )
    return formato


def _arquivo(conteudo: bytes, *, nome: str, tipo: str) -> Response:
    return Response(
        content=conteudo,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


def _rotulo_do_periodo(janela: mod_periodo.Periodo) -> str:
    return (
        f"{janela.rotulo} — {janela.inicio.strftime('%d/%m/%Y')} a "
        f"{janela.fim.strftime('%d/%m/%Y')}"
    )


def _hierarquia(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Monta categoria → subcategorias a partir do resultado de `grouping sets`.

    A linha com `subcategoria_id` nulo é o total da categoria; as demais são as filhas.
    """
    categorias: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        chave = str(linha["categoria_id"])
        if linha["subcategoria_id"] is None:
            categorias.setdefault(chave, {"subcategorias": []})
            categorias[chave] |= {
                "categoria_id": chave,
                "nome": linha["categoria_nome"],
                "cor": linha["cor"],
                "valor": _dinheiro(linha["valor"]),
                "quantidade": linha["quantidade"],
                "subcategorias": categorias[chave]["subcategorias"],
            }
        else:
            categorias.setdefault(chave, {"subcategorias": []})
            categorias[chave]["subcategorias"].append(
                {
                    "subcategoria_id": str(linha["subcategoria_id"]),
                    "nome": linha["subcategoria_nome"],
                    "valor": _dinheiro(linha["valor"]),
                    "quantidade": linha["quantidade"],
                }
            )
    return sorted(categorias.values(), key=lambda item: _d(item.get("valor")), reverse=True)


# ── T115 · DRE ──────────────────────────────────────────────────────────────


def _leitura_do_dre(
    *, janela: mod_periodo.Periodo, receitas: Decimal, despesas: Decimal, anterior: Decimal
) -> str:
    """`FR-095` — a leitura em linguagem natural, montada no servidor.

    Cita números que só o cálculo conhece, então é texto de **negócio**, não de
    interface (`RNF-02`).
    """
    from app.comum.erros import formata_dinheiro

    resultado = receitas - despesas
    rotulo = MESES_PT.get(janela.inicio.month, janela.rotulo).capitalize()

    if receitas == 0 and despesas == 0:
        return f"{rotulo} não teve nenhum lançamento efetivado."

    partes = [
        f"{rotulo} teve {formata_dinheiro(receitas)} de receita e "
        f"{formata_dinheiro(despesas)} de despesa"
    ]
    margem = _percentual(resultado, receitas)
    if resultado >= 0:
        partes.append(
            f"resultado positivo de {formata_dinheiro(resultado)}"
            + (f", margem de {margem.replace('.', ',')}%" if margem else "")
        )
    else:
        partes.append(f"resultado negativo de {formata_dinheiro(abs(resultado))}")

    if anterior != 0:
        variacao = (resultado - anterior) / abs(anterior) * 100
        direcao = "melhor" if variacao > 0 else "pior"
        partes.append(f"{abs(variacao):.1f}% {direcao} que o período anterior".replace(".", ","))

    return ". ".join(partes) + "."


@roteador.get(
    "/dre",
    summary="DRE do período, com quebra por subcategoria",
    description=(
        "Papel: gestor, operador. `FR-090`. `formato` = `json` (padrão) | `csv` | `pdf` — "
        "com arquivo, **os mesmos dados do json**, nunca um recorte diferente."
    ),
    response_class=Response,
)
async def dre(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    formato: Annotated[str, Query(description="json | csv | pdf.")] = "json",
) -> Any:
    _valida_formato(formato)
    await rotina_diaria.executa_se_necessario(conexao)

    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)

    receitas = await repositorio.por_categoria_e_subcategoria(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim, tipo="receita"
    )
    despesas = await repositorio.por_categoria_e_subcategoria(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim, tipo="despesa"
    )
    totais = await repositorio.totais(conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim)
    totais_anteriores = await repositorio.totais(
        conexao, mundos=mundos, inicio=janela.inicio_anterior, fim=janela.fim_anterior
    )

    # Acumulado do ano: a mesma consulta com outro recorte, para o DRE responder
    # "e no ano?" sem uma segunda requisição.
    acumulado = await repositorio.totais(
        conexao,
        mundos=mundos,
        inicio=date(janela.fim.year, 1, 1),
        fim=janela.fim,
    )

    receita_bruta, despesa_total = _d(totais["receitas"]), _d(totais["despesas"])
    resultado = receita_bruta - despesa_total
    resultado_anterior = _d(totais_anteriores["receitas"]) - _d(totais_anteriores["despesas"])

    resposta = {
        "periodo": janela.como_dicionario(),
        "mundo": mundo or "ambos",
        "periodo_vazio": receita_bruta == 0 and despesa_total == 0,
        "receitas": _hierarquia(receitas),
        "despesas": _hierarquia(despesas),
        "receita_bruta": _dinheiro(receita_bruta),
        "despesa_total": _dinheiro(despesa_total),
        "resultado": _dinheiro(resultado),
        "margem_percentual": _percentual(resultado, receita_bruta),
        "acumulado_ano": {
            "receita_bruta": _dinheiro(acumulado["receitas"]),
            "despesa_total": _dinheiro(acumulado["despesas"]),
            "resultado": _dinheiro(_d(acumulado["receitas"]) - _d(acumulado["despesas"])),
        },
        "comparativo_periodo_anterior": {
            "receita_bruta": _dinheiro(totais_anteriores["receitas"]),
            "despesa_total": _dinheiro(totais_anteriores["despesas"]),
            "resultado": _dinheiro(resultado_anterior),
        },
        "leitura_linguagem_natural": _leitura_do_dre(
            janela=janela,
            receitas=receita_bruta,
            despesas=despesa_total,
            anterior=resultado_anterior,
        ),
    }

    if formato == "csv":
        return _arquivo(
            exportacao_csv.dre(resposta),
            nome=f"dre-{janela.inicio.isoformat()}-a-{janela.fim.isoformat()}.csv",
            tipo="text/csv; charset=utf-8",
        )
    if formato == "pdf":
        return _arquivo(
            exportacao_pdf.dre(resposta, periodo_rotulo=_rotulo_do_periodo(janela)),
            nome=f"dre-{janela.inicio.isoformat()}-a-{janela.fim.isoformat()}.pdf",
            tipo="application/pdf",
        )
    return resposta


# ── T116 · Ranking de clientes ──────────────────────────────────────────────


@roteador.get(
    "/clientes",
    summary="Ranking de clientes por receita",
    description=(
        "Papel: gestor, operador. `FR-091`. `quebra_por_mundo` existe porque **o cliente "
        "não tem mundo** (D-04), mas a receita dele tem. `situacao` é derivada (`RN-10`)."
    ),
    response_class=Response,
)
async def clientes(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query()] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    formato: Annotated[str, Query(description="json | csv | pdf.")] = "json",
) -> Any:
    _valida_formato(formato)
    hoje = date.today()
    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)
    tolerancia = int(
        await le_configuracao(
            conexao,
            "inadimplencia_dias_tolerancia",
            padrao=mod_inadimplencia.PADRAO_DIAS_TOLERANCIA,
        )
    )

    linhas = await repositorio.por_cliente(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim
    )
    evolucao = await repositorio.evolucao_mensal_por_cliente(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim
    )
    por_cliente: dict[str, list[dict[str, str]]] = {}
    for item in evolucao:
        por_cliente.setdefault(str(item["cliente_id"]), []).append(
            {"mes": item["mes"], "valor": _dinheiro(item["valor"])}
        )

    faturamento = sum((_d(item["total"]) for item in linhas), Decimal("0"))

    from app.clientes import repositorio as repositorio_clientes

    itens = []
    for linha in linhas:
        abertos = await repositorio_clientes.em_aberto(conexao, linha["cliente_id"])
        situacao = mod_inadimplencia.avalia(abertos, tolerancia_dias=tolerancia, hoje=hoje)
        quebra = linha["quebra"] or {}
        itens.append(
            {
                "cliente_id": str(linha["cliente_id"]),
                "nome": linha["nome"],
                "empresa": linha["empresa"],
                "total_recebido": _dinheiro(linha["total"]),
                "percentual_faturamento": _percentual(_d(linha["total"]), faturamento),
                "evolucao_mensal": por_cliente.get(str(linha["cliente_id"]), []),
                "quebra_por_mundo": {
                    "digital": _dinheiro(quebra.get("digital", 0)),
                    "infra": _dinheiro(quebra.get("infra", 0)),
                },
                **situacao.como_dicionario(),
            }
        )

    resposta = {
        "periodo": janela.como_dicionario(),
        "mundo": mundo or "ambos",
        "faturamento_total": _dinheiro(faturamento),
        "tolerancia_dias": tolerancia,
        "clientes": itens,
    }

    if formato == "csv":
        return _arquivo(
            exportacao_csv.clientes(resposta),
            nome=f"clientes-{janela.inicio.isoformat()}-a-{janela.fim.isoformat()}.csv",
            tipo="text/csv; charset=utf-8",
        )
    if formato == "pdf":
        return _arquivo(
            exportacao_pdf.clientes(resposta, periodo_rotulo=_rotulo_do_periodo(janela)),
            nome=f"clientes-{janela.inicio.isoformat()}-a-{janela.fim.isoformat()}.pdf",
            tipo="application/pdf",
        )
    return resposta


# ── T117 · Variação por categoria ───────────────────────────────────────────


@roteador.get(
    "/variacao-categorias",
    summary="Variação mensal por categoria, com destaque configurável",
    description=(
        "Papel: gestor, operador. `FR-092`. `destacar` é calculado no servidor contra "
        "`configuracoes.variacao_destaque_percentual` — **o número não aparece no "
        "frontend** (`RNF-02`). Ele vem em `limiar_destaque_percentual`, para a tela "
        "poder explicar o critério."
    ),
    response_class=Response,
)
async def variacao_categorias(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query()] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    tipo: Annotated[str | None, Query(description="receita | despesa.")] = "despesa",
    formato: Annotated[str, Query(description="json | csv.")] = "json",
) -> Any:
    _valida_formato(formato)
    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)
    limiar = _d(await le_configuracao(conexao, "variacao_destaque_percentual", padrao=20))

    meses, linhas = await repositorio.matriz_mensal(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim, tipo=tipo
    )

    por_categoria: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        chave = str(linha["categoria_id"])
        registro = por_categoria.setdefault(
            chave,
            {
                "categoria_id": chave,
                "nome": linha["nome"],
                "cor": linha["cor"],
                "valores": [],
            },
        )
        registro["valores"].append({"mes": linha["mes"], "valor": _d(linha["valor"])})

    montadas = []
    for registro in por_categoria.values():
        valores = sorted(registro["valores"], key=lambda item: item["mes"])
        saida = []
        anterior: Decimal | None = None
        for item in valores:
            variacao = None
            destacar = False
            if anterior is not None and anterior != 0:
                calculo = (item["valor"] - anterior) / abs(anterior) * 100
                variacao = f"{calculo:.1f}"
                destacar = abs(calculo) >= limiar
            saida.append(
                {
                    "mes": item["mes"],
                    "valor": _dinheiro(item["valor"]),
                    "variacao_percentual": variacao,
                    "destacar": destacar,
                }
            )
            anterior = item["valor"]
        montadas.append({**registro, "valores": saida})

    resposta = {
        "periodo": janela.como_dicionario(),
        "mundo": mundo or "ambos",
        "tipo": tipo,
        "meses": meses,
        "linhas": sorted(montadas, key=lambda item: item["nome"].lower()),
        "limiar_destaque_percentual": float(limiar),
    }

    if formato == "csv":
        return _arquivo(
            exportacao_csv.variacao_categorias(resposta),
            nome=f"variacao-categorias-{janela.inicio.isoformat()}.csv",
            tipo="text/csv; charset=utf-8",
        )
    if formato == "pdf":
        raise ErroValidacao(
            "Este relatório não sai em PDF. Use CSV ou json.",
            requisito="FR-094",
            campos={"formato": "Aceitos aqui: json, csv."},
        )
    return resposta


# ── T118 · Matriz mensal ────────────────────────────────────────────────────


@roteador.get(
    "/matriz-mensal",
    summary="Meses × categorias, com todos os totais",
    description=(
        "Papel: gestor, operador. `FR-093`. Sem foco em variação — é a visão de conferir "
        "o ano inteiro de uma vez. Mês sem movimento aparece zerado, senão as colunas "
        "deixariam de comparar os mesmos meses."
    ),
    response_class=Response,
)
async def matriz_mensal(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query()] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    tipo: Annotated[str | None, Query(description="receita | despesa. Vazio traz os dois.")] = None,
    formato: Annotated[str, Query(description="json | csv.")] = "json",
) -> Any:
    _valida_formato(formato)
    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)

    meses, linhas = await repositorio.matriz_mensal(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim, tipo=tipo
    )

    por_categoria: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        chave = str(linha["categoria_id"])
        registro = por_categoria.setdefault(
            chave,
            {
                "categoria_id": chave,
                "nome": linha["nome"],
                "cor": linha["cor"],
                "valores": {},
                "_total": Decimal("0"),
            },
        )
        registro["valores"][linha["mes"]] = _dinheiro(linha["valor"])
        registro["_total"] += _d(linha["valor"])

    montadas = [
        {
            "categoria_id": item["categoria_id"],
            "nome": item["nome"],
            "cor": item["cor"],
            "valores": item["valores"],
            "total": _dinheiro(item["_total"]),
        }
        for item in sorted(por_categoria.values(), key=lambda i: i["_total"], reverse=True)
    ]

    totais_por_mes = {
        mes: _dinheiro(sum((_d(item["valores"].get(mes, 0)) for item in montadas), Decimal("0")))
        for mes in meses
    }

    resposta = {
        "periodo": janela.como_dicionario(),
        "mundo": mundo or "ambos",
        "tipo": tipo,
        "meses": meses,
        "linhas": montadas,
        "totais_por_mes": totais_por_mes,
    }

    if formato == "csv":
        return _arquivo(
            exportacao_csv.matriz_mensal(resposta),
            nome=f"matriz-mensal-{janela.inicio.isoformat()}.csv",
            tipo="text/csv; charset=utf-8",
        )
    if formato == "pdf":
        raise ErroValidacao(
            "Este relatório não sai em PDF. Use CSV ou json.",
            requisito="FR-094",
            campos={"formato": "Aceitos aqui: json, csv."},
        )
    return resposta


# ── T137 · Exportação completa (`FR-112`, `SC-011`) ─────────────────────────


@roteador_exportacoes.post(
    "/completa",
    summary="Baixa tudo: um CSV por tabela, num ZIP",
    description=(
        "Papel: **gestor**. `FR-112`. É a cópia de segurança que sai da empresa — CSVs "
        "abertos em qualquer planilha, sem depender de nada nosso. Os **anexos não vão "
        "no pacote**: são arquivos do bucket privado e embutir dezenas de PDFs estouraria "
        "a memória da função; `anexos.csv` traz o caminho de cada um."
    ),
    response_class=Response,
)
async def exportacao_completa(
    usuario: Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))],
    conexao: Conexao,
) -> Response:
    from app.relatorios import exportacao_completa as exportador

    pacote, contagens = await exportador.monta_zip(conexao)
    hoje = date.today().isoformat()
    return Response(
        content=pacote,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="synapse-exportacao-{hoje}.zip"',
            # Contagem no cabeçalho para o cliente conferir sem abrir o ZIP.
            "X-Total-Lancamentos": str(contagens.get("lancamentos", 0)),
        },
    )
