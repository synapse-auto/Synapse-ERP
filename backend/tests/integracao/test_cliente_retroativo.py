"""Cliente retroativo ("cliente desde") contra Postgres real.

**O que só o banco prova**, e é por isso que estes testes existem separados dos de
unidade:

- que as ocorrências passadas realmente **entram no saldo** — `RN-05` é uma soma no
  banco, não uma função Python;
- que o mês corrente **não duplica** — a garantia é o índice único
  `(recorrencia_id, data)`, que não existe fora do Postgres;
- que 18 meses custam **uma** ida ao banco, não 18 (`insert … select from unnest`);
- que repetir o `POST` com a mesma `Idempotency-Key` não carrega o histórico duas
  vezes.

    .venv/Scripts/python -m pytest tests/integracao/test_cliente_retroativo.py -q

⚠️ Rodam contra o banco de **produção**; a transação desfeita do `conftest` é o que
protege os dados. Ver o aviso no topo de `tests/conftest.py`.

Tarefa: cliente retroativo (2026-08-04)
"""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from dateutil.relativedelta import relativedelta
from sqlalchemy import text

from app.clientes import rotas as rotas_clientes
from app.comum.erros import ErroValidacao
from app.comum.paginacao import Paginacao
from app.seguranca.auth import UsuarioAutenticado

pytestmark = pytest.mark.integracao

HOJE = date.today()
VALOR = Decimal("2000.00")
DIA_COBRANCA = 10


async def _usuario(conexao) -> UsuarioAutenticado:
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, 'Teste retroativo', :email, 'gestor')
            """),
        {"id": str(identificador), "email": f"retro-{identificador.hex[:8]}@synapse.local"},
    )
    return UsuarioAutenticado(
        id=identificador,
        nome="Teste retroativo",
        email="retro@synapse.local",
        papel="gestor",
        preferencias={},
    )


def _corpo(**sobrescreve) -> rotas_clientes.ClienteEntrada:
    return rotas_clientes.ClienteEntrada(
        **{
            "nome": f"Retroativo {uuid4().hex[:6]}",
            "tipo_cobranca": "recorrente",
            "valor_recorrente": VALOR,
            "dia_cobranca": DIA_COBRANCA,
            "mundo_cobranca": "digital",
            **sobrescreve,
        }
    )


def _mes(meses_atras: int) -> str:
    alvo = HOJE - relativedelta(months=meses_atras)
    return f"{alvo.year:04d}-{alvo.month:02d}"


async def _caixa(conexao, mundo: str = "digital") -> Decimal:
    """O caixa como `RN-05` o define: **só** o que está efetivado."""
    valor = (
        await conexao.execute(
            text("""
                select coalesce(sum(valor) filter (where tipo = 'receita'), 0)
                     - coalesce(sum(valor) filter (where tipo = 'despesa'), 0)
                from lancamentos_ativos
                where status = 'efetivado' and mundo = cast(:mundo as mundo)
                """),
            {"mundo": mundo},
        )
    ).scalar_one()
    return Decimal(str(valor))


async def _ocorrencias(conexao, recorrencia_id: str) -> list[tuple[date, str, str]]:
    linhas = (
        (
            await conexao.execute(
                text("""
                    select data, status, mundo from lancamentos_ativos
                    where recorrencia_id = cast(:id as uuid)
                    order by data
                    """),
                {"id": recorrencia_id},
            )
        )
        .mappings()
        .all()
    )
    return [(linha["data"], linha["status"], linha["mundo"]) for linha in linhas]


# ── O cenário pedido: 18 meses de casa ──────────────────────────────────────


async def test_dezoito_meses_atras_sobem_o_caixa_pelo_valor_certo(conexao_de_teste):
    """O teste que o dono do projeto pediu, com o número conferido dos dois lados.

    A conta não é "18 × 2000" escrita à mão: é a quantidade de ocorrências efetivadas
    que o banco realmente gravou, multiplicada pelo valor. Se a geração pular ou repetir
    um mês, os dois lados discordam.
    """
    usuario = await _usuario(conexao_de_teste)
    antes = await _caixa(conexao_de_teste)

    criado = await rotas_clientes.criar(_corpo(cliente_desde=_mes(18)), usuario, conexao_de_teste)

    ocorrencias = await _ocorrencias(conexao_de_teste, criado["recorrencia"]["id"])
    efetivadas = [linha for linha in ocorrencias if linha[1] == "efetivado"]

    assert len(efetivadas) >= 18, "O histórico dos 18 meses não foi gerado."
    assert await _caixa(conexao_de_teste) - antes == VALOR * len(efetivadas)

    # `RN-05`: o que ainda não venceu **não** entra no saldo, mesmo estando gravado.
    assert any(linha[1] == "programado" for linha in ocorrencias)


async def test_a_resposta_conta_o_que_foi_carregado(conexao_de_teste):
    """`RNF-02`: a tela mostra o número e o texto que o servidor mandou."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_corpo(cliente_desde=_mes(18)), usuario, conexao_de_teste)

    retroativo = criado["recorrencia"]["retroativo"]
    assert retroativo is not None
    assert retroativo["ocorrencias_efetivadas"] >= 18
    assert Decimal(retroativo["valor_total"]) == VALOR * retroativo["ocorrencias_efetivadas"]
    assert "já contam no saldo" in retroativo["mensagem"]


