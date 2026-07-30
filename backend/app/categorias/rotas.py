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

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import periodo as mod_periodo
from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/categorias", tags=["Cadastros"])


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
    incluir_arquivadas: Annotated[bool, Query()] = False,
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
                      count(l.id) filter (where l.id is not null)              as quantidade,
                      coalesce(sum(l.valor) filter (where l.status = 'efetivado'), 0) as total_efetivado,
                      coalesce(sum(l.valor), 0)                               as total_periodo
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
                    where (:incluir_arquivadas or c.arquivada_em is null)
                    group by c.id
                    order by c.ordem, lower(c.nome)
                    """),
                {
                    "inicio": janela.inicio,
                    "fim": janela.fim,
                    "mundos": mundos,
                    "incluir_arquivadas": incluir_arquivadas,
                },
            )
        )
        .mappings()
        .all()
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
                "quantidade": linha["quantidade"],
                # Dinheiro sai como string decimal na fronteira (contracts/README.md).
                "total_efetivado": f"{linha['total_efetivado']:.2f}",
                "total_periodo": f"{linha['total_periodo']:.2f}",
            }
            for linha in linhas
        ],
        "periodo": janela.como_dicionario(),
    }
