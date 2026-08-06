"""D-07 — a subcategoria espelho de cliente e de funcionário.

Cadastrar um cliente cria, na mesma transação, uma subcategoria com o nome dele **em cada**
categoria que tem `vinculo = 'cliente'`. Renomear renomeia todas; arquivar arquiva todas. O
mesmo vale para funcionário.

## Por que espelho e não uma coisa só

A alternativa seria o lançamento apontar direto para `cliente_id`. Foi descartada em D-07:
o Dashboard, o DRE e o relatório de variação agrupam **por subcategoria**, e ter clientes
fora desse agrupamento obrigaria cada um desses lugares a tratar "Clientes" como caso
especial — que é exatamente o `if nome == 'Clientes'` que `FR-079` proíbe.

Com o espelho, quem agrupa não precisa saber que aquela subcategoria é um cliente. Continua
sendo uma subcategoria.

## Por que "cada categoria" e não "a categoria" (`RF-58`, 2026-08-05)

Até a migração `015` havia uma categoria por vínculo, garantida por índice único em
`vinculo`. Com o custo operacional por cliente passam a ser **duas**: "Clientes" (receita)
e "Custos Operacionais" (despesa) — e o índice único virou `(vinculo, tipo)`. Quem precisa
de uma só diz **qual lado** quer (`tipo`); quem mantém o espelho em dia opera em todas.

A pergunta "qual é a categoria de receita do cliente?" continua tendo resposta única, que
é o que importa. E continua sendo respondida por `vinculo` + `tipo`, nunca por nome.

## O preço, dito em voz alta

Duas linhas por cliente e por categoria, que podem divergir. É por isso que **toda**
operação daqui é feita na mesma transação da operação principal, e por isso a checagem
"subcategoria com `cliente_id` só existe em categoria com `vinculo = cliente`" mora neste
módulo: `CHECK` do Postgres não alcança outra tabela (data-model §3.3), e o único gatilho
de regra do projeto está reservado para a imutabilidade de `mundo`.

Tarefas: T102, `RF-58`
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada

VINCULO_DE = {"cliente": "cliente_id", "funcionario": "funcionario_id"}

# De onde sai o espelho quando uma categoria é promovida a especial com o vínculo já
# tendo donos cadastrados. Só tabela e coluna — nenhum valor de usuário entra por aqui.
CADASTRO_DE = {
    "cliente": ("clientes", "cliente_id"),
    "funcionario": ("funcionarios", "funcionario_id"),
}

_QUEM = {"cliente": "cliente", "funcionario": "funcionário"}
_QUEM_PLURAL = {"cliente": "clientes", "funcionario": "funcionários"}


async def categorias_do_vinculo(conexao: AsyncConnection, vinculo: str) -> list[dict[str, Any]]:
    """Todas as categorias ativas daquele vínculo — receita e despesa."""
    linhas = (
        (
            await conexao.execute(
                text("""
                    select id, nome, tipo::text as tipo, especial, vinculo::text as vinculo
                    from categorias
                    where vinculo = cast(:vinculo as vinculo_subcategoria)
                      and arquivada_em is null
                    order by ordem
                    """),
                {"vinculo": vinculo},
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


async def categoria_do_vinculo(
    conexao: AsyncConnection, vinculo: str, *, tipo: str
) -> dict[str, Any]:
    """A categoria especial daquele vínculo **daquele lado**.

    **Resolvida por `vinculo` + `tipo`, nunca por nome.** `tipo` é obrigatório desde a
    `015`: sem ele, "a categoria do cliente" passou a ter duas respostas, e escolher a
    primeira por `ordem` mandaria a mensalidade para a categoria de custo em silêncio.
    """
    for categoria in await categorias_do_vinculo(conexao, vinculo):
        if categoria["tipo"] == tipo:
            return categoria

    quem = _QUEM_PLURAL[vinculo]
    lado = "receita" if tipo == "receita" else "despesa"
    raise ErroRegraViolada(
        (
            f"Não existe categoria de {quem} de {lado} ativa. Ela é criada no seed do "
            f"sistema e é onde os {quem} viram subcategoria."
        ),
        requisito="D-07",
        campos={"categoria": f"Categoria com vínculo de {quem} ({lado}) ausente."},
    )


async def cria(
    conexao: AsyncConnection, *, vinculo: str, dono_id: UUID, nome: str, tipo_principal: str
) -> dict[str, Any]:
    """Cria o espelho em **todas** as categorias do vínculo. Uma ida ao banco.

    Chamada dentro da transação do cadastro. Devolve o espelho do lado `tipo_principal`
    em `id` — é ele que a mensalidade (receita) ou a folha (despesa) usa —, e a lista
    inteira em `espelhos`, para quem precisar.

    O `on conflict do nothing` se apoia nos índices únicos `(categoria_id, cliente_id)` e
    `(categoria_id, funcionario_id)` da `015`: repetir a chamada não duplica nada. O
    `union all` existe porque a linha recém-inserida só é visível pelo `returning` do
    próprio comando, e a que já existia só pela leitura da tabela.
    """
    coluna = VINCULO_DE[vinculo]
    linhas = (
        (
            await conexao.execute(
                text(f"""
                    with alvo as (
                      select id, tipo::text as tipo
                      from categorias
                      where vinculo = cast(:vinculo as vinculo_subcategoria)
                        and arquivada_em is null
                    ),
                    inserida as (
                      insert into subcategorias (categoria_id, nome, {coluna})
                      select a.id, :nome, cast(:dono as uuid) from alvo a
                      on conflict do nothing
                      returning id, categoria_id
                    )
                    select i.id, i.categoria_id, a.tipo, true as criada
                      from inserida i join alvo a on a.id = i.categoria_id
                    union all
                    select s.id, s.categoria_id, a.tipo, false as criada
                      from subcategorias s join alvo a on a.id = s.categoria_id
                     where s.{coluna} = cast(:dono as uuid)
                    """),
                {"vinculo": vinculo, "nome": nome, "dono": str(dono_id)},
            )
        )
        .mappings()
        .all()
    )

    espelhos = [dict(linha) for linha in linhas]
    principal = next((item for item in espelhos if item["tipo"] == tipo_principal), None)
    if principal is None:
        # Chegar aqui significa que a categoria daquele lado não existe. A mensagem de
        # negócio é a mesma de `categoria_do_vinculo`, então é ela que responde.
        await categoria_do_vinculo(conexao, vinculo, tipo=tipo_principal)
        raise AssertionError("inalcançável")  # pragma: no cover

    return {
        "id": principal["id"],
        "categoria_id": principal["categoria_id"],
        "criada": principal["criada"],
        "espelhos": espelhos,
    }


async def sincroniza_categoria(
    conexao: AsyncConnection, *, categoria_id: UUID, vinculo: str
) -> int:
    """Preenche os espelhos que faltam numa categoria recém-promovida a especial.

    Promover é ligar `especial` e escolher o `vinculo` (`FR-079`) — mas os clientes já
    cadastrados não voltam ao cadastro para ganhar subcategoria. Sem isto, a categoria
    nasceria vazia e o gestor teria que inventar como povoá-la.

    Espelho de cadastro arquivado nasce arquivado: ele espelha o cadastro, e cliente
    arquivado não pode reaparecer nos formulários pela porta da categoria nova.
    """
    tabela, coluna = CADASTRO_DE[vinculo]
    resultado = await conexao.execute(
        text(f"""
            insert into subcategorias (categoria_id, nome, {coluna}, arquivada_em)
            select cast(:categoria as uuid), d.nome, d.id, d.arquivado_em
              from {tabela} d
            on conflict do nothing
            """),
        {"categoria": str(categoria_id)},
    )
    return resultado.rowcount or 0


async def renomeia(conexao: AsyncConnection, *, vinculo: str, dono_id: UUID, nome: str) -> None:
    """Renomear o cliente renomeia todas as subcategorias espelho dele.

    Sem isto, o Dashboard continuaria mostrando o nome antigo — e ninguém entenderia por
    quê, já que a tela de clientes mostraria o novo.
    """
    coluna = VINCULO_DE[vinculo]
    await conexao.execute(
        text(f"update subcategorias set nome = :nome where {coluna} = :dono"),
        {"nome": nome, "dono": str(dono_id)},
    )


async def arquiva(conexao: AsyncConnection, *, vinculo: str, dono_id: UUID) -> None:
    coluna = VINCULO_DE[vinculo]
    await conexao.execute(
        text(
            f"update subcategorias set arquivada_em = now() "
            f"where {coluna} = :dono and arquivada_em is null"
        ),
        {"dono": str(dono_id)},
    )


async def desarquiva(conexao: AsyncConnection, *, vinculo: str, dono_id: UUID) -> None:
    coluna = VINCULO_DE[vinculo]
    await conexao.execute(
        text(f"update subcategorias set arquivada_em = null where {coluna} = :dono"),
        {"dono": str(dono_id)},
    )


async def id_do_dono(conexao: AsyncConnection, *, vinculo: str, dono_id: UUID, tipo: str) -> UUID:
    """A subcategoria espelho de um cliente/funcionário **de um lado**, para filtrar.

    `tipo` deixou de ser opcional pelo mesmo motivo de `categoria_do_vinculo`: com duas
    categorias por vínculo, "a subcategoria do cliente" não é mais uma pergunta com uma
    resposta.
    """
    coluna = VINCULO_DE[vinculo]
    achada = (
        await conexao.execute(
            text(f"""
                select s.id from subcategorias s
                join categorias c on c.id = s.categoria_id
                where s.{coluna} = :dono and c.tipo = cast(:tipo as tipo_categoria)
                order by s.criado_em limit 1
                """),
            {"dono": str(dono_id), "tipo": tipo},
        )
    ).scalar_one_or_none()
    if achada is None:
        raise ErroNaoEncontrado(
            "Este cadastro não tem subcategoria vinculada — o espelho não foi criado."
        )
    return achada


async def recusa_criacao_manual(conexao: AsyncConnection, categoria_id: UUID) -> None:
    """Criar subcategoria à mão em categoria com `vinculo` é recusado (`RF-055`).

    A subcategoria ali **nasce** do cadastro do cliente ou do funcionário. Deixar criar
    à mão produziria uma linha sem dono, que apareceria nos relatórios como se fosse um
    cliente e não teria perfil, nem cobrança, nem inadimplência.
    """
    linha = (
        (
            await conexao.execute(
                text("select nome, vinculo from categorias where id = :id"),
                {"id": str(categoria_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None or linha["vinculo"] is None:
        return

    quem = _QUEM[linha["vinculo"]]
    onde = _QUEM_PLURAL[linha["vinculo"]].capitalize()
    raise ErroRegraViolada(
        (
            f"Em '{linha['nome']}' as subcategorias vêm do cadastro. Para ter um "
            f"{quem} novo aqui, cadastre-o em {onde} — a subcategoria é criada junto."
        ),
        requisito="RF-055",
        campos={"nome": f"Cadastre o {quem}, não a subcategoria."},
    )