async def test_ocorrencias_ficam_na_serie_e_no_mundo_da_cobranca(conexao_de_teste):
    """`RN-15` e o vínculo: nem lançamento solto, nem lançamento sem mundo."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(
        _corpo(cliente_desde=_mes(6), mundo_cobranca="infra"), usuario, conexao_de_teste
    )

    ocorrencias = await _ocorrencias(conexao_de_teste, criado["recorrencia"]["id"])
    assert ocorrencias, "Nenhuma ocorrência ficou ligada à recorrência."
    assert {linha[2] for linha in ocorrencias} == {"infra"}

    # Todas penduradas na subcategoria espelho — é o que faz o perfil e o Dashboard
    # acharem esse dinheiro (D-07).
    fora_do_espelho = (
        await conexao_de_teste.execute(
            text("""
                select count(*) from lancamentos_ativos
                where recorrencia_id = cast(:id as uuid)
                  and subcategoria_id is distinct from cast(:espelho as uuid)
                """),
            {"id": criado["recorrencia"]["id"], "espelho": criado["subcategoria_id"]},
        )
    ).scalar_one()
    assert fora_do_espelho == 0


async def test_dia_31_cai_no_ultimo_dia_do_mes_curto(conexao_de_teste):
    """A regra do dia 31 é a da recorrência, reaproveitada — não uma segunda cópia."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(
        _corpo(cliente_desde=_mes(18), dia_cobranca=31), usuario, conexao_de_teste
    )

    datas = [
        linha[0] for linha in await _ocorrencias(conexao_de_teste, criado["recorrencia"]["id"])
    ]
    fevereiros = [quando for quando in datas if quando.month == 2]
    assert fevereiros, "A janela de 18 meses não pegou nenhum fevereiro."
    for quando in fevereiros:
        assert quando.day in (28, 29)
    # E março volta para 31 — o clamp é por mês, nunca acumulado.
    for quando in [d for d in datas if d.month == 3]:
        assert quando.day == 31


# ── O que não pode acontecer ────────────────────────────────────────────────


async def test_mes_atual_nao_duplica_e_gera_o_mesmo_que_sem_retroativo(conexao_de_teste):
    """A regra "mês corrente = comportamento de hoje", conferida no banco.

    Duas criações, uma com `cliente_desde` do mês atual e outra sem nada: as datas
    geradas têm que ser **idênticas**. Se um dia divergirem, o mês corrente aparece
    duas vezes no caixa de quem cadastrar assim.
    """
    usuario = await _usuario(conexao_de_teste)
    mes_atual = f"{HOJE.year:04d}-{HOJE.month:02d}"

    com = await rotas_clientes.criar(_corpo(cliente_desde=mes_atual), usuario, conexao_de_teste)
    sem = await rotas_clientes.criar(_corpo(), usuario, conexao_de_teste)

    datas_com = [
        linha[0] for linha in await _ocorrencias(conexao_de_teste, com["recorrencia"]["id"])
    ]
    datas_sem = [
        linha[0] for linha in await _ocorrencias(conexao_de_teste, sem["recorrencia"]["id"])
    ]

    assert datas_com == datas_sem
    assert len(datas_com) == len(set(datas_com)), "O mês corrente saiu duplicado."
    assert com["recorrencia"]["retroativo"] is None


