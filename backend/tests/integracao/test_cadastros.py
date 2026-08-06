"""Clientes, funcionários e categorias contra Postgres real — sub-fase B4.

**O que só o banco prova**: que as três escritas do cadastro de cliente acontecem na
mesma transação (D-07) e que nenhuma delas fica pela metade. E que o filtro de mundo
derivado — a consequência de `clientes` não ter `mundo` (D-04) — devolve o conjunto certo,
inclusive o cliente sem lançamento nenhum, que é o caso que some sozinho se o `exists` for
escrito errado.

    .venv/Scripts/python -m pytest tests/integracao -q

⚠️ Rodam contra o banco de **produção**; a transação desfeita do `conftest` é o
que protege os dados. Ver o aviso no topo de `tests/conftest.py`.

Tarefa: T112
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.cadastros import centros_custo as rotas_centros
from app.cadastros import servicos as rotas_servicos
from app.categorias import rotas as rotas_categorias
from app.clientes import rotas as rotas_clientes
from app.comum.erros import ErroConfirmacaoNecessaria, ErroNaoEncontrado, ErroRegraViolada
from app.comum.paginacao import Paginacao
from app.funcionarios import rotas as rotas_funcionarios
from app.seguranca.auth import UsuarioAutenticado

pytestmark = pytest.mark.integracao

HOJE = date.today()


async def _usuario(conexao) -> UsuarioAutenticado:
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, 'Teste B4', :email, 'gestor')
            """),
        {"id": str(identificador), "email": f"b4-{identificador.hex[:8]}@synapse.local"},
    )
    return UsuarioAutenticado(
        id=identificador, nome="Teste B4", email="b4@synapse.local", papel="gestor", preferencias={}
    )


def _paginacao(por_pagina: int = 50) -> Paginacao:
    return Paginacao(pagina=1, por_pagina=por_pagina, ordenar=None, direcao="desc")


def _cliente(nome: str | None = None, **sobrescreve) -> rotas_clientes.ClienteEntrada:
    corpo = {
        "nome": nome or f"Cliente {uuid4().hex[:6]}",
        "tipo_cobranca": "pontual",
    }
    return rotas_clientes.ClienteEntrada(**(corpo | sobrescreve))


def _recorrente(nome: str | None = None, **sobrescreve) -> rotas_clientes.ClienteEntrada:
    return _cliente(
        nome,
        **{
            "tipo_cobranca": "recorrente",
            "valor_recorrente": Decimal("2000.00"),
            "dia_cobranca": 10,
            "mundo_cobranca": "digital",
            **sobrescreve,
        },
    )


# ── Cadastro de cliente: as três escritas juntas (D-07, FR-082) ─────────────


async def test_cadastrar_cliente_cria_a_subcategoria_espelho(conexao_de_teste):
    """O nome é sorteado de propósito.

    Era fixo em "Estrutural Vidros" e passou a falhar em 2026-08-04, quando um cliente
    real com esse nome entrou na base: `clientes_nome_ativos_uidx` recusa o segundo, e o
    teste morria em `IntegrityError` sem ter nada a ver com o que ele mede. Todo teste
    daqui cria o que precisa (`conftest`, "regra para teste novo") — este era a exceção.
    """
    usuario = await _usuario(conexao_de_teste)
    nome = f"Estrutural Vidros {uuid4().hex[:6]}"
    criado = await rotas_clientes.criar(_cliente(nome), usuario, conexao_de_teste)

    espelho = (
        (
            await conexao_de_teste.execute(
                text("""
                    select s.id, s.nome, c.vinculo
                    from subcategorias s join categorias c on c.id = s.categoria_id
                    where s.cliente_id = :cliente
                    """),
                {"cliente": criado["id"]},
            )
        )
        .mappings()
        .first()
    )
    assert espelho is not None, "O cliente nasceu sem subcategoria — D-07 quebrado."
    assert espelho["nome"] == nome
    assert espelho["vinculo"] == "cliente"


