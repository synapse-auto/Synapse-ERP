"""Custo operacional por cliente contra Postgres real — `RF-58`.

**O que só o banco prova**: que a segunda categoria especial do vínculo `cliente`
existe, que o cadastro cria o espelho nela junto com o de receita, que uma despesa
lançada ali entra no perfil do cliente como custo — e **não** contamina a receita —
e que o Dashboard separa os dois lados em vez de somar tudo no mesmo card.

O caso que some sozinho se o `filter` for escrito errado é o último: com a receita e
o custo caindo no mesmo agrupamento, o cliente apareceria duas vezes no card de
faturamento, uma delas com o valor do custo — e o número continuaria "bonito".

    .venv/Scripts/python -m pytest tests/integracao/test_custos_por_cliente.py -q

⚠️ Roda contra o banco de **produção**; a transação desfeita do `conftest` é o que
protege os dados. Ver o aviso no topo de `tests/conftest.py`.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.clientes import rotas as rotas_clientes
from app.comum.paginacao import Paginacao
from app.dashboard import rotas as rotas_dashboard
from app.dominio import espelho_subcategoria as mod_espelho
from app.seguranca.auth import UsuarioAutenticado

pytestmark = pytest.mark.integracao

HOJE = date.today()


async def _usuario(conexao) -> UsuarioAutenticado:
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, 'Teste RF-58', :email, 'gestor')
            """),
        {"id": str(identificador), "email": f"rf58-{identificador.hex[:8]}@synapse.local"},
    )
    return UsuarioAutenticado(
        id=identificador,
        nome="Teste RF-58",
        email="rf58@synapse.local",
        papel="gestor",
        preferencias={},
    )


def _cliente(nome: str | None = None) -> rotas_clientes.ClienteEntrada:
    return rotas_clientes.ClienteEntrada(
        nome=nome or f"Cliente Custo {uuid4().hex[:6]}", tipo_cobranca="pontual"
    )


async def _lanca(conexao, usuario, *, tipo: str, valor: str, cliente_id: str) -> None:
    """Um lançamento efetivado hoje, no espelho do cliente **daquele lado**.

    Direto em SQL de propósito: o que este arquivo mede é a leitura (perfil e
    Dashboard), e passar pelo `POST /api/lancamentos` traria a validação de
    classificação junto, que já tem teste próprio.
    """
    espelho = await mod_espelho.id_do_dono(
        conexao, vinculo="cliente", dono_id=UUID(cliente_id), tipo=tipo
    )
    categoria = (
        await conexao.execute(
            text("select categoria_id from subcategorias where id = :s"), {"s": str(espelho)}
        )
    ).scalar_one()

    await conexao.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id, subcategoria_id,
              efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
            ) values (
              'digital', cast(:tipo as tipo_lancamento), :descricao, cast(:valor as numeric),
              :data, 'efetivado', :cat, :sub, false, now(), cast(:u as uuid), cast(:u as uuid)
            )
            """),
        {
            "tipo": tipo,
            "descricao": f"teste {tipo} RF-58",
            "valor": valor,
            "data": HOJE,
            "cat": str(categoria),
            "sub": str(espelho),
            "u": str(usuario.id),
        },
    )


# ── A categoria existe, e existe do lado certo ─────────────────────────────


async def test_existe_categoria_de_custo_do_cliente(conexao_de_teste):
    """Resolvida por `vinculo` + `tipo` (`FR-079`), nunca por nome."""
    receita = await mod_espelho.categoria_do_vinculo(conexao_de_teste, "cliente", tipo="receita")
    despesa = await mod_espelho.categoria_do_vinculo(conexao_de_teste, "cliente", tipo="despesa")

    assert receita["id"] != despesa["id"], (
        "Receita e custo do cliente caíram na mesma categoria — o par (vinculo, tipo) "
        "deixou de separar os dois lados."
    )
    assert receita["especial"] and despesa["especial"]


# ── Perfil do cliente ──────────────────────────────────────────────────────


async def test_custo_do_cliente_entra_no_perfil_sem_virar_receita(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente(), usuario, conexao_de_teste)

    await _lanca(
        conexao_de_teste, usuario, tipo="receita", valor="2000.00", cliente_id=criado["id"]
    )
    await _lanca(conexao_de_teste, usuario, tipo="despesa", valor="500.00", cliente_id=criado["id"])

    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)

    assert Decimal(perfil["total_recebido_periodo"]) == Decimal("2000.00"), (
        "O custo entrou na receita — o `filter` por tipo não está separando os lados."
    )
    assert Decimal(perfil["custos"]["total_periodo"]) == Decimal("500.00")
    assert Decimal(perfil["custos"]["margem_periodo"]) == Decimal("1500.00")
    assert perfil["custos"]["margem_percentual_periodo"] == "75.0"

    # A série mensal traz os três números do mesmo mês.
    mes_atual = next(p for p in perfil["receita_mensal"] if p["mes"] == HOJE.strftime("%Y-%m"))
    assert Decimal(mes_atual["valor"]) == Decimal("2000.00")
    assert Decimal(mes_atual["custo"]) == Decimal("500.00")
    assert Decimal(mes_atual["margem"]) == Decimal("1500.00")

    # E a quebra por mundo tem os dois lados, no mundo em que o dinheiro andou.
    assert Decimal(perfil["quebra_por_mundo"]["digital"]) == Decimal("2000.00")
    assert Decimal(perfil["quebra_custo_por_mundo"]["digital"]) == Decimal("500.00")


async def test_margem_percentual_e_nula_quando_o_cliente_so_custou(conexao_de_teste):
    """Custo sem faturamento não é margem de 0% — é margem que não dá para calcular."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente(), usuario, conexao_de_teste)
    await _lanca(conexao_de_teste, usuario, tipo="despesa", valor="300.00", cliente_id=criado["id"])

    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert perfil["custos"]["margem_percentual_periodo"] is None
    assert Decimal(perfil["custos"]["margem_periodo"]) == Decimal("-300.00")


