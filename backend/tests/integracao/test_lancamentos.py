"""Lançamentos contra Postgres real — sub-fase B1.

**Por que contra banco de verdade e não com um dublê**: metade das garantias de B1 é
do banco, não do Python — o gatilho que recusa mudar `mundo` (`RN-15`), a view
`lancamentos_ativos` que esconde o excluído (`RN-08`), o `numeric(14,2)` que não
arredonda como float (`RN-11`) e os SAVEPOINTs que fazem o lote ser tudo-ou-nada
(`FR-021`). Um dublê de banco aprovaria os quatro estando errados.

## Como rodar

    $env:DATABASE_URL_TESTE = "postgresql://...:6543/postgres"   # NUNCA o de produção
    .venv/Scripts/python -m pytest tests/integracao -q

Sem a variável, **pulam com aviso** (conftest) — nunca passam em silêncio. O banco
apontado precisa ter as migrações `001`…`009` aplicadas; os testes criam e apagam só
o que usam, dentro de uma transação desfeita no fim.

Chamam as funções de rota direto, passando a conexão da transação de teste. É de
propósito: subir o `TestClient` abriria uma conexão própria, fora da transação, e o
`rollback` do fim não desfaria nada — o banco de teste acumularia lixo a cada
execução. A camada HTTP (papel, formato de erro, rota) é coberta pelos testes de
contrato.

Tarefas: T067 (gatilho de `mundo`), T068
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.comum.erros import ErroConflitoVersao, ErroNaoEncontrado, ErroRegraViolada
from app.comum.paginacao import Paginacao
from app.dominio import mundo as mod_mundo
from app.lancamentos import repositorio, rotas
from app.lancamentos.esquemas import (
    AcoesEmMassaEntrada,
    DivisaoEntrada,
    LancamentoEdicao,
    LancamentoEntrada,
    LoteEntrada,
)
from app.seguranca.auth import UsuarioAutenticado

pytestmark = pytest.mark.integracao

HOJE = date.today()


# ── Apoio ───────────────────────────────────────────────────────────────────


async def _usuario(conexao) -> UsuarioAutenticado:
    """Um gestor só para esta transação. Some no rollback."""
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, 'Teste de Integração', :email, 'gestor')
            """),
        {"id": str(identificador), "email": f"teste-{identificador.hex[:8]}@synapse.local"},
    )
    return UsuarioAutenticado(
        id=identificador,
        nome="Teste de Integração",
        email="teste@synapse.local",
        papel="gestor",
        preferencias={},
    )


async def _categoria(conexao, nome: str) -> UUID:
    """Categoria do seed `008`. Falha explicando, se o banco de teste não tiver o seed."""
    achada = (
        await conexao.execute(text("select id from categorias where nome = :nome"), {"nome": nome})
    ).scalar_one_or_none()
    if achada is None:
        pytest.fail(
            f"A categoria '{nome}' não existe no banco de teste. Aplique as migrações "
            "001…009, inclusive o seed 008 (quickstart.md §3)."
        )
    return achada


def _entrada(categoria_id: UUID, **sobrescreve) -> LancamentoEntrada:
    corpo = {
        "mundo": "digital",
        "tipo": "despesa",
        "descricao": "Servidor de produção",
        "data": HOJE,
        "valor": Decimal("500.00"),
        "categoria_id": categoria_id,
        "efetivar_automaticamente": True,
    }
    return LancamentoEntrada(**(corpo | sobrescreve))


async def _cria(conexao, usuario, categoria_id, **sobrescreve) -> dict:
    return await rotas.criar(_entrada(categoria_id, **sobrescreve), usuario, conexao)


def _paginacao(por_pagina: int = 50) -> Paginacao:
    """Monta o objeto direto, sem passar por `parametros_de_paginacao`.

    Aquela função é uma **dependência do FastAPI**: chamada fora de uma requisição,
    os defaults dela são objetos `Query(...)`, não números — e `por_pagina` viraria
    `Query` dentro do `LIMIT`.
    """
    return Paginacao(pagina=1, por_pagina=por_pagina, ordenar=None, direcao="desc")


# ── Criar, ler e somar ──────────────────────────────────────────────────────