async def _espelho_do_cliente(conexao, cliente_id, *, tipo: str = "receita") -> dict:
    """O espelho do cliente **de um lado** (`RF-58`).

    Desde a migração `015` o cliente tem dois: um em "Clientes" (receita) e um em
    "Custos Operacionais" (despesa). Todo teste que precisa "da subcategoria do
    cliente" precisa dizer qual — e é por `categorias.tipo`, nunca por nome.
    """
    return dict(
        (
            await conexao.execute(
                text("""
                    select s.id, s.categoria_id, s.nome, s.arquivada_em
                    from subcategorias s join categorias c on c.id = s.categoria_id
                    where s.cliente_id = :cliente and c.tipo = cast(:tipo as tipo_categoria)
                    """),
                {"cliente": str(cliente_id), "tipo": tipo},
            )
        )
        .mappings()
        .one()
    )


async def test_cadastrar_cliente_cria_espelho_dos_dois_lados(conexao_de_teste):
    """`RF-58`: o cliente nasce em Clientes (receita) **e** em Custos Operacionais.

    É o que faz o custo operacional poder apontar para um cliente sem que ninguém
    compare nome de categoria em lugar nenhum.
    """
    usuario = await _usuario(conexao_de_teste)
    nome = f"Dois Lados {uuid4().hex[:6]}"
    criado = await rotas_clientes.criar(_cliente(nome), usuario, conexao_de_teste)

    lados = (
        (
            await conexao_de_teste.execute(
                text("""
                    select c.tipo::text as tipo, s.nome
                    from subcategorias s join categorias c on c.id = s.categoria_id
                    where s.cliente_id = :cliente and c.vinculo = 'cliente'
                    """),
                {"cliente": criado["id"]},
            )
        )
        .mappings()
        .all()
    )
    assert {linha["tipo"] for linha in lados} == {"receita", "despesa"}
    assert {linha["nome"] for linha in lados} == {nome}


async def test_cliente_recorrente_ganha_a_recorrencia_da_mensalidade(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_recorrente(), usuario, conexao_de_teste)

    assert criado["recorrencia"] is not None
    assert criado["recorrencia"]["rotulo"] == "Mensal, dia 10"
    assert criado["recorrencia"]["geracao"]["geradas"] > 0

    mundo = (
        await conexao_de_teste.execute(
            text("select mundo from recorrencias where id = :id"),
            {"id": criado["recorrencia"]["id"]},
        )
    ).scalar_one()
    assert mundo == "digital"  # o `mundo_cobranca`, não o do cliente (que não existe)


async def test_mensalidade_nasce_com_efetivacao_manual_por_padrao(conexao_de_teste):
    """D-05 — e é o que faz o alerta de inadimplência existir."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_recorrente(), usuario, conexao_de_teste)

    assert criado["recorrencia"]["efetivar_automaticamente"] is False
    assert "gera alerta de inadimplência" in criado["recorrencia"]["aviso_inadimplencia"]


async def test_com_efetivacao_automatica_a_resposta_avisa_a_consequencia(conexao_de_teste):
    """A tela precisa poder explicar por que esse cliente nunca vai cobrar."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(
        _recorrente(efetivar_automaticamente=True), usuario, conexao_de_teste
    )
    assert "nunca vai aparecer como inadimplente" in criado["recorrencia"]["aviso_inadimplencia"]


async def test_recorrente_sem_os_tres_campos_e_recusado_no_corpo(conexao_de_teste):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        rotas_clientes.ClienteEntrada(nome="Falho", tipo_cobranca="recorrente")


# ── Filtro de mundo derivado (D-04) ────────────────────────────────────────


async def test_cliente_sem_lancamento_aparece_nos_tres_estados_do_seletor(conexao_de_teste):
    """O caso que some sozinho se o `exists` for escrito errado."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente("Sem Movimento"), usuario, conexao_de_teste)

    for mundo in ("digital", "infra", "ambos"):
        lista = await rotas_clientes.listar(usuario, conexao_de_teste, _paginacao(200), mundo=mundo)
        achado = [item for item in lista["itens"] if item["id"] == criado["id"]]
        assert achado, f"O cliente sem movimentação sumiu no modo {mundo}."
        assert achado[0]["sem_movimentacao"] is True


async def test_cliente_com_movimentacao_so_aparece_no_mundo_em_que_movimentou(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente("Só Digital"), usuario, conexao_de_teste)

    espelho = await _espelho_do_cliente(conexao_de_teste, criado["id"])
    subcategoria, categoria = espelho["id"], espelho["categoria_id"]

    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id, subcategoria_id,
              efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
            ) values (
              'digital', 'receita', 'mensalidade', 2000.00, :data, 'efetivado',
              :cat, :sub, false, now(), cast(:u as uuid), cast(:u as uuid)
            )
            """),
        {
            "data": HOJE,
            "cat": str(categoria),
            "sub": str(subcategoria),
            "u": str(usuario.id),
        },
    )

    no_digital = await rotas_clientes.listar(
        usuario, conexao_de_teste, _paginacao(200), mundo="digital"
    )
    no_infra = await rotas_clientes.listar(
        usuario, conexao_de_teste, _paginacao(200), mundo="infra"
    )

    assert criado["id"] in {i["id"] for i in no_digital["itens"]}
    assert criado["id"] not in {i["id"] for i in no_infra["itens"]}


