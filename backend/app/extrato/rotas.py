"""`GET /api/extrato` — contracts/consultas.md §2. Papel: gestor, operador.

O extrato é o "olhar de contador" do sistema: a mesma base do Dashboard, mas em ordem
cronológica e com saldo correndo ao lado. A garantia que o contrato cobra — o
`saldo_acumulado` do último grupo bater com `resumo.saldo_final` — é montada em
`servico.py` e conferida por teste de integração.

Tarefa: T096
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import periodo as mod_periodo
from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.extrato import servico
from app.rotinas import diaria as rotina_diaria
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/extrato", tags=["Consultas"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]


def _d(valor: Any) -> Decimal:
    return Decimal(str(valor or 0))


def _variacao(atual: Decimal, anterior: Decimal) -> dict[str, Any]:
    if anterior == 0:
        return {
            "variacao_percentual": None,
            "direcao": "alta" if atual > 0 else "estavel",
        }
    variacao = (atual - anterior) / abs(anterior) * 100
    return {
        "variacao_percentual": f"{variacao:.1f}",
        "direcao": "alta" if variacao > 0 else ("baixa" if variacao < 0 else "estavel"),
    }


@roteador.get(
    "",
    summary="Extrato agrupado, com saldo acumulado",
    description=(
        "Papel: gestor, operador. `FR-047`–`FR-052`. `agrupamento` = `dia` | `semana` | "
        "`mes`. O `saldo_acumulado` do último grupo é **igual** a `resumo.saldo_final` — "
        "o servidor garante a coerência. Grupos futuros vêm com `previsto: true` e "
        "**não** entram no acumulado (`RN-05`). A seção `pendencias` ignora o filtro de "
        "período: pendência não é histórico (`FR-051`)."
    ),
)
async def obter(
    usuario: Autenticado,
    conexao: Conexao,
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
    periodo: Annotated[str | None, Query()] = None,
    data_inicio: Annotated[date | None, Query()] = None,
    data_fim: Annotated[date | None, Query()] = None,
    agrupamento: Annotated[str, Query(description="dia | semana | mes.")] = "dia",
) -> dict[str, Any]:
    await rotina_diaria.executa_se_necessario(conexao)  # T085

    hoje = date.today()
    mundos = mod_mundo.resolve_filtro(mundo)
    janela = mod_periodo.resolve(periodo, data_inicio=data_inicio, data_fim=data_fim)
    servico.valida_agrupamento(agrupamento)

    saldo_base = await servico.saldo_antes(conexao, mundos=mundos, inicio=janela.inicio)
    atual = await servico.totais_do_periodo(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim
    )
    anterior = await servico.totais_do_periodo(
        conexao, mundos=mundos, inicio=janela.inicio_anterior, fim=janela.fim_anterior
    )

    linhas = await servico.lancamentos_do_periodo(
        conexao, mundos=mundos, inicio=janela.inicio, fim=janela.fim, agrupamento=agrupamento
    )
    grupos = servico.monta_grupos(linhas, agrupamento=agrupamento, saldo_base=saldo_base, hoje=hoje)

    receitas, despesas = _d(atual["receitas"]), _d(atual["despesas"])
    receitas_ant, despesas_ant = _d(anterior["receitas"]), _d(anterior["despesas"])
    resultado, resultado_ant = receitas - despesas, receitas_ant - despesas_ant

    # A coerência que o contrato cobra: o saldo final é a base mais o que foi efetivado
    # no período. É o mesmo número que o último grupo não previsto acumulou.
    saldo_final = saldo_base + resultado
    saldo_final_ant = (
        await servico.saldo_antes(conexao, mundos=mundos, inicio=janela.inicio_anterior)
    ) + resultado_ant

    return {
        "periodo": janela.como_dicionario(),
        "mundo": mundo or "ambos",
        "agrupamento": agrupamento,
        "periodo_vazio": not linhas,
        "resumo": {
            "total_receitas": f"{receitas:.2f}",
            "total_despesas": f"{despesas:.2f}",
            "resultado": f"{resultado:.2f}",
            "saldo_final": f"{saldo_final:.2f}",
            "saldo_anterior_ao_periodo": f"{saldo_base:.2f}",
            "comparativos": {
                "total_receitas": _variacao(receitas, receitas_ant),
                "total_despesas": _variacao(despesas, despesas_ant),
                "resultado": _variacao(resultado, resultado_ant),
                "saldo_final": _variacao(saldo_final, saldo_final_ant),
            },
        },
        "grafico": servico.monta_grafico(grupos),
        "grupos": grupos,
        "pendencias": await servico.pendencias(conexao, mundos=mundos, hoje=hoje),
    }
