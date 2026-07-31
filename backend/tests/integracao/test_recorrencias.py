"""Recorrências, parcelamento e rotina diária contra Postgres real — sub-fase B2.

**Por que contra banco de verdade**: as garantias centrais de B2 são do banco. A
idempotência da rotina se apoia no índice único `(recorrencia_id, data)` (migração
`010`); a materialização incremental se apoia em `gerada_ate`; o `numeric(14,2)` é o que
faz as parcelas somarem exato. Um dublê aprovaria os três estando errados.

## Como rodar

    $env:DATABASE_URL_TESTE = "postgresql://...:6543/postgres"   # NUNCA o de produção
    .venv/Scripts/python -m pytest tests/integracao -q

Sem a variável, pulam com aviso (conftest). O banco precisa das migrações `001`…`010`.

Tarefa: T086
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.comum.erros import ErroConfirmacaoNecessaria, ErroRegraViolada
from app.comum.paginacao import Paginacao
from app.recorrencias import repositorio, rotas, servico
from app.recorrencias.esquemas import (
    ContinuarGeracaoEntrada,
    ParcelamentoEntrada,
    PreviaEntrada,
    RecorrenciaEdicao,
    RecorrenciaEntrada,
)
from app.rotinas import diaria
from app.seguranca.auth import UsuarioAutenticado

pytestmark = pytest.mark.integracao

HOJE = date.today()


# ── Apoio ───────────────────────────────────────────────────────────────────


async def _usuario(conexao) -> UsuarioAutenticado:
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, 'Teste B2', :email, 'gestor')
            """),
        {"id": str(identificador), "email": f"b2-{identificador.hex[:8]}@synapse.local"},
    )
    return UsuarioAutenticado(
        id=identificador, nome="Teste B2", email="b2@synapse.local", papel="gestor", preferencias={}
    )


async def _categoria(conexao, nome: str) -> UUID:
    achada = (
        await conexao.execute(text("select id from categorias where nome = :nome"), {"nome": nome})
    ).scalar_one_or_none()
    if achada is None:
        pytest.fail(f"A categoria '{nome}' não existe. Aplique as migrações 001…010.")
    return achada


def _entrada(categoria_id: UUID, **sobrescreve) -> RecorrenciaEntrada:
    corpo = {
        "mundo": "digital",
        "tipo": "despesa",
        "descricao": "Assinatura mensal",
        "valor": Decimal("100.00"),
        "categoria_id": categoria_id,
        "frequencia": "mensal",
        "dia_vencimento": 10,
        "data_inicio": HOJE.replace(day=10),
        "efetivar_automaticamente": True,
        "confirmar_geracao_retroativa": True,
    }
    return RecorrenciaEntrada(**(corpo | sobrescreve))


def _paginacao(por_pagina: int = 50) -> Paginacao:
    return Paginacao(pagina=1, por_pagina=por_pagina, ordenar=None, direcao="desc")


async def _ocorrencias(conexao, recorrencia_id) -> list[dict]:
    return await repositorio.ocorrencias(conexao, UUID(str(recorrencia_id)))


# ── Criação e materialização ────────────────────────────────────────────────