# ── Inadimplência derivada (`RN-10`) ───────────────────────────────────────


async def _cria_receita_vencida(conexao, usuario, cliente_id, *, dias, automatico=False):
    subcategoria = await _espelho_do_cliente(conexao, cliente_id)
    await conexao.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id, subcategoria_id,
              efetivar_automaticamente, criado_por
            ) values (
              'digital', 'receita', 'mensalidade vencida', 2000.00, :data, 'atrasado',
              :cat, :sub, :auto, cast(:u as uuid)
            )
            """),
        {
            "data": HOJE - timedelta(days=dias),
            "cat": str(subcategoria["categoria_id"]),
            "sub": str(subcategoria["id"]),
            "auto": automatico,
            "u": str(usuario.id),
        },
    )


async def test_cliente_com_atraso_alem_da_tolerancia_aparece_marcado(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente("Devedor"), usuario, conexao_de_teste)
    await _cria_receita_vencida(conexao_de_teste, usuario, criado["id"], dias=8)

    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert perfil["situacao"] == "atrasado"
    assert perfil["dias_atraso"] == 8
    assert Decimal(perfil["valor_atrasado"]) == Decimal("2000.00")


async def test_atraso_com_efetivacao_automatica_nao_marca_o_cliente(conexao_de_teste):
    """D-05, ponta a ponta: o sistema vai efetivar sozinho, não há o que cobrar."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente("Automático"), usuario, conexao_de_teste)
    await _cria_receita_vencida(conexao_de_teste, usuario, criado["id"], dias=90, automatico=True)

    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert perfil["situacao"] == "em_dia"


async def test_inadimplentes_vem_no_topo_da_lista(conexao_de_teste):
    """`FR-083`."""
    usuario = await _usuario(conexao_de_teste)
    await rotas_clientes.criar(_cliente("AAA Em dia"), usuario, conexao_de_teste)
    devedor = await rotas_clientes.criar(_cliente("ZZZ Devedor"), usuario, conexao_de_teste)
    await _cria_receita_vencida(conexao_de_teste, usuario, devedor["id"], dias=20)

    lista = await rotas_clientes.listar(usuario, conexao_de_teste, _paginacao(200))
    assert lista["itens"][0]["id"] == devedor["id"], (
        "O inadimplente não ficou no topo — a ordenação alfabética venceu a situação."
    )


# ── Renomear e arquivar mantêm o espelho em dia ────────────────────────────


async def test_renomear_o_cliente_renomeia_a_subcategoria(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente("Nome Velho"), usuario, conexao_de_teste)

    await rotas_clientes.editar(
        UUID(criado["id"]), _cliente("Nome Novo"), usuario, conexao_de_teste
    )
    # Os **dois** espelhos (`RF-58`): o de receita e o de custo. Renomear um só faria
    # o Dashboard mostrar dois nomes para o mesmo cliente.
    nomes = (
        (
            await conexao_de_teste.execute(
                text("select nome from subcategorias where cliente_id = :c"), {"c": criado["id"]}
            )
        )
        .scalars()
        .all()
    )
    assert len(nomes) == 2
    assert set(nomes) == {"Nome Novo"}, "O Dashboard continuaria mostrando o nome antigo."