async def test_uma_data_por_mes_sem_repeticao(conexao_de_teste):
    """O índice único `(recorrencia_id, data)` fazendo o trabalho dele."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_corpo(cliente_desde=_mes(24)), usuario, conexao_de_teste)

    datas = [
        linha[0] for linha in await _ocorrencias(conexao_de_teste, criado["recorrencia"]["id"])
    ]
    assert len(datas) == len(set(datas))
    meses = [(quando.year, quando.month) for quando in datas]
    assert len(meses) == len(set(meses)), "Dois lançamentos no mesmo mês."


async def test_repetir_o_post_com_a_mesma_chave_nao_dobra_o_historico(conexao_de_teste):
    """A repetição que a Vercel faz depois de um timeout não pode contar duas vezes.

    Sem a chave de idempotência, a segunda invocação criaria um cliente **novo** com o
    histórico inteiro de novo — e o `on conflict` da ocorrência não veria nada de
    errado, porque a recorrência é outra.
    """
    usuario = await _usuario(conexao_de_teste)
    corpo = _corpo(cliente_desde=_mes(18))
    chave = f"teste-{uuid4().hex}"

    antes = await _caixa(conexao_de_teste)
    primeira = await rotas_clientes.criar(corpo, usuario, conexao_de_teste, chave=chave)
    depois_da_primeira = await _caixa(conexao_de_teste)
    segunda = await rotas_clientes.criar(corpo, usuario, conexao_de_teste, chave=chave)

    assert segunda["id"] == primeira["id"], "Nasceu um segundo cliente."
    assert await _caixa(conexao_de_teste) == depois_da_primeira
    assert depois_da_primeira > antes


async def test_futuro_e_limite_sao_recusados(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)

    with pytest.raises(ErroValidacao):
        await rotas_clientes.criar(_corpo(cliente_desde=_mes(-1)), usuario, conexao_de_teste)

    # O limite vem de `configuracoes.cliente_retroativo_meses_maximo` (padrão 120).
    with pytest.raises(ErroValidacao):
        await rotas_clientes.criar(_corpo(cliente_desde="1990-01"), usuario, conexao_de_teste)


async def test_retroativo_nao_existe_em_cobranca_pontual(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    with pytest.raises(ErroValidacao):
        await rotas_clientes.criar(
            rotas_clientes.ClienteEntrada(
                nome="Pontual retroativo", tipo_cobranca="pontual", cliente_desde=_mes(6)
            ),
            usuario,
            conexao_de_teste,
        )


async def test_editar_recusa_carregar_historico(conexao_de_teste):
    """A edição não mexe na recorrência — aceitar o campo prometeria o que não faria."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_corpo(), usuario, conexao_de_teste)

    with pytest.raises(ErroValidacao):
        await rotas_clientes.editar(
            UUID(criado["id"]), _corpo(cliente_desde=_mes(6)), usuario, conexao_de_teste
        )


# ── Onde o histórico tem que aparecer depois ────────────────────────────────


async def test_cliente_desde_e_derivado_e_aparece_na_lista_e_no_perfil(conexao_de_teste):
    """Sem coluna nova: a data sai do lançamento mais antigo (data-model §3.4)."""
    usuario = await _usuario(conexao_de_teste)
    nome = f"Desde {uuid4().hex[:6]}"
    criado = await rotas_clientes.criar(
        _corpo(nome=nome, cliente_desde=_mes(18)), usuario, conexao_de_teste
    )

    esperado = (HOJE - relativedelta(months=18)).replace(day=DIA_COBRANCA)

    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert perfil["cliente_desde"] == esperado.isoformat()

    lista = await rotas_clientes.listar(
        usuario,
        conexao_de_teste,
        Paginacao(pagina=1, por_pagina=50, ordenar=None, direcao="desc"),
        busca=nome,
    )
    encontrado = next(item for item in lista["itens"] if item["id"] == criado["id"])
    assert encontrado["cliente_desde"] == esperado.isoformat()


