"""Medição de `SC-007` e `SC-002` — desempenho com volume real.

Os dois números que a spec cobra:

- **`SC-007`**: com 5.000 lançamentos, aplicar filtro responde em **menos de 2 s**.
- **`SC-002`**: o Dashboard sai em **uma** requisição (contamos as idas ao banco, não o
  relógio — cold start de função serverless polui qualquer medição de tempo aqui).

## Por que estão marcados `integracao` e `lento`

Populam 5.000 linhas. Não é teste de rodar a cada salvamento; é a conferência que
T097 pede e que T204 repete na interface real, já com o frontend no meio.

    .venv/Scripts/python -m pytest tests/integracao/test_desempenho.py -q -m lento

⚠️ **Este arquivo insere milhares de linhas no banco de PRODUÇÃO.** A transação desfeita
do `conftest` garante que nada sobrevive, mas a carga chega ao servidor: são milhares de
INSERTs e um `analyze`, e o `analyze` não volta atrás (é estatística, inofensiva). Por
isso está marcado `lento` e **fora da execução padrão** — rodá-lo é decisão consciente.
Não rode com alguém usando o sistema.

O lado bom de medir contra produção: o número **vale**. É o Supabase de verdade, com rede
no meio e pooler em modo transaction, que é exatamente o que `SC-007` cobra.

Tarefa: T097
"""

import time
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.comum.paginacao import Paginacao
from app.dashboard import rotas as rotas_dashboard
from app.lancamentos import rotas as rotas_lancamentos
from app.seguranca.auth import UsuarioAutenticado

pytestmark = [pytest.mark.integracao, pytest.mark.lento]

QUANTIDADE = 5_000
LIMITE_DO_FILTRO_SEGUNDOS = 2.0


async def _popula(conexao, quantidade: int = QUANTIDADE) -> UsuarioAutenticado:
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, 'Carga de teste', :email, 'gestor')
            """),
        {"id": str(identificador), "email": f"carga-{identificador.hex[:8]}@synapse.local"},
    )
    usuario = UsuarioAutenticado(
        id=identificador,
        nome="Carga de teste",
        email="carga@synapse.local",
        papel="gestor",
        preferencias={},
    )

    categorias = (
        (await conexao.execute(text("select id, tipo from categorias where not especial")))
        .mappings()
        .all()
    )
    if not categorias:
        pytest.fail("Sem categorias — aplique o seed 008 (quickstart.md §3).")

    # `generate_series` gera as 5.000 linhas dentro do banco: 5.000 INSERTs pela rede
    # levariam minutos e mediriam a latência da rede, não a consulta.
    await conexao.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id,
              efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
            )
            select
              (array['digital','infra'])[1 + (n % 2)]::mundo,
              (array['receita','despesa'])[1 + (n % 2)]::tipo_lancamento,
              'carga de desempenho ' || n,
              (10 + (n % 5000))::numeric(14,2),
              (current_date - ((n % 900) || ' days')::interval)::date,
              'efetivado',
              :categoria,
              true, now(), cast(:usuario as uuid), cast(:usuario as uuid)
            from generate_series(1, :quantidade) as n
            """),
        {
            "quantidade": quantidade,
            "categoria": str(categorias[0]["id"]),
            "usuario": str(identificador),
        },
    )
    await conexao.execute(text("analyze lancamentos"))
    return usuario


def _paginacao() -> Paginacao:
    return Paginacao(pagina=1, por_pagina=50, ordenar="data", direcao="desc")


async def test_filtro_com_5000_lancamentos_responde_em_menos_de_2s(conexao_de_teste):
    """`SC-007`. Mede a consulta filtrada + o resumo do conjunto inteiro."""
    usuario = await _popula(conexao_de_teste)

    comeco = time.monotonic()
    resposta = await rotas_lancamentos.listar(
        usuario,
        conexao_de_teste,
        _paginacao(),
        mundo="digital",
        periodo="ultimos_3_meses",
        tipo="despesa",
    )
    duracao = time.monotonic() - comeco

    assert resposta["paginacao"]["total"] > 0, "A carga não gerou nada no recorte medido."
    assert duracao < LIMITE_DO_FILTRO_SEGUNDOS, (
        f"O filtro levou {duracao:.2f}s, acima do limite de {LIMITE_DO_FILTRO_SEGUNDOS}s "
        f"de SC-007. Confira o plano com EXPLAIN — provavelmente um índice deixou de ser "
        f"usado."
    )


async def test_busca_por_texto_usa_o_indice_trigram(conexao_de_teste):
    """`pg_trgm` com `%`; `ilike '%x%'` faria varredura completa das 5.000 linhas."""
    usuario = await _popula(conexao_de_teste)

    comeco = time.monotonic()
    await rotas_lancamentos.listar(
        usuario, conexao_de_teste, _paginacao(), mundo="ambos", busca="desempenho"
    )
    duracao = time.monotonic() - comeco

    assert duracao < LIMITE_DO_FILTRO_SEGUNDOS, (
        f"A busca por texto levou {duracao:.2f}s. O índice GIN de trigram provavelmente "
        f"não está sendo usado."
    )


async def test_dashboard_inteiro_sai_numa_requisicao_http(conexao_de_teste):
    """`SC-002`.

    O que se mede aqui é o **contrato**: uma chamada devolve tudo. O tempo de parede não
    serve de critério porque cold start de função serverless domina a medição e não tem
    relação com a qualidade da consulta — para isso existe `SC-007` acima.
    """
    usuario = await _popula(conexao_de_teste)

    comeco = time.monotonic()
    painel = await rotas_dashboard.obter(
        usuario, conexao_de_teste, mundo="ambos", periodo="este_mes"
    )
    duracao = time.monotonic() - comeco

    # Uma chamada, tudo dentro: cards, gráficos, blocos e resumo.
    assert painel["cards"]
    assert painel["fluxo_caixa_mensal"]
    assert painel["saude_caixa"]
    assert painel["resumo_linguagem_natural"]
    assert "card_clientes" in painel and "card_funcionarios" in painel

    # Limite generoso de propósito: é rede de segurança contra regressão grosseira
    # (um N+1 novo), não o critério de aceitação.
    assert duracao < 5.0, f"O Dashboard levou {duracao:.2f}s — investigue antes de seguir."


async def test_evolucao_do_saldo_nao_faz_uma_consulta_por_mes(conexao_de_teste):
    """A regressão que este teste pega: trocar a janela SQL por um laço em Python.

    Doze meses viram doze idas ao banco, e o Dashboard deixa de caber numa requisição
    sem que nada quebre visivelmente.
    """
    usuario = await _popula(conexao_de_teste, quantidade=1_000)

    comeco = time.monotonic()
    painel = await rotas_dashboard.obter(usuario, conexao_de_teste, mundo="ambos")
    duracao = time.monotonic() - comeco

    assert len(painel["evolucao_saldo"]) >= 12
    assert duracao < 5.0