async def test_arquivar_cliente_desliga_a_cobranca_e_diz_quantas_saiu(conexao_de_teste):
    """`FR-084` e o *edge case* "desligado com lançamentos futuros programados"."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_recorrente(), usuario, conexao_de_teste)

    resposta = await rotas_clientes.arquivar(
        UUID(criado["id"]), rotas_clientes.ArquivarEntrada(), usuario, conexao_de_teste
    )
    assert resposta["arquivado_em"] is not None
    assert resposta["ocorrencias_futuras_removidas"] > 0

    ativa = (
        await conexao_de_teste.execute(
            text("select ativa from recorrencias where cliente_id = :c"), {"c": criado["id"]}
        )
    ).scalar_one()
    assert ativa is False

    arquivadas = (
        (
            await conexao_de_teste.execute(
                text("select arquivada_em from subcategorias where cliente_id = :c"),
                {"c": criado["id"]},
            )
        )
        .scalars()
        .all()
    )
    assert len(arquivadas) == 2
    assert all(data is not None for data in arquivadas)


async def test_arquivar_preserva_o_que_ja_foi_recebido(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_recorrente(), usuario, conexao_de_teste)

    efetivados_antes = (
        await conexao_de_teste.execute(
            text("""
                select count(*) from lancamentos l
                join subcategorias s on s.id = l.subcategoria_id
                where s.cliente_id = :c and l.status = 'efetivado' and l.excluido_em is null
                """),
            {"c": criado["id"]},
        )
    ).scalar_one()

    await rotas_clientes.arquivar(
        UUID(criado["id"]), rotas_clientes.ArquivarEntrada(), usuario, conexao_de_teste
    )

    efetivados_depois = (
        await conexao_de_teste.execute(
            text("""
                select count(*) from lancamentos l
                join subcategorias s on s.id = l.subcategoria_id
                where s.cliente_id = :c and l.status = 'efetivado' and l.excluido_em is null
                """),
            {"c": criado["id"]},
        )
    ).scalar_one()
    assert efetivados_depois == efetivados_antes


# ── Funcionários (`RN-15` — aqui tem mundo) ────────────────────────────────


def _funcionario(**sobrescreve) -> rotas_funcionarios.FuncionarioEntrada:
    corpo = {
        "nome": f"Func {uuid4().hex[:6]}",
        "funcao": "Automação",
        "tipo_contratacao": "pj",
        "valor_mensal": Decimal("1200.00"),
        "dia_pagamento": 5,
        "mundo": "digital",
    }
    return rotas_funcionarios.FuncionarioEntrada(**(corpo | sobrescreve))


async def test_cadastrar_funcionario_cria_espelho_e_folha(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_funcionarios.criar(_funcionario(), usuario, conexao_de_teste)

    assert criado["subcategoria_id"]
    assert criado["recorrencia"]["rotulo"] == "Mensal, dia 5"
    assert criado["recorrencia"]["geracao"]["geradas"] > 0


async def test_mudar_o_mundo_do_funcionario_e_recusado(conexao_de_teste):
    """`RN-15` — a diferença de modelagem em relação a cliente."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_funcionarios.criar(_funcionario(), usuario, conexao_de_teste)

    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas_funcionarios.editar(
            UUID(criado["id"]),
            _funcionario(nome=criado["nome"], mundo="infra"),
            usuario,
            conexao_de_teste,
        )
    assert capturado.value.requisito == "RN-15"


async def test_bonus_avulso_soma_ao_custo_do_funcionario(conexao_de_teste):
    """`FR-088`: é um lançamento na mesma subcategoria — sem campo nem endpoint novo."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_funcionarios.criar(_funcionario(), usuario, conexao_de_teste)

    subcategoria = (
        (
            await conexao_de_teste.execute(
                text("select id, categoria_id from subcategorias where funcionario_id = :f"),
                {"f": criado["id"]},
            )
        )
        .mappings()
        .one()
    )
    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id, subcategoria_id,
              efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
            ) values (
              'digital', 'despesa', 'Bônus de projeto', 500.00, :data, 'efetivado',
              :cat, :sub, true, now(), cast(:u as uuid), cast(:u as uuid)
            )
            """),
        {
            "data": HOJE,
            "cat": str(subcategoria["categoria_id"]),
            "sub": str(subcategoria["id"]),
            "u": str(usuario.id),
        },
    )

    perfil = await rotas_funcionarios.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    avulsos = [p for p in perfil["pagamentos"] if not p["da_folha"]]
    assert avulsos, "O bônus não apareceu no perfil."
    assert Decimal(perfil["custo_historico"]) >= Decimal("500.00")