async def test_cliente_sem_historico_e_cliente_desde_hoje(conexao_de_teste):
    """A primeira mensalidade pode vencer só no mês que vem — e nem por isso o cliente
    é "cliente desde o mês que vem"."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(
        _corpo(dia_cobranca=28 if HOJE.day < 28 else 1), usuario, conexao_de_teste
    )
    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert perfil["cliente_desde"] <= HOJE.isoformat()


async def test_grafico_do_perfil_cobre_o_tempo_de_casa(conexao_de_teste):
    """Era fixo em 12 meses, e cortava justamente o histórico recém-carregado."""
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_corpo(cliente_desde=_mes(18)), usuario, conexao_de_teste)
    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)

    serie = perfil["receita_mensal"]
    assert len(serie) >= 19, "O gráfico cortaria os primeiros meses do histórico."
    com_valor = [ponto for ponto in serie if Decimal(ponto["valor"]) > 0]
    assert len(com_valor) >= 18
    assert serie[0]["mes"] <= _mes(18)


async def test_lancamentos_do_perfil_e_o_total_historico_enxergam_o_passado(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_corpo(cliente_desde=_mes(18)), usuario, conexao_de_teste)
    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)

    esperado = VALOR * criado["recorrencia"]["retroativo"]["ocorrencias_efetivadas"]
    assert Decimal(perfil["total_recebido_historico"]) == esperado
    assert Decimal(perfil["quebra_por_mundo"]["digital"]) == esperado
    # O período padrão é o mês corrente, então o total do período **não** é o histórico.
    assert Decimal(perfil["total_recebido_periodo"]) < esperado


async def test_carregar_36_meses_custa_o_mesmo_numero_de_idas_ao_banco_que_6(conexao_de_teste):
    """O ponto crítico de desempenho, medido no que de fato custa: **idas ao banco**.

    O banco é remoto (`db.py`: 1328 ms de mediana por consulta com pool quente), então
    36 ocorrências em laço seriam 36 viagens — meio minuto para cadastrar um cliente, e
    a função da Vercel cortada no meio. O `insert … select from unnest(…)` faz as 36
    numa.

    Este teste não olha o relógio: conta os `execute` que saem da conexão. Um laço de
    `insert` novo faria a contagem crescer com o número de meses, e é exatamente isso
    que o `assert` final proíbe.
    """
    from sqlalchemy import event

    usuario = await _usuario(conexao_de_teste)
    bruto = conexao_de_teste.sync_connection
    contagem = {"n": 0}

    def _conta(*_args, **_kwargs):
        contagem["n"] += 1

    async def _mede(meses: int) -> int:
        contagem["n"] = 0
        event.listen(bruto, "before_cursor_execute", _conta)
        try:
            await rotas_clientes.criar(_corpo(cliente_desde=_mes(meses)), usuario, conexao_de_teste)
        finally:
            event.remove(bruto, "before_cursor_execute", _conta)
        return contagem["n"]

    # Aquecimento: a primeira criação da conexão ainda paga a leitura de
    # `configuracoes`, que depois vem do cache do processo
    # (`comum/cache_configuracoes.py`). Sem isto a primeira medição sai 1 ida mais cara
    # e o teste compararia coisas diferentes.
    await _mede(1)

    seis = await _mede(6)
    trinta_e_seis = await _mede(36)

    assert trinta_e_seis == seis, (
        f"{seis} idas para 6 meses e {trinta_e_seis} para 36 — o custo passou a crescer "
        "com o histórico. Procure um laço de insert."
    )
    # Teto absoluto: cadastro de cliente é cliente + espelho + serviços + recorrência +
    # ocorrências + auditoria + as releituras da resposta. Uma dúzia e meia, não trinta.
    assert trinta_e_seis < 20, f"{trinta_e_seis} idas ao banco para cadastrar um cliente."


async def test_o_cliente_antigo_nao_nasce_inadimplente(conexao_de_teste):
    """`RN-05a` de novo, agora pelo lado que o usuário vê.

    Se as ocorrências passadas nascessem `pendente`, o cliente que acabou de ser
    cadastrado apareceria devendo 18 meses no dia seguinte ao cadastro.
    """
    usuario = await _usuario(conexao_de_teste)
    criado = await rotas_clientes.criar(_corpo(cliente_desde=_mes(18)), usuario, conexao_de_teste)
    perfil = await rotas_clientes.detalhar(UUID(criado["id"]), usuario, conexao_de_teste)
    assert perfil["situacao"] == "em_dia"
    assert perfil["dias_atraso"] is None