async def test_criar_recorrencia_materializa_as_ocorrencias(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    criada = await rotas.criar(_entrada(infra), usuario, conexao_de_teste)

    assert criada["geracao"]["concluida"] is True
    assert criada["geracao"]["geradas"] > 0
    assert criada["ocorrencias_geradas"] == criada["geracao"]["geradas"]
    assert criada["rotulo"] == "Mensal, dia 10"


async def test_ocorrencias_retroativas_nascem_efetivadas(conexao_de_teste):
    """`RN-05a` / `SC-004` — o teste que prova a regra ponta a ponta."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    inicio = (HOJE - timedelta(days=150)).replace(day=10)
    criada = await rotas.criar(
        _entrada(infra, data_inicio=inicio, efetivar_automaticamente=False),
        usuario,
        conexao_de_teste,
    )

    ocorrencias = await _ocorrencias(conexao_de_teste, criada["id"])
    passadas = [o for o in ocorrencias if o["data"] <= HOJE]
    futuras = [o for o in ocorrencias if o["data"] > HOJE]

    assert passadas, "Nenhuma ocorrência retroativa foi gerada."
    # Efetivadas MESMO com efetivar_automaticamente=False: o passado já aconteceu.
    assert all(o["status"] == "efetivado" for o in passadas)
    assert all(o["status"] == "programado" for o in futuras)


async def test_serie_longa_pede_confirmacao_antes_de_gravar(conexao_de_teste):
    """`FR-027`: o `422` mostra o impacto e **nada é gravado**."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    antes = (await conexao_de_teste.execute(text("select count(*) from recorrencias"))).scalar_one()

    with pytest.raises(ErroConfirmacaoNecessaria) as capturado:
        await rotas.criar(
            _entrada(
                infra,
                data_inicio=date(2023, 1, 10),
                confirmar_geracao_retroativa=False,
            ),
            usuario,
            conexao_de_teste,
        )

    assert capturado.value.status == 422
    assert capturado.value.extra["campo_confirmacao"] == "confirmar_geracao_retroativa"
    assert capturado.value.extra["previa"]["total_ocorrencias"] > 24

    depois = (
        await conexao_de_teste.execute(text("select count(*) from recorrencias"))
    ).scalar_one()
    assert depois == antes, "O 422 gravou a recorrência mesmo sem confirmação."


async def test_previa_nao_grava_nada(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    antes = (await conexao_de_teste.execute(text("select count(*) from recorrencias"))).scalar_one()

    resposta = await rotas.previa(
        PreviaEntrada(
            frequencia="mensal",
            data_inicio=date(2025, 3, 10),
            dia_vencimento=10,
            valor=Decimal("2000.00"),
        ),
        usuario,
        conexao_de_teste,
    )

    assert resposta["previa"]["total_ocorrencias"] > 0
    assert resposta["previa"]["valor_total_retroativo"] is not None
    depois = (
        await conexao_de_teste.execute(text("select count(*) from recorrencias"))
    ).scalar_one()
    assert depois == antes


# ── Geração em lotes com cursor (D-02a) ─────────────────────────────────────


async def test_lote_pequeno_devolve_cursor_e_continuar_termina(conexao_de_teste):
    """A série longa não trava a invocação: gera um pedaço e devolve o cursor."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    nova = await repositorio.insere(
        conexao_de_teste,
        campos={
            "tipo": "despesa",
            "descricao": "Diária longa",
            "valor": Decimal("10.00"),
            "categoria_id": str(infra),
            "subcategoria_id": None,
            "servico_id": None,
            "centro_custo_id": None,
            "frequencia": "dias",
            "intervalo_dias": 1,
            "dia_vencimento": None,
            "mes_vencimento": None,
            "data_inicio": HOJE - timedelta(days=40),
            "data_fim": None,
            "total_parcelas": None,
            "efetivar_automaticamente": True,
        },
        mundo="digital",
        usuario_id=usuario.id,
    )
    linha = await servico.exige_recorrencia(conexao_de_teste, nova["id"])
    ate = HOJE + timedelta(days=30)

    primeiro = await servico.materializa(
        conexao_de_teste, linha, usuario_id=usuario.id, ate=ate, limite_do_lote=10
    )
    assert primeiro.concluida is False
    assert primeiro.geradas == 10
    assert primeiro.cursor is not None

    # Continuar até o fim, como o frontend faria com a barra de progresso.
    voltas = 0
    while True:
        linha = await servico.exige_recorrencia(conexao_de_teste, nova["id"])
        passo = await servico.materializa(
            conexao_de_teste, linha, usuario_id=usuario.id, ate=ate, limite_do_lote=10
        )
        voltas += 1
        if passo.concluida:
            break
        assert voltas < 50, "A continuação não avançou — laço infinito."

    total = await _ocorrencias(conexao_de_teste, nova["id"])
    assert len(total) == 71  # 40 dias atrás + hoje + 30 à frente


async def test_continuar_geracao_e_idempotente(conexao_de_teste):
    """Chamar de novo depois de concluída não cria nada."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criada = await rotas.criar(_entrada(infra), usuario, conexao_de_teste)

    antes = len(await _ocorrencias(conexao_de_teste, criada["id"]))
    resposta = await rotas.continuar_geracao(
        UUID(criada["id"]), ContinuarGeracaoEntrada(), usuario, conexao_de_teste
    )
    depois = len(await _ocorrencias(conexao_de_teste, criada["id"]))

    assert resposta["geracao"]["geradas"] == 0
    assert depois == antes


# ── `RN-07` — editar a série não toca no passado ────────────────────────────


async def test_editar_com_esta_e_futuras_nao_altera_ocorrencia_passada(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    inicio = (HOJE - timedelta(days=120)).replace(day=1)
    criada = await rotas.criar(
        _entrada(infra, data_inicio=inicio, dia_vencimento=1, valor=Decimal("1800.00")),
        usuario,
        conexao_de_teste,
    )

    passadas_antes = {
        str(o["id"]): o["valor"]
        for o in await _ocorrencias(conexao_de_teste, criada["id"])
        if o["data"] < HOJE
    }
    assert passadas_antes, "Sem ocorrência passada, o teste não prova nada."

    await rotas.editar(
        UUID(criada["id"]),
        RecorrenciaEdicao(
            mundo="digital",
            tipo="despesa",
            descricao="Assinatura mensal",
            valor=Decimal("2000.00"),
            categoria_id=infra,
            frequencia="mensal",
            dia_vencimento=1,
            data_inicio=inicio,
            efetivar_automaticamente=True,
            escopo_serie="esta_e_futuras",
        ),
        usuario,
        conexao_de_teste,
    )

    depois = await _ocorrencias(conexao_de_teste, criada["id"])
    passadas_depois = {str(o["id"]): o["valor"] for o in depois if o["data"] < HOJE}
    futuras_depois = [o for o in depois if o["data"] >= HOJE]

    assert passadas_depois == passadas_antes, "Uma ocorrência passada mudou — viola RN-07."
    assert futuras_depois, "As futuras não foram regeradas."
    assert all(Decimal(str(o["valor"])) == Decimal("2000.00") for o in futuras_depois)


async def test_editar_com_apenas_esta_e_recusado_explicando(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criada = await rotas.criar(_entrada(infra), usuario, conexao_de_teste)

    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas.editar(
            UUID(criada["id"]),
            RecorrenciaEdicao(
                mundo="digital",
                tipo="despesa",
                descricao="Assinatura mensal",
                valor=Decimal("120.00"),
                categoria_id=infra,
                frequencia="mensal",
                dia_vencimento=10,
                data_inicio=HOJE.replace(day=10),
                escopo_serie="apenas_esta",
            ),
            usuario,
            conexao_de_teste,
        )
    assert capturado.value.requisito == "RN-07"


async def test_mudar_o_mundo_da_recorrencia_e_recusado(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criada = await rotas.criar(_entrada(infra), usuario, conexao_de_teste)

    with pytest.raises(ErroRegraViolada) as capturado:
        await rotas.editar(
            UUID(criada["id"]),
            RecorrenciaEdicao(
                mundo="infra",
                tipo="despesa",
                descricao="Assinatura mensal",
                valor=Decimal("100.00"),
                categoria_id=infra,
                frequencia="mensal",
                dia_vencimento=10,
                data_inicio=HOJE.replace(day=10),
                escopo_serie="esta_e_futuras",
            ),
            usuario,
            conexao_de_teste,
        )
    assert capturado.value.requisito == "RN-15"


# ── Desativar e excluir ─────────────────────────────────────────────────────


async def test_desativar_remove_futuras_e_preserva_efetivadas(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    inicio = (HOJE - timedelta(days=90)).replace(day=5)
    criada = await rotas.criar(
        _entrada(infra, data_inicio=inicio, dia_vencimento=5), usuario, conexao_de_teste
    )
    efetivadas_antes = [
        o for o in await _ocorrencias(conexao_de_teste, criada["id"]) if o["status"] == "efetivado"
    ]

    resposta = await rotas.desativar(UUID(criada["id"]), usuario, conexao_de_teste)
    assert resposta["ativa"] is False
    assert resposta["ocorrencias_futuras_removidas"] > 0

    restantes = await _ocorrencias(conexao_de_teste, criada["id"])
    assert len(restantes) == len(efetivadas_antes)
    assert all(o["status"] == "efetivado" for o in restantes)


async def test_desativar_duas_vezes_e_recusado(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criada = await rotas.criar(_entrada(infra), usuario, conexao_de_teste)

    await rotas.desativar(UUID(criada["id"]), usuario, conexao_de_teste)
    with pytest.raises(ErroRegraViolada):
        await rotas.desativar(UUID(criada["id"]), usuario, conexao_de_teste)


async def test_lista_filtra_por_mundo(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    do_digital = await rotas.criar(_entrada(infra, mundo="digital"), usuario, conexao_de_teste)
    do_infra = await rotas.criar(_entrada(infra, mundo="infra"), usuario, conexao_de_teste)

    lista = await rotas.listar(usuario, conexao_de_teste, _paginacao(200), mundo="digital")
    ids = {item["id"] for item in lista["itens"]}
    assert do_digital["id"] in ids
    assert do_infra["id"] not in ids


# ── Parcelamento (`FR-028`) ─────────────────────────────────────────────────


async def test_parcelamento_soma_exata_com_a_ultima_absorvendo(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    resposta = await rotas.criar_parcelamento(
        ParcelamentoEntrada(
            mundo="digital",
            tipo="despesa",
            descricao="Equipamento",
            valor_total=Decimal("1000.00"),
            total_parcelas=3,
            data_primeira_parcela=HOJE + timedelta(days=5),
            categoria_id=infra,
        ),
        usuario,
        conexao_de_teste,
    )

    valores = [Decimal(p["valor"]) for p in resposta["parcelas"]]
    assert valores == [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")]
    assert sum(valores) == Decimal("1000.00")
    assert resposta["parcelas"][1]["rotulo"] == "2/3"
    assert "(2/3)" in resposta["parcelas"][1]["descricao"]


async def test_parcelas_futuras_nascem_programadas(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    resposta = await rotas.criar_parcelamento(
        ParcelamentoEntrada(
            mundo="digital",
            tipo="despesa",
            descricao="Equipamento",
            valor_total=Decimal("300.00"),
            total_parcelas=3,
            data_primeira_parcela=HOJE + timedelta(days=5),
            categoria_id=infra,
        ),
        usuario,
        conexao_de_teste,
    )
    assert all(p["status"] == "programado" for p in resposta["parcelas"])
    assert resposta["pago"] == "0.00"
    assert resposta["a_pagar"] == "300.00"


# ── Rotina diária (D-08) ────────────────────────────────────────────────────


async def test_rotina_efetiva_o_automatico_e_deixa_o_manual_pendente(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    automatico = await _lancamento_programado(
        conexao_de_teste, usuario, infra, vence=HOJE, automatico=True
    )
    manual = await _lancamento_programado(
        conexao_de_teste, usuario, infra, vence=HOJE, automatico=False
    )

    await diaria.executa(conexao_de_teste, hoje=HOJE)

    assert await _status(conexao_de_teste, automatico) == "efetivado"
    assert await _status(conexao_de_teste, manual) == "pendente"


async def test_rotina_marca_atrasado_so_o_manual_vencido(conexao_de_teste):
    """D-05: o automático se efetiva na data e **nunca** chega a atrasado."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    ontem = HOJE - timedelta(days=1)
    automatico = await _lancamento_programado(
        conexao_de_teste, usuario, infra, vence=ontem, automatico=True
    )
    manual = await _lancamento_programado(
        conexao_de_teste, usuario, infra, vence=ontem, automatico=False
    )

    await diaria.executa(conexao_de_teste, hoje=HOJE)  # programado → efetivado/pendente
    await diaria.executa(conexao_de_teste, hoje=HOJE)  # pendente → atrasado

    assert await _status(conexao_de_teste, automatico) == "efetivado"
    assert await _status(conexao_de_teste, manual) == "atrasado"


async def test_rodar_a_rotina_duas_vezes_no_mesmo_dia_nao_duplica_nada(conexao_de_teste):
    """A propriedade central de D-08."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    criada = await rotas.criar(_entrada(infra), usuario, conexao_de_teste)

    antes = len(await _ocorrencias(conexao_de_teste, criada["id"]))
    primeira = await diaria.executa(conexao_de_teste, hoje=HOJE)
    segunda = await diaria.executa(conexao_de_teste, hoje=HOJE)
    depois = len(await _ocorrencias(conexao_de_teste, criada["id"]))

    assert depois == antes
    assert segunda["ja_executada_hoje"] is True
    assert segunda["resultado"]["ocorrencias_geradas"] == 0
    assert primeira["data_processada"] == HOJE.isoformat()


async def test_dia_perdido_e_recuperado_na_execucao_seguinte(conexao_de_teste):
    """O cron falhou ontem: hoje a rotina cobre o buraco e diz que cobriu."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    await conexao_de_teste.execute(
        text("""
            insert into execucoes_rotina (
              nome, ultima_execucao_em, ultima_data_processada, ultimo_resultado
            ) values ('diaria', now() - interval '3 days', :antiga, '{}'::jsonb)
            on conflict (nome) do update set ultima_data_processada = excluded.ultima_data_processada
            """),
        {"antiga": HOJE - timedelta(days=3)},
    )

    vencido = await _lancamento_programado(
        conexao_de_teste, usuario, infra, vence=HOJE - timedelta(days=2), automatico=True
    )
    resposta = await diaria.executa(conexao_de_teste, hoje=HOJE)

    assert await _status(conexao_de_teste, vencido) == "efetivado"
    assert any("recuperado" in aviso for aviso in resposta["resultado"]["avisos"])


async def test_estado_da_rotina_guarda_o_que_ela_fez(conexao_de_teste):
    """Princípio VI: "funcionou" precisa ser conferível, não afirmado."""
    await diaria.executa(conexao_de_teste, hoje=HOJE)

    linha = (
        (
            await conexao_de_teste.execute(
                text(
                    "select ultima_data_processada, ultimo_resultado "
                    "from execucoes_rotina where nome = 'diaria'"
                )
            )
        )
        .mappings()
        .one()
    )
    assert linha["ultima_data_processada"] == HOJE
    assert "ocorrencias_geradas" in linha["ultimo_resultado"]


async def test_chamada_implicita_nao_derruba_a_leitura_se_falhar(conexao_de_teste):
    """T085: um cron falho não pode virar erro no lugar do Dashboard."""
    await diaria.executa_se_necessario(conexao_de_teste, HOJE)
    assert await diaria.ja_rodou_hoje(conexao_de_teste, HOJE) is True


# ── Apoio dos testes de rotina ──────────────────────────────────────────────


async def _lancamento_programado(conexao, usuario, categoria_id, *, vence: date, automatico: bool):
    return (
        await conexao.execute(
            text("""
                insert into lancamentos (
                  mundo, tipo, descricao, valor, data, status,
                  categoria_id, efetivar_automaticamente, criado_por
                ) values (
                  'digital', 'despesa', 'teste de rotina', 10.00, :data, 'programado',
                  :categoria, :automatico, cast(:usuario as uuid)
                )
                returning id
                """),
            {
                "data": vence,
                "categoria": str(categoria_id),
                "automatico": automatico,
                "usuario": str(usuario.id),
            },
        )
    ).scalar_one()


async def _status(conexao, lancamento_id) -> str:
    return (
        await conexao.execute(
            text("select status from lancamentos where id = :id"), {"id": str(lancamento_id)}
        )
    ).scalar_one()