async def test_desarquivar_funcionario_traz_de_volta_sem_religar_a_folha(conexao_de_teste):
    """`RN-06` — arquivar não pode ser caminho sem volta, já que `DELETE` não existe.

    O endpoint faltava até 2026-08-03: o cabeçalho de contracts/cadastros.md promete o
    par `arquivar`/`desarquivar` para todo cadastro e só categorias e clientes tinham.

    A folha **não** volta junto, de propósito e igual ao cliente: as ocorrências futuras
    foram removidas ao arquivar, e recriá-las sozinho reativaria um pagamento mensal que
    alguém desligou.
    """
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_funcionarios.criar(_funcionario(), usuario, conexao_de_teste)
    identificador = UUID(criado["id"])

    await rotas_funcionarios.arquivar(identificador, usuario, conexao_de_teste)
    espelho_arquivado = (
        await conexao_de_teste.execute(
            text("select arquivada_em from subcategorias where funcionario_id = :f"),
            {"f": criado["id"]},
        )
    ).scalar_one()
    assert espelho_arquivado is not None

    voltou = await rotas_funcionarios.desarquivar(identificador, usuario, conexao_de_teste)
    assert voltou["arquivado_em"] is None
    assert "folha" in voltou["aviso_folha"].lower()

    espelho_ativo = (
        await conexao_de_teste.execute(
            text("select arquivada_em from subcategorias where funcionario_id = :f"),
            {"f": criado["id"]},
        )
    ).scalar_one()
    assert espelho_ativo is None, "A subcategoria espelho ficou arquivada."

    # A folha continua desativada — é a metade que o gestor precisa pedir de novo.
    ativa = (
        await conexao_de_teste.execute(
            text("select ativa from recorrencias where funcionario_id = :f"),
            {"f": criado["id"]},
        )
    ).scalar_one()
    assert ativa is False

    with pytest.raises(ErroRegraViolada):
        await rotas_funcionarios.desarquivar(identificador, usuario, conexao_de_teste)


# ── Categorias (`RN-06`) ───────────────────────────────────────────────────


async def test_arquivar_categoria_com_lancamentos_pede_escolha(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    categoria = (
        await conexao_de_teste.execute(
            text("select id from categorias where nome = 'Infraestrutura'")
        )
    ).scalar_one()

    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id,
              efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
            ) values (
              'digital', 'despesa', 'servidor', 500.00, :data, 'efetivado', :cat,
              true, now(), cast(:u as uuid), cast(:u as uuid)
            )
            """),
        {"data": HOJE, "cat": str(categoria), "u": str(usuario.id)},
    )

    with pytest.raises(ErroConfirmacaoNecessaria) as capturado:
        await rotas_categorias.arquivar(
            categoria,
            rotas_categorias.ArquivarCategoriaEntrada(),
            usuario,
            conexao_de_teste,
        )
    assert capturado.value.requisito == "RN-06"
    assert capturado.value.extra["previa"]["quantidade_lancamentos"] >= 1


async def test_arquivar_movendo_leva_os_lancamentos_junto(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    origem = (
        await conexao_de_teste.execute(text("select id from categorias where nome = 'Marketing'"))
    ).scalar_one()
    destino = (
        await conexao_de_teste.execute(text("select id from categorias where nome = 'Outros'"))
    ).scalar_one()

    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id,
              efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
            ) values (
              'digital', 'despesa', 'anúncio', 300.00, :data, 'efetivado', :cat,
              true, now(), cast(:u as uuid), cast(:u as uuid)
            )
            """),
        {"data": HOJE, "cat": str(origem), "u": str(usuario.id)},
    )

    resposta = await rotas_categorias.arquivar(
        origem,
        rotas_categorias.ArquivarCategoriaEntrada(destino_lancamentos=destino),
        usuario,
        conexao_de_teste,
    )
    assert resposta["lancamentos_movidos"] >= 1

    sobraram = (
        await conexao_de_teste.execute(
            text("select count(*) from lancamentos_ativos where categoria_id = :c"),
            {"c": str(origem)},
        )
    ).scalar_one()
    assert sobraram == 0, "Ficou lançamento na categoria arquivada — RN-06 quebrado."


