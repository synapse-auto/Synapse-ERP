"""D-07 — a subcategoria espelho de cliente e de funcionário.

Cadastrar um cliente cria, na mesma transação, uma subcategoria com o nome dele dentro da
categoria que tem `vinculo = 'cliente'`. Renomear renomeia; arquivar arquiva. O mesmo vale
para funcionário.

## Por que espelho e não uma coisa só

A alternativa seria o lançamento apontar direto para `cliente_id`. Foi descartada em D-07:
o Dashboard, o DRE e o relatório de variação agrupam **por subcategoria**, e ter clientes
fora desse agrupamento obrigaria cada um desses lugares a tratar "Clientes" como caso
especial — que é exatamente o `if nome == 'Clientes'` que `FR-079` proíbe.

Com o espelho, quem agrupa não precisa saber que aquela subcategoria é um cliente. Continua
sendo uma subcategoria.

## O preço, dito em voz alta

Duas linhas para a mesma entidade, que podem divergir. É por isso que **toda** operação
daqui é feita na mesma transação da operação principal, e por isso a checagem
"subcategoria com `cliente_id` só existe em categoria com `vinculo = cliente`" mora neste
módulo: `CHECK` do Postgres não alcança outra tabela (data-model §3.3), e o único gatilho
de regra do projeto está reservado para a imutabilidade de `mundo`.

Tarefa: T102
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada

VINCULO_DE = {"cliente": "cliente_id", "funcionario": "funcionario_id"}


async def categoria_do_vinculo(conexao: AsyncConnection, vinculo: str) -> dict[str, Any]:
    """A categoria especial daquele vínculo. **Resolvida por `vinculo`, nunca por nome.**"""
    linha = (
        (
            await conexao.execute(
                text("""
                    select id, nome, tipo, especial, vinculo
                    from categorias
                    where vinculo = cast(:vinculo as vinculo_subcategoria)
                      and arquivada_em is null
                    order by ordem
                    limit 1
                    """),
                {"vinculo": vinculo},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        quem = "clientes" if vinculo == "cliente" else "funcionários"
        raise ErroRegraViolada(
            (
                f"Não existe categoria de {quem} ativa. Ela é criada no seed do sistema "
                f"e é onde os {quem} viram subcategoria."
            ),
            requisito="D-07",
            campos={"categoria": f"Categoria com vínculo de {quem} ausente."},
        )
    return dict(linha)


async def cria(
    conexao: AsyncConnection, *, vinculo: str, dono_id: UUID, nome: str
) -> dict[str, Any]:
    """Cria a subcategoria espelho. Chamada dentro da transação do cadastro."""
    categoria = await categoria_do_vinculo(conexao, vinculo)
    coluna = VINCULO_DE[vinculo]

    ja_existe = (
        await conexao.execute(
            text(f"select id from subcategorias where {coluna} = :dono and arquivada_em is null"),
            {"dono": str(dono_id)},
        )
    ).scalar_one_or_none()
    if ja_existe is not None:
        return {"id": ja_existe, "categoria_id": categoria["id"], "criada": False}

    nova = (
        await conexao.execute(
            text(f"""
                insert into subcategorias (categoria_id, nome, {coluna})
                values (:categoria, :nome, cast(:dono as uuid))
                returning id
                """),
            {"categoria": str(categoria["id"]), "nome": nome, "dono": str(dono_id)},
        )
    ).scalar_one()
    return {"id": nova, "categoria_id": categoria["id"], "criada": True}


async def renomeia(conexao: AsyncConnection, *, vinculo: str, dono_id: UUID, nome: str) -> None:
    """Renomear o cliente renomeia a subcategoria.

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


async def id_do_dono(conexao: AsyncConnection, *, vinculo: str, dono_id: UUID) -> UUID:
    """A subcategoria espelho de um cliente/funcionário, para filtrar lançamentos."""
    coluna = VINCULO_DE[vinculo]
    achada = (
        await conexao.execute(
            text(f"select id from subcategorias where {coluna} = :dono order by criado_em limit 1"),
            {"dono": str(dono_id)},
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

    onde = "Clientes" if linha["vinculo"] == "cliente" else "Funcionários"
    quem = "cliente" if linha["vinculo"] == "cliente" else "funcionário"
    raise ErroRegraViolada(
        (
            f"Em '{linha['nome']}' as subcategorias vêm do cadastro. Para ter um "
            f"{quem} novo aqui, cadastre-o em {onde} — a subcategoria é criada junto."
        ),
        requisito="RF-055",
        campos={"nome": f"Cadastre o {quem}, não a subcategoria."},
    )
