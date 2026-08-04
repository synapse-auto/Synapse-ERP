"""Busca global — contracts/consultas.md §4. `FR-046`.

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T132).

**Usa `pg_trgm` com `%` (similaridade), não `ilike '%texto%'`.** O `%` usa o índice GIN
que a migração `004` criou; o `ilike` com curinga na frente varreria a tabela inteira a
cada tecla digitada — e esta busca é chamada enquanto o usuário digita.

**Mínimo de 2 caracteres.** Abaixo disso devolve listas vazias em vez de varrer a base:
uma letra casa com quase tudo, e o resultado seria inútil e caro ao mesmo tempo.

Lançamentos e funcionários respeitam o mundo ativo; clientes e categorias não têm mundo
(`RF-101`, D-04).

Tarefas: T132, T212 (funcionários entram na busca — Boss 4)
"""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/busca", tags=["Consultas"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

MINIMO_DE_CARACTERES = 2
LIMITE_PADRAO = 5


@roteador.get(
    "",
    summary="Busca global em lançamentos, clientes, funcionários e categorias",
    description=(
        "Papel: gestor, operador. `FR-046`. Mínimo de 2 caracteres — abaixo disso devolve "
        "listas vazias em vez de varrer a tabela. Lançamentos e funcionários respeitam o "
        "mundo ativo; clientes e categorias não têm mundo. Usa `pg_trgm`, então acha por "
        "semelhança e aguenta erro de digitação."
    ),
)
async def buscar(
    usuario: Autenticado,
    conexao: Conexao,
    q: Annotated[str, Query(min_length=0, description="Texto procurado.")] = "",
    limite: Annotated[int, Query(ge=1, le=20)] = LIMITE_PADRAO,
    mundo: Annotated[str | None, Query(description="digital | infra | ambos.")] = None,
) -> dict[str, Any]:
    termo = q.strip()
    if len(termo) < MINIMO_DE_CARACTERES:
        return {
            "termo": termo,
            "lancamentos": [],
            "clientes": [],
            "funcionarios": [],
            "categorias": [],
            "minimo_de_caracteres": MINIMO_DE_CARACTERES,
        }

    mundos = mod_mundo.resolve_filtro(mundo)

    lancamentos = (
        (
            await conexao.execute(
                text("""
                    select l.id, l.descricao, l.valor, l.data, l.mundo, l.tipo, l.status,
                           c.nome as categoria_nome
                    from lancamentos_ativos l
                    join categorias c on c.id = l.categoria_id
                    where l.mundo = any(cast(:mundos as mundo[]))
                      and l.descricao % :termo
                    order by similarity(l.descricao, :termo) desc, l.data desc
                    limit :limite
                    """),
                {"mundos": mundos, "termo": termo, "limite": limite},
            )
        )
        .mappings()
        .all()
    )

    clientes = (
        (
            await conexao.execute(
                text("""
                    select id, nome, empresa
                    from clientes
                    where arquivado_em is null
                      and (nome % :termo or coalesce(empresa, '') % :termo)
                    order by similarity(nome, :termo) desc
                    limit :limite
                    """),
                {"termo": termo, "limite": limite},
            )
        )
        .mappings()
        .all()
    )

    # Funcionário tem mundo (`RN-15`), então segue o mundo ativo como o lançamento.
    # Busca por nome **e por função**: quem procura "designer" quer a pessoa, não
    # precisa lembrar o nome dela.
    funcionarios = (
        (
            await conexao.execute(
                text("""
                    select id, nome, funcao, mundo
                    from funcionarios
                    where arquivado_em is null
                      and mundo = any(cast(:mundos as mundo[]))
                      and (nome % :termo or funcao % :termo)
                    order by greatest(similarity(nome, :termo), similarity(funcao, :termo)) desc
                    limit :limite
                    """),
                {"mundos": mundos, "termo": termo, "limite": limite},
            )
        )
        .mappings()
        .all()
    )

    categorias = (
        (
            await conexao.execute(
                text("""
                    select id, nome, cor, icone
                    from categorias
                    where arquivada_em is null and nome % :termo
                    order by similarity(nome, :termo) desc
                    limit :limite
                    """),
                {"termo": termo, "limite": limite},
            )
        )
        .mappings()
        .all()
    )

    return {
        "termo": termo,
        "lancamentos": [
            {
                "id": str(linha["id"]),
                "descricao": linha["descricao"],
                "valor": f"{Decimal(str(linha['valor'])):.2f}",
                "data": linha["data"].isoformat(),
                "mundo": linha["mundo"],
                "tipo": linha["tipo"],
                "status": linha["status"],
                "categoria": linha["categoria_nome"],
            }
            for linha in lancamentos
        ],
        "clientes": [
            {"id": str(linha["id"]), "nome": linha["nome"], "empresa": linha["empresa"]}
            for linha in clientes
        ],
        "funcionarios": [
            {
                "id": str(linha["id"]),
                "nome": linha["nome"],
                "funcao": linha["funcao"],
                "mundo": linha["mundo"],
            }
            for linha in funcionarios
        ],
        "categorias": [
            {
                "id": str(linha["id"]),
                "nome": linha["nome"],
                "cor": linha["cor"],
                "icone": linha["icone"],
            }
            for linha in categorias
        ],
        "minimo_de_caracteres": MINIMO_DE_CARACTERES,
    }