async def test_categoria_especial_nao_se_arquiva(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    clientes = (
        await conexao_de_teste.execute(
            text("select id from categorias where vinculo = 'cliente' limit 1")
        )
    ).scalar_one()

    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas_categorias.arquivar(
            clientes, rotas_categorias.ArquivarCategoriaEntrada(), usuario, conexao_de_teste
        )
    assert "Arquive os clientes" in capturado.value.mensagem


async def test_criar_subcategoria_a_mao_em_categoria_especial_e_recusado(conexao_de_teste):
    """`RF-055`: ali a subcategoria nasce do cadastro (D-07)."""
    usuario = await _usuario(conexao_de_teste)
    clientes = (
        await conexao_de_teste.execute(
            text("select id from categorias where vinculo = 'cliente' limit 1")
        )
    ).scalar_one()

    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas_categorias.criar_subcategoria(
            clientes,
            rotas_categorias.SubcategoriaEntrada(nome="Cliente à mão"),
            usuario,
            conexao_de_teste,
        )
    assert capturado.value.requisito == "RF-055"
    # A mensagem tem que dizer ONDE cadastrar, não só recusar.
    assert "cadastre-o em Clientes" in capturado.value.mensagem


async def test_promover_para_vinculo_ja_ocupado_e_recusado_dizendo_quem_ocupa(conexao_de_teste):
    """`FR-079` tem um limite: **um** vínculo, **uma** categoria.

    O índice `categorias_vinculo_uidx` garante isso, e tem que garantir —
    `dominio/espelho_subcategoria.py` precisa saber em qual categoria criar a
    subcategoria quando um cliente é cadastrado, e com duas a pergunta não tem resposta.

    O que este teste protege é a **mensagem**: antes da auditoria de 2026-07-31 o
    `update` batia direto no índice e o usuário recebia `500 erro_interno`, com a
    explicação só no log.
    """
    usuario = await _usuario(conexao_de_teste)
    nova = await rotas_categorias.criar(
        rotas_categorias.CategoriaEntrada(
            nome=f"Parceiros {uuid4().hex[:6]}",
            cor="#8B6CF0",
            icone="users",
            tipo="receita",
        ),
        usuario,
        conexao_de_teste,
    )

    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas_categorias.editar(
            UUID(nova["id"]),
            rotas_categorias.CategoriaEntrada(
                nome=nova["nome"],
                cor="#8B6CF0",
                icone="users",
                tipo="receita",
                especial=True,
                vinculo="cliente",  # já é da categoria "Clientes", vinda do seed
            ),
            usuario,
            conexao_de_teste,
        )

    assert capturado.value.requisito == "FR-079"
    # Precisa dizer **quem** ocupa — é a informação que resolve.
    assert "Clientes" in capturado.value.mensagem
    assert "vinculo" in capturado.value.campos


async def test_promover_categoria_a_especial_aponta_as_subcategorias_sem_dono(conexao_de_teste):
    """`FR-079`: promover é gravar `especial` e `vinculo`, sem deploy.

    ⚠️ **Único teste que altera uma linha do seed** — e por isso a exceção está escrita
    aqui. Como só pode existir uma categoria por vínculo (teste acima), provar que a
    promoção funciona exige o vínculo livre, e os dois nascem ocupados pelo seed. A
    alternativa seria não cobrir a promoção, que é o coração de `FR-079`.

    A regra do `conftest` continua valendo para o resto: nada é apagado, o arquivamento
    é desfeito no `rollback` como todo o resto, e a janela é de segundos.
    """
    usuario = await _usuario(conexao_de_teste)

    await conexao_de_teste.execute(
        text(
            "update categorias set arquivada_em = now() "
            "where vinculo = 'cliente' and arquivada_em is null"
        )
    )

    nova = await rotas_categorias.criar(
        rotas_categorias.CategoriaEntrada(
            nome=f"Parceiros {uuid4().hex[:6]}",
            cor="#8B6CF0",
            icone="users",
            tipo="receita",
        ),
        usuario,
        conexao_de_teste,
    )
    await rotas_categorias.criar_subcategoria(
        UUID(nova["id"]),
        rotas_categorias.SubcategoriaEntrada(nome="Antiga sem dono"),
        usuario,
        conexao_de_teste,
    )

    promovida = await rotas_categorias.editar(
        UUID(nova["id"]),
        rotas_categorias.CategoriaEntrada(
            nome=nova["nome"],
            cor="#8B6CF0",
            icone="users",
            tipo="receita",
            especial=True,
            vinculo="cliente",
        ),
        usuario,
        conexao_de_teste,
    )
    assert promovida["especial"] is True
    nomes = [item["nome"] for item in promovida["subcategorias_pendentes_de_vinculo"]]
    assert "Antiga sem dono" in nomes


# ── Serviços e centros de custo: o par arquivar/desarquivar ────────────────
#
# Os dois endpoints de volta entraram em 2026-08-03, na auditoria de requisitos. Sem
# eles, desativar o serviço ou o centro errado não tinha correção pela API — e `DELETE`
# não existe aqui de propósito (`RN-06`).


async def test_desarquivar_servico_devolve_ele_a_lista(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_servicos.criar(
        rotas_servicos.ServicoEntrada(nome=f"Serviço {uuid4().hex[:6]}", mundo="infra"),
        usuario,
        conexao_de_teste,
    )
    identificador = UUID(criado["id"])

    arquivado = await rotas_servicos.arquivar(identificador, usuario, conexao_de_teste)
    assert arquivado["ativo"] is False
    listagem = await rotas_servicos.listar(usuario, conexao_de_teste, mundo="infra")
    assert criado["id"] not in [item["id"] for item in listagem["itens"]]

    voltou = await rotas_servicos.desarquivar(identificador, usuario, conexao_de_teste)
    assert voltou["ativo"] is True
    listagem = await rotas_servicos.listar(usuario, conexao_de_teste, mundo="infra")
    assert criado["id"] in [item["id"] for item in listagem["itens"]]

    # Segunda chamada não tem o que fazer — e diz isso, em vez de fingir sucesso.
    with pytest.raises(ErroNaoEncontrado):
        await rotas_servicos.desarquivar(identificador, usuario, conexao_de_teste)


async def test_desarquivar_centro_de_custo_devolve_ele_a_lista(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_centros.criar(
        rotas_centros.CentroEntrada(nome=f"Obra {uuid4().hex[:6]}", mundo="infra"),
        usuario,
        conexao_de_teste,
    )
    identificador = UUID(criado["id"])

    await rotas_centros.arquivar(identificador, usuario, conexao_de_teste)
    listagem = await rotas_centros.listar(usuario, conexao_de_teste, mundo="infra")
    assert criado["id"] not in [item["id"] for item in listagem["itens"]]

    voltou = await rotas_centros.desarquivar(identificador, usuario, conexao_de_teste)
    assert voltou["arquivado_em"] is None
    listagem = await rotas_centros.listar(usuario, conexao_de_teste, mundo="infra")
    assert criado["id"] in [item["id"] for item in listagem["itens"]]

    with pytest.raises(ErroNaoEncontrado):
        await rotas_centros.desarquivar(identificador, usuario, conexao_de_teste)


async def test_incluir_arquivados_traz_a_categoria_arquivada_de_volta_na_lista(conexao_de_teste):
    """O nome do parâmetro é `incluir_arquivados`, como manda contracts/cadastros.md §1.

    Estava escrito `incluir_arquivadas` no servidor. O FastAPI **ignora** parâmetro de
    consulta desconhecido, então o que o frontend mandava caía no vazio e a caixa
    "Mostrar arquivadas" da tela de Categorias não fazia nada — sem erro nenhum.
    """
    usuario = await _usuario(conexao_de_teste)
    criada = await rotas_categorias.criar(
        rotas_categorias.CategoriaEntrada(
            nome=f"Temporária {uuid4().hex[:6]}", cor="#8B6CF0", icone="tag", tipo="despesa"
        ),
        usuario,
        conexao_de_teste,
    )
    await rotas_categorias.arquivar(
        UUID(criada["id"]),
        rotas_categorias.ArquivarCategoriaEntrada(),
        usuario,
        conexao_de_teste,
    )

    sem = await rotas_categorias.listar(usuario, conexao_de_teste)
    assert criada["id"] not in [item["id"] for item in sem["itens"]]

    com = await rotas_categorias.listar(usuario, conexao_de_teste, incluir_arquivados=True)
    assert criada["id"] in [item["id"] for item in com["itens"]]
