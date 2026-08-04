"""Busca global — contracts/consultas.md §4. `FR-046`.

Skill `supabase-postgres-best-practices` acionada antes de escrever (task 🟢 T132).

**Usa `pg_trgm` com `%` (similaridade), não `ilike '%texto%'`.** O `%` usa o índice GIN
que a migração `004` criou; o `ilike` com curinga na frente varreria a tabela inteira a
cada tecla digitada — e esta busca é chamada enquanto o usuário digita.

**Mínimo de 2 caracteres.** Abaixo disso devolve listas vazias em vez de varrer a base:
uma letra casa com quase tudo, e o resultado seria inútil e caro ao mesmo tempo.

Lançamentos e funcionários respeitam o mundo ativo; clientes e categorias não têm mundo
(`RF-101`, D-04).

**As quatro famílias saem de uma consulta só, por `union all`.** Eram quatro idas ao
banco em série, uma esperando a outra, num endereço que é chamado a cada tecla
digitada: o que mandava no tempo de resposta não era o trabalho do Postgres (0,1 ms
por família) e sim as quatro viagens de rede. Cada ramo do `union all` mantém o
próprio `order by` e o próprio `limit`, então o resultado é o mesmo — a diferença é o
número de viagens. `row_number()` carrega a ordem de cada ramo para fora, porque
`union all` não promete preservar ordem de entrada.

Tarefas: T132, T212 (funcionários entram na busca — Boss 4)
"""

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

# ── Os quatro ramos do `union all` ──────────────────────────────────────────
#
# Cada ramo já monta o objeto que vai para a tela, com `jsonb_build_object`. Dinheiro
# e data saem como texto direto do Postgres (`::text` em `numeric(14,2)` devolve
# `"1234.56"`; em `date`, o ISO 8601 que o contrato pede), então não sobra formatação
# para o Python fazer — o que também evita a conversão para `Decimal` e de volta.
#
# O nome da família é fixo em cada ramo e o `order by familia, posicao` no fim ordena
# por ele; por isso os nomes seguem a ordem alfabética que a tela espera
# (categoria < cliente < funcionario < lancamento não importa: o agrupamento é por
# chave no Python, e a ordem que importa é a `posicao` dentro de cada família).

_RAMO_LANCAMENTOS = """
select 'lancamentos' as familia, row_number() over () as posicao,
       jsonb_build_object(
         'id', t.id::text, 'descricao', t.descricao, 'valor', t.valor::text,
         'data', t.data::text, 'mundo', t.mundo, 'tipo', t.tipo,
         'status', t.status, 'categoria', t.categoria_nome
       ) as item
from (
  select l.id, l.descricao, l.valor, l.data, l.mundo, l.tipo, l.status,
         c.nome as categoria_nome
  from lancamentos_ativos l
  join categorias c on c.id = l.categoria_id
  where l.mundo = any(cast(:mundos as mundo[]))
    and l.descricao % :termo
  order by similarity(l.descricao, :termo) desc, l.data desc
  limit :limite
) t
"""

_RAMO_CLIENTES = """
select 'clientes', row_number() over (),
       jsonb_build_object('id', t.id::text, 'nome', t.nome, 'empresa', t.empresa)
from (
  select id, nome, empresa
  from clientes
  where arquivado_em is null
    and (nome % :termo or coalesce(empresa, '') % :termo)
  order by similarity(nome, :termo) desc
  limit :limite
) t
"""

# Funcionário tem mundo (`RN-15`), então segue o mundo ativo como o lançamento.
# Busca por nome **e por função**: quem procura "designer" quer a pessoa, não
# precisa lembrar o nome dela.
_RAMO_FUNCIONARIOS = """
select 'funcionarios', row_number() over (),
       jsonb_build_object('id', t.id::text, 'nome', t.nome,
                          'funcao', t.funcao, 'mundo', t.mundo)
from (
  select id, nome, funcao, mundo
  from funcionarios
  where arquivado_em is null
    and mundo = any(cast(:mundos as mundo[]))
    and (nome % :termo or funcao % :termo)
  order by greatest(similarity(nome, :termo), similarity(funcao, :termo)) desc
  limit :limite
) t
"""

_RAMO_CATEGORIAS = """
select 'categorias', row_number() over (),
       jsonb_build_object('id', t.id::text, 'nome', t.nome,
                          'cor', t.cor, 'icone', t.icone)
from (
  select id, nome, cor, icone
  from categorias
  where arquivada_em is null and nome % :termo
  order by similarity(nome, :termo) desc
  limit :limite
) t
"""


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

    linhas = (
        await conexao.execute(
            text(f"""
                {_RAMO_LANCAMENTOS}
                union all
                {_RAMO_CLIENTES}
                union all
                {_RAMO_FUNCIONARIOS}
                union all
                {_RAMO_CATEGORIAS}
                order by familia, posicao
                """),
            {"mundos": mundos, "termo": termo, "limite": limite},
        )
    ).all()

    achados: dict[str, list[dict[str, Any]]] = {
        "lancamentos": [],
        "clientes": [],
        "funcionarios": [],
        "categorias": [],
    }
    for familia, _posicao, item in linhas:
        achados[familia].append(item)

    return {"termo": termo, **achados, "minimo_de_caracteres": MINIMO_DE_CARACTERES}