async def test_criado_aparece_na_lista_e_no_resumo(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    criado = await _cria(conexao_de_teste, usuario, infra, valor=Decimal("500.00"))
    assert criado["status"] == "efetivado"  # data de hoje nasce efetivado (FR-024)
    assert criado["valor"] == "500.00"

    lista = await rotas.listar(
        usuario,
        conexao_de_teste,
        _paginacao(),
        mundo="digital",
        periodo="este_mes",
    )
    ids = [item["id"] for item in lista["itens"]]
    assert criado["id"] in ids
    assert Decimal(lista["resumo_filtrado"]["total_despesas"]) >= Decimal("500.00")


async def test_valor_nao_perde_centavo_no_caminho(conexao_de_teste):
    """`numeric(14,2)`, nunca float — `RN-02` e a razão de dinheiro ir como string."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    criado = await _cria(conexao_de_teste, usuario, infra, valor=Decimal("0.10"))
    outro = await _cria(conexao_de_teste, usuario, infra, valor=Decimal("0.20"))
    assert (Decimal(criado["valor"]) + Decimal(outro["valor"])) == Decimal("0.30")


# ── `RN-15` — mundo obrigatório e imutável (T067) ────────────────────────────


async def test_editar_mudando_o_mundo_e_recusado_com_rn15(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criado = await _cria(conexao_de_teste, usuario, infra, mundo="digital")

    edicao = LancamentoEdicao(
        mundo="infra",
        tipo="despesa",
        descricao="Servidor de produção",
        data=HOJE,
        valor=Decimal("500.00"),
        categoria_id=infra,
        versao=criado["versao"],
    )
    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas.editar(UUID(criado["id"]), edicao, usuario, conexao_de_teste)

    assert capturado.value.requisito == "RN-15"
    assert capturado.value.status == 409


async def test_o_gatilho_do_banco_recusa_mesmo_por_sql_direto(conexao_de_teste):
    """A rede embaixo da regra: o `UPDATE` cru também é recusado.

    A validação em Python protege o caminho da API. Este teste cobre o outro: uma
    correção manual, uma rotina futura, um `UPDATE` numa migração. Sem o gatilho,
    qualquer um deles moveria dinheiro de um mundo para o outro em silêncio — e
    `SC-005` exige zero vazamento.
    """
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criado = await _cria(conexao_de_teste, usuario, infra, mundo="digital")

    ponto = await conexao_de_teste.begin_nested()
    with pytest.raises(DBAPIError) as capturado:
        await conexao_de_teste.execute(
            text("update lancamentos set mundo = 'infra' where id = :id"),
            {"id": criado["id"]},
        )
    await ponto.rollback()

    traduzido = mod_mundo.traduz_erro_do_banco(capturado.value)
    assert traduzido is not None, (
        "O gatilho recusou, mas com outro SQLSTATE. `traduz_erro_do_banco` espera "
        f"{mod_mundo.SQLSTATE_MUNDO_IMUTAVEL} — sem isso o usuário veria texto de Postgres."
    )
    assert traduzido.requisito == "RN-15"


async def test_filtro_de_mundo_nao_deixa_vazar_nada(conexao_de_teste):
    """`SC-005`: nenhum dado de um mundo aparece no outro."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    do_digital = await _cria(conexao_de_teste, usuario, infra, mundo="digital")
    do_infra = await _cria(conexao_de_teste, usuario, infra, mundo="infra")

    so_digital = await rotas.listar(
        usuario, conexao_de_teste, _paginacao(por_pagina=200), mundo="digital"
    )
    ids = {item["id"] for item in so_digital["itens"]}
    assert do_digital["id"] in ids
    assert do_infra["id"] not in ids
    assert all(item["mundo"] == "digital" for item in so_digital["itens"])


async def test_modo_ambos_traz_a_quebra_por_mundo(conexao_de_teste):
    """`FR-003`/`RF-102`: consolidado sempre vem com a quebra."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    await _cria(conexao_de_teste, usuario, infra, mundo="infra")

    consolidado = await rotas.listar(usuario, conexao_de_teste, _paginacao(), mundo="ambos")
    assert set(consolidado["quebra_por_mundo"]) == {"digital", "infra"}


# ── `RN-05` / `RN-16` — saldo ───────────────────────────────────────────────


async def test_saldo_ignora_o_que_nao_esta_efetivado(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    antes = await rotas.obter_saldo(usuario, conexao_de_teste, mundo="digital")

    # Futuro nasce `programado` e NÃO pode entrar no saldo (`RN-05`).
    await _cria(
        conexao_de_teste,
        usuario,
        infra,
        data=HOJE + timedelta(days=30),
        valor=Decimal("999.00"),
        efetivar_automaticamente=False,
    )
    depois = await rotas.obter_saldo(usuario, conexao_de_teste, mundo="digital")
    assert Decimal(depois["saldo"]) == Decimal(antes["saldo"])
    assert depois["sem_saldo_inicial"] is True


# ── `RN-08` — lixeira ───────────────────────────────────────────────────────


async def test_excluido_sai_da_lista_e_volta_pela_lixeira(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criado = await _cria(conexao_de_teste, usuario, infra)
    identificador = UUID(criado["id"])

    await rotas.excluir(identificador, usuario, conexao_de_teste)

    with pytest.raises(ErroNaoEncontrado):
        await rotas.detalhar(identificador, usuario, conexao_de_teste)

    lixeira = await rotas.listar_lixeira(usuario, conexao_de_teste)
    na_lixeira = [item for item in lixeira["itens"] if item["id"] == criado["id"]]
    assert na_lixeira and na_lixeira[0]["pode_restaurar"] is True

    restaurado = await rotas.restaurar(identificador, usuario, conexao_de_teste)
    assert restaurado["id"] == criado["id"]

    # A linha nunca sai do banco — `RN-08`, histórico financeiro é permanente.
    total = (
        await conexao_de_teste.execute(
            text("select count(*) from lancamentos where id = :id"), {"id": criado["id"]}
        )
    ).scalar_one()
    assert total == 1


# ── `RN-11` — split ─────────────────────────────────────────────────────────


async def test_split_com_soma_errada_e_recusado_dizendo_a_diferenca(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    ferramentas = await _categoria(conexao_de_teste, "Ferramentas/Assinaturas")
    criado = await _cria(conexao_de_teste, usuario, infra, valor=Decimal("500.00"))

    divisao = DivisaoEntrada(
        partes=[
            {"descricao": "Parte A", "valor": Decimal("300.00"), "categoria_id": infra},
            {"descricao": "Parte B", "valor": Decimal("180.00"), "categoria_id": ferramentas},
        ]
    )
    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas.dividir(UUID(criado["id"]), divisao, usuario, conexao_de_teste)

    assert capturado.value.requisito == "RN-11"
    assert "20,00" in capturado.value.mensagem  # a diferença que falta fechar


async def test_depois_do_split_o_pai_sai_dos_totais(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    ferramentas = await _categoria(conexao_de_teste, "Ferramentas/Assinaturas")

    saldo_antes = await rotas.obter_saldo(usuario, conexao_de_teste, mundo="digital")
    criado = await _cria(conexao_de_teste, usuario, infra, valor=Decimal("500.00"))

    await rotas.dividir(
        UUID(criado["id"]),
        DivisaoEntrada(
            partes=[
                {"descricao": "Parte A", "valor": Decimal("300.00"), "categoria_id": infra},
                {"descricao": "Parte B", "valor": Decimal("200.00"), "categoria_id": ferramentas},
            ]
        ),
        usuario,
        conexao_de_teste,
    )

    saldo_depois = await rotas.obter_saldo(usuario, conexao_de_teste, mundo="digital")
    # 500 de despesa contados UMA vez: se o pai continuasse somando, seriam 1.000.
    assert Decimal(saldo_antes["saldo"]) - Decimal(saldo_depois["saldo"]) == Decimal("500.00")


# ── Versão (data-model §5.6) ────────────────────────────────────────────────


async def test_editar_com_versao_velha_responde_conflito(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criado = await _cria(conexao_de_teste, usuario, infra)

    corpo = LancamentoEdicao(
        mundo="digital",
        tipo="despesa",
        descricao="Primeira edição",
        data=HOJE,
        valor=Decimal("600.00"),
        categoria_id=infra,
        versao=criado["versao"],
    )
    await rotas.editar(UUID(criado["id"]), corpo, usuario, conexao_de_teste)

    with pytest.raises(ErroConflitoVersao) as capturado:
        await rotas.editar(UUID(criado["id"]), corpo, usuario, conexao_de_teste)
    assert capturado.value.status == 409


# ── T062 — lote é tudo ou nada ──────────────────────────────────────────────


async def test_lote_valido_grava_tudo(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    resposta = await rotas.criar_em_lote(
        LoteEntrada(
            lancamentos=[
                _entrada(infra, descricao="Linha 1"),
                _entrada(infra, descricao="Linha 2"),
                _entrada(infra, descricao="Linha 3"),
            ]
        ),
        usuario,
        conexao_de_teste,
    )
    assert resposta.status_code == 201


async def test_lote_com_linha_invalida_nao_grava_nenhuma(conexao_de_teste):
    """`FR-021`: meio lote gravado numa tabela editável é pior que nenhum."""
    import json

    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    clientes = await _categoria(conexao_de_teste, "Clientes")  # especial: exige subcategoria

    antes = (await conexao_de_teste.execute(text("select count(*) from lancamentos"))).scalar_one()

    resposta = await rotas.criar_em_lote(
        LoteEntrada(
            lancamentos=[
                _entrada(infra, descricao="Boa 1"),
                # Índice 1: categoria especial sem subcategoria → `RN-01`.
                _entrada(clientes, descricao="Ruim", tipo="receita"),
                _entrada(infra, descricao="Boa 2"),
            ]
        ),
        usuario,
        conexao_de_teste,
    )
    corpo = json.loads(bytes(resposta.body))

    assert resposta.status_code == 400
    assert corpo["criados"] == 0
    assert [erro["indice"] for erro in corpo["erros"]] == [1]
    assert corpo["erros"][0]["requisito"] == "RN-01"

    depois = (await conexao_de_teste.execute(text("select count(*) from lancamentos"))).scalar_one()
    assert depois == antes, "O lote foi recusado mas alguma linha ficou gravada."


async def test_lote_reporta_todas_as_linhas_com_problema_de_uma_vez(conexao_de_teste):
    """A tabela editável marca tudo numa passada, em vez de um erro por reenvio."""
    import json

    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    clientes = await _categoria(conexao_de_teste, "Clientes")

    resposta = await rotas.criar_em_lote(
        LoteEntrada(
            lancamentos=[
                _entrada(clientes, descricao="Ruim 1", tipo="receita"),
                _entrada(infra, descricao="Boa"),
                _entrada(clientes, descricao="Ruim 2", tipo="receita"),
            ]
        ),
        usuario,
        conexao_de_teste,
    )
    corpo = json.loads(bytes(resposta.body))
    assert [erro["indice"] for erro in corpo["erros"]] == [0, 2]


# ── T063 — ações em massa ───────────────────────────────────────────────────


async def test_massa_muda_categoria_de_todos(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    ferramentas = await _categoria(conexao_de_teste, "Ferramentas/Assinaturas")

    a = await _cria(conexao_de_teste, usuario, infra)
    b = await _cria(conexao_de_teste, usuario, infra)

    resultado = await rotas.acoes_em_massa(
        AcoesEmMassaEntrada(
            lancamento_ids=[UUID(a["id"]), UUID(b["id"])],
            acao="mudar_categoria",
            parametros={"categoria_id": ferramentas},
        ),
        usuario,
        conexao_de_teste,
    )
    assert resultado["afetados"] == 2

    depois = await rotas.detalhar(UUID(a["id"]), usuario, conexao_de_teste)
    assert depois["categoria"]["nome"] == "Ferramentas/Assinaturas"


async def test_massa_para_categoria_de_outro_tipo_e_recusada(conexao_de_teste):
    """`RN-01`: categoria de receita não recebe despesa — nem em massa."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    clientes = await _categoria(conexao_de_teste, "Clientes")  # tipo `receita`

    despesa = await _cria(conexao_de_teste, usuario, infra)

    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas.acoes_em_massa(
            AcoesEmMassaEntrada(
                lancamento_ids=[UUID(despesa["id"])],
                acao="mudar_categoria",
                parametros={"categoria_id": clientes},
            ),
            usuario,
            conexao_de_teste,
        )
    assert capturado.value.requisito == "RN-01"


async def test_massa_com_id_inexistente_nao_altera_nada(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    ferramentas = await _categoria(conexao_de_teste, "Ferramentas/Assinaturas")
    existente = await _cria(conexao_de_teste, usuario, infra)

    with pytest.raises(ErroNaoEncontrado):
        await rotas.acoes_em_massa(
            AcoesEmMassaEntrada(
                lancamento_ids=[UUID(existente["id"]), uuid4()],
                acao="mudar_categoria",
                parametros={"categoria_id": ferramentas},
            ),
            usuario,
            conexao_de_teste,
        )

    intacto = await rotas.detalhar(UUID(existente["id"]), usuario, conexao_de_teste)
    assert intacto["categoria"]["nome"] == "Infraestrutura"


async def test_massa_cancela_e_o_valor_sai_do_saldo(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criado = await _cria(conexao_de_teste, usuario, infra, valor=Decimal("100.00"))

    antes = await rotas.obter_saldo(usuario, conexao_de_teste, mundo="digital")
    await rotas.acoes_em_massa(
        AcoesEmMassaEntrada(
            lancamento_ids=[UUID(criado["id"])],
            acao="mudar_status",
            parametros={"status": "cancelado"},
        ),
        usuario,
        conexao_de_teste,
    )
    depois = await rotas.obter_saldo(usuario, conexao_de_teste, mundo="digital")
    assert Decimal(depois["saldo"]) - Decimal(antes["saldo"]) == Decimal("100.00")


async def test_massa_adiciona_e_remove_tag(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criado = await _cria(conexao_de_teste, usuario, infra)

    tag = (
        await conexao_de_teste.execute(
            text("insert into tags (nome, cor) values (:nome, '#8B6CF0') returning id"),
            {"nome": f"teste-{uuid4().hex[:6]}"},
        )
    ).scalar_one()

    await rotas.acoes_em_massa(
        AcoesEmMassaEntrada(
            lancamento_ids=[UUID(criado["id"])],
            acao="adicionar_tags",
            parametros={"tag_ids": [tag]},
        ),
        usuario,
        conexao_de_teste,
    )
    com_tag = await rotas.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert [t["id"] for t in com_tag["tags"]] == [str(tag)]

    await rotas.acoes_em_massa(
        AcoesEmMassaEntrada(
            lancamento_ids=[UUID(criado["id"])],
            acao="remover_tags",
            parametros={"tag_ids": [tag]},
        ),
        usuario,
        conexao_de_teste,
    )
    sem_tag = await rotas.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert sem_tag["tags"] == []


# ── T065 — exportação respeita o filtro da tela ─────────────────────────────


async def test_exportacao_traz_so_o_que_o_filtro_traria(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    marca = f"exportacao-{uuid4().hex[:6]}"
    await _cria(conexao_de_teste, usuario, infra, mundo="digital", descricao=marca)
    await _cria(conexao_de_teste, usuario, infra, mundo="infra", descricao=f"{marca}-infra")

    resposta = await rotas.exportar(usuario, conexao_de_teste, mundo="digital", periodo="este_mes")
    texto = resposta.body.decode("utf-8-sig")

    assert resposta.headers["content-disposition"].endswith('.csv"')
    assert marca in texto
    assert f"{marca}-infra" not in texto
    assert "Synapse Infra" not in texto


# ── `RF-013a` — anexo do pai vale para as partes ────────────────────────────


async def test_parte_de_split_herda_a_contagem_de_anexos_do_pai(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    ferramentas = await _categoria(conexao_de_teste, "Ferramentas/Assinaturas")
    pai = await _cria(conexao_de_teste, usuario, infra, valor=Decimal("500.00"))

    await conexao_de_teste.execute(
        text("""
            insert into anexos (
              lancamento_id, nome_arquivo, caminho_storage, mime_type, tamanho_bytes, criado_por
            ) values (
              :lancamento, 'nota.pdf', :caminho, 'application/pdf', 1024, cast(:usuario as uuid)
            )
            """),
        {
            "lancamento": pai["id"],
            "caminho": f"{pai['id']}/{uuid4().hex}-nota.pdf",
            "usuario": str(usuario.id),
        },
    )

    detalhe = await rotas.dividir(
        UUID(pai["id"]),
        DivisaoEntrada(
            partes=[
                {"descricao": "Parte A", "valor": Decimal("300.00"), "categoria_id": infra},
                {"descricao": "Parte B", "valor": Decimal("200.00"), "categoria_id": ferramentas},
            ]
        ),
        usuario,
        conexao_de_teste,
    )

    parte = await repositorio.por_id(conexao_de_teste, UUID(detalhe["partes_split"][0]["id"]))
    assert parte["quantidade_anexos"] == 1, (
        "A parte do split não enxergou o comprovante do pai — `RF-013a` diz que o "
        "anexo fica no pai e as partes leem por herança."
    )