async def test_custo_aparece_na_lista_de_clientes(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_cliente(), usuario, conexao_de_teste)
    await _lanca(
        conexao_de_teste, usuario, tipo="receita", valor="1000.00", cliente_id=criado["id"]
    )
    await _lanca(conexao_de_teste, usuario, tipo="despesa", valor="250.00", cliente_id=criado["id"])

    lista = await rotas_clientes.listar(
        usuario,
        conexao_de_teste,
        Paginacao(pagina=1, por_pagina=200, ordenar=None, direcao="desc"),
    )
    item = next(i for i in lista["itens"] if i["id"] == criado["id"])

    assert Decimal(item["total_recebido_periodo"]) == Decimal("1000.00")
    assert Decimal(item["total_custo_periodo"]) == Decimal("250.00")
    assert Decimal(item["margem_periodo"]) == Decimal("750.00")


# ── Dashboard ──────────────────────────────────────────────────────────────


async def test_dashboard_separa_faturamento_de_custo_do_mesmo_cliente(conexao_de_teste):
    """O caso que some sozinho: sem `tipo` no agrupamento, o cliente entraria duas
    vezes no card de faturamento — uma delas com o valor do custo."""
    usuario = await _usuario(conexao_de_teste)
    nome = f"Cliente Painel {uuid4().hex[:6]}"
    criado = await rotas_clientes.criar(_cliente(nome), usuario, conexao_de_teste)

    await _lanca(
        conexao_de_teste, usuario, tipo="receita", valor="3000.00", cliente_id=criado["id"]
    )
    await _lanca(
        conexao_de_teste, usuario, tipo="despesa", valor="1200.00", cliente_id=criado["id"]
    )

    painel = await rotas_dashboard.obter(usuario, conexao_de_teste, mundo="digital")

    faturamento = [c for c in painel["card_clientes"]["top_clientes"] if c["nome"] == nome]
    assert len(faturamento) == 1, "O mesmo cliente apareceu duas vezes no card de faturamento."
    assert Decimal(faturamento[0]["valor"]) == Decimal("3000.00")

    custos = [c for c in painel["card_custos_cliente"]["por_cliente"] if c["nome"] == nome]
    assert len(custos) == 1
    assert Decimal(custos[0]["custo"]) == Decimal("1200.00")
    assert Decimal(custos[0]["receita"]) == Decimal("3000.00")
    assert Decimal(custos[0]["margem"]) == Decimal("1800.00")
    assert custos[0]["margem_percentual"] == "60.0"


async def test_card_de_custos_esta_no_catalogo_do_dashboard(conexao_de_teste):
    """`FR-106`: id fora do catálogo é ignorado em silêncio pela grade."""
    usuario = await _usuario(conexao_de_teste)
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste)

    ids = {item["id"] for item in painel["cards_disponiveis"]}
    assert "bloco_custos_cliente" in ids, (
        "Sem a entrada no catálogo o bloco existe no frontend e nunca é desenhado."
    )
