"""As rotinas contra Postgres real — a prova de D-08.

Duas propriedades, e as duas só se provam com banco: **rodar duas vezes no mesmo dia não
duplica nada** (o `UNIQUE (usuario_id, chave_deduplicacao)` é quem garante) e **um dia
perdido é recuperado** na execução seguinte.

    .venv/Scripts/python -m pytest tests/integracao -q

⚠️ Rodam contra o banco de **produção**; a transação desfeita do `conftest` é o
que protege os dados. Ver o aviso no topo de `tests/conftest.py`.

Tarefa: T128
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.rotinas import diaria, semanal
from app.seguranca.auth import UsuarioAutenticado

pytestmark = pytest.mark.integracao

HOJE = date.today()


async def _usuario(conexao) -> UsuarioAutenticado:
    identificador = uuid4()
    await conexao.execute(
        text("""
            insert into usuarios (id, nome, email, papel)
            values (:id, 'Teste rotinas', :email, 'gestor')
            """),
        {"id": str(identificador), "email": f"rot-{identificador.hex[:8]}@synapse.local"},
    )
    return UsuarioAutenticado(
        id=identificador,
        nome="Teste rotinas",
        email="rot@synapse.local",
        papel="gestor",
        preferencias={},
    )


async def _categoria(conexao, nome: str) -> UUID:
    achada = (
        await conexao.execute(text("select id from categorias where nome = :nome"), {"nome": nome})
    ).scalar_one_or_none()
    if achada is None:
        pytest.fail(f"A categoria '{nome}' não existe. Aplique as migrações 001…011.")
    return achada


async def _lanca(conexao, usuario, categoria, *, quando, status="programado", automatico=False):
    return (
        await conexao.execute(
            text("""
                insert into lancamentos (
                  mundo, tipo, descricao, valor, data, status, categoria_id,
                  efetivar_automaticamente, criado_por
                ) values (
                  'digital', 'despesa', 'conta a vencer', 480.00, :data,
                  cast(:status as status_lancamento), :cat, :auto, cast(:u as uuid)
                )
                returning id
                """),
            {
                "data": quando,
                "status": status,
                "cat": str(categoria),
                "auto": automatico,
                "u": str(usuario.id),
            },
        )
    ).scalar_one()


async def _notificacoes(conexao, usuario, tipo: str) -> int:
    return (
        await conexao.execute(
            text("""
                select count(*) from notificacoes
                where usuario_id = :u and tipo = cast(:tipo as tipo_notificacao)
                """),
            {"u": str(usuario.id), "tipo": tipo},
        )
    ).scalar_one()


# ── Idempotência (D-08) ────────────────────────────────────────────────────


async def test_rodar_duas_vezes_no_mesmo_dia_nao_duplica_notificacao(conexao_de_teste):
    """A propriedade central: a rotina roda pelo cron, pelo disparo manual e pela
    chamada implícita de uma leitura. Três vezes no mesmo dia é o caso comum."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    await _lanca(conexao_de_teste, usuario, infra, quando=HOJE + timedelta(days=3))

    await diaria.executa(conexao_de_teste, hoje=HOJE)
    primeira = await _notificacoes(conexao_de_teste, usuario, "vencimento")

    await diaria.executa(conexao_de_teste, hoje=HOJE)
    await diaria.executa(conexao_de_teste, hoje=HOJE)
    terceira = await _notificacoes(conexao_de_teste, usuario, "vencimento")

    assert primeira >= 1, "Nenhum alerta de vencimento foi criado."
    assert terceira == primeira, "A rotina duplicou o alerta ao rodar de novo."


async def test_a_antecedencia_faz_avisos_diferentes_do_mesmo_lancamento(conexao_de_teste):
    """ "Vence em 7" e "vence em 3" são fatos diferentes — os dois devem existir."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")
    lancamento = await _lanca(conexao_de_teste, usuario, infra, quando=HOJE + timedelta(days=7))

    await diaria.executa(conexao_de_teste, hoje=HOJE)  # avisa "em 7"
    await diaria.executa(conexao_de_teste, hoje=HOJE + timedelta(days=4))  # avisa "em 3"

    chaves = (
        (
            await conexao_de_teste.execute(
                text("""
                select chave_deduplicacao from notificacoes
                where usuario_id = :u and lancamento_id = :l
                order by chave_deduplicacao
                """),
                {"u": str(usuario.id), "l": str(lancamento)},
            )
        )
        .scalars()
        .all()
    )

    assert len(chaves) == 2
    assert chaves[0].endswith(":3")
    assert chaves[1].endswith(":7")


async def test_dia_perdido_e_recuperado(conexao_de_teste):
    """O cron falhou ontem: hoje a rotina cobre o buraco e diz que cobriu."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    await conexao_de_teste.execute(
        text("""
            insert into execucoes_rotina (
              nome, ultima_execucao_em, ultima_data_processada, ultimo_resultado
            ) values ('diaria', now() - interval '3 days', :antiga, '{}'::jsonb)
            on conflict (nome) do update
              set ultima_data_processada = excluded.ultima_data_processada
            """),
        {"antiga": HOJE - timedelta(days=3)},
    )
    vencido = await _lanca(
        conexao_de_teste, usuario, infra, quando=HOJE - timedelta(days=2), automatico=True
    )

    resposta = await diaria.executa(conexao_de_teste, hoje=HOJE)

    status = (
        await conexao_de_teste.execute(
            text("select status from lancamentos where id = :id"), {"id": str(vencido)}
        )
    ).scalar_one()
    assert status == "efetivado"
    assert any("recuperado" in aviso for aviso in resposta["resultado"]["avisos"])


# ── Inadimplência (`FR-097`) ───────────────────────────────────────────────


async def test_alerta_de_inadimplencia_usa_a_mesma_regra_da_tela(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    clientes = await _categoria(conexao_de_teste, "Clientes")

    cliente = (
        await conexao_de_teste.execute(
            text("""
                insert into clientes (nome, tipo_cobranca) values (:nome, 'pontual')
                returning id
                """),
            {"nome": f"Devedor {uuid4().hex[:6]}"},
        )
    ).scalar_one()
    subcategoria = (
        await conexao_de_teste.execute(
            text("""
                insert into subcategorias (categoria_id, nome, cliente_id)
                values (:cat, :nome, :cli) returning id
                """),
            {"cat": str(clientes), "nome": "Devedor", "cli": str(cliente)},
        )
    ).scalar_one()
    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id, subcategoria_id,
              efetivar_automaticamente, criado_por
            ) values (
              'digital', 'receita', 'mensalidade', 2000.00, :data, 'atrasado',
              :cat, :sub, false, cast(:u as uuid)
            )
            """),
        {
            "data": HOJE - timedelta(days=8),
            "cat": str(clientes),
            "sub": str(subcategoria),
            "u": str(usuario.id),
        },
    )

    resposta = await diaria.executa(conexao_de_teste, hoje=HOJE)
    assert resposta["resultado"]["clientes_marcados_inadimplentes"] >= 1
    assert await _notificacoes(conexao_de_teste, usuario, "inadimplencia") >= 1


async def test_atraso_com_efetivacao_automatica_nao_gera_alerta(conexao_de_teste):
    """D-05, na rotina: o sistema vai efetivar sozinho, não há o que cobrar."""
    usuario = await _usuario(conexao_de_teste)
    clientes = await _categoria(conexao_de_teste, "Clientes")

    cliente = (
        await conexao_de_teste.execute(
            text("insert into clientes (nome, tipo_cobranca) values (:n, 'pontual') returning id"),
            {"n": f"Automático {uuid4().hex[:6]}"},
        )
    ).scalar_one()
    subcategoria = (
        await conexao_de_teste.execute(
            text("""
                insert into subcategorias (categoria_id, nome, cliente_id)
                values (:cat, :nome, :cli) returning id
                """),
            {"cat": str(clientes), "nome": "Automático", "cli": str(cliente)},
        )
    ).scalar_one()
    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id, subcategoria_id,
              efetivar_automaticamente, criado_por
            ) values (
              'digital', 'receita', 'mensalidade', 2000.00, :data, 'pendente',
              :cat, :sub, true, cast(:u as uuid)
            )
            """),
        {
            "data": HOJE - timedelta(days=90),
            "cat": str(clientes),
            "sub": str(subcategoria),
            "u": str(usuario.id),
        },
    )

    antes = await _notificacoes(conexao_de_teste, usuario, "inadimplencia")
    await diaria.executa(conexao_de_teste, hoje=HOJE)
    assert await _notificacoes(conexao_de_teste, usuario, "inadimplencia") == antes


# ── Rotina semanal (`FR-098`, `FR-099`) ────────────────────────────────────


async def test_resumo_semanal_e_um_so_por_semana(conexao_de_teste):
    """Rodar cinco vezes na mesma segunda produz um resumo — chave por semana ISO."""
    usuario = await _usuario(conexao_de_teste)

    segunda = HOJE - timedelta(days=HOJE.isoweekday() - 1)
    await semanal.executa(conexao_de_teste, hoje=segunda)
    await semanal.executa(conexao_de_teste, hoje=segunda)
    await semanal.executa(conexao_de_teste, hoje=segunda + timedelta(days=2))

    assert await _notificacoes(conexao_de_teste, usuario, "resumo_semanal") == 1


async def test_caixa_baixo_so_avisa_quando_o_saldo_nao_cobre(conexao_de_teste):
    """Avisar "seu caixa cobre R$ 0,00" seria ruído que ensina a ignorar o sino."""
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    # Sem compromisso nenhum: não há alerta a dar.
    await semanal.executa(conexao_de_teste, hoje=HOJE)
    sem_conta = await _notificacoes(conexao_de_teste, usuario, "caixa_baixo")

    # Uma despesa grande e programada para a semana, com saldo zero.
    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id,
              efetivar_automaticamente, criado_por
            ) values (
              'digital', 'despesa', 'conta grande', 99999.00, :data, 'programado',
              :cat, false, cast(:u as uuid)
            )
            """),
        {"data": HOJE + timedelta(days=2), "cat": str(infra), "u": str(usuario.id)},
    )

    # Semana seguinte, para a chave de deduplicação ser outra.
    await semanal.executa(conexao_de_teste, hoje=HOJE + timedelta(days=7))
    com_conta = await _notificacoes(conexao_de_teste, usuario, "caixa_baixo")

    assert sem_conta == 0
    assert com_conta >= 1


async def test_a_diaria_dispara_a_semanal_na_segunda(conexao_de_teste):
    """`FR-098`: o plano gratuito só dá um cron por dia."""
    usuario = await _usuario(conexao_de_teste)
    segunda = HOJE - timedelta(days=HOJE.isoweekday() - 1)

    assert semanal.e_segunda(segunda) is True
    await diaria.executa(conexao_de_teste, hoje=segunda)
    assert await _notificacoes(conexao_de_teste, usuario, "resumo_semanal") == 1


async def test_o_resumo_cita_os_numeros_da_semana(conexao_de_teste):
    usuario = await _usuario(conexao_de_teste)
    infra = await _categoria(conexao_de_teste, "Infraestrutura")

    quinta = HOJE - timedelta(days=HOJE.isoweekday() + 3)
    await conexao_de_teste.execute(
        text("""
            insert into lancamentos (
              mundo, tipo, descricao, valor, data, status, categoria_id,
              efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
            ) values (
              'digital', 'despesa', 'da semana passada', 1234.00, :data, 'efetivado',
              :cat, true, now(), cast(:u as uuid), cast(:u as uuid)
            )
            """),
        {"data": quinta, "cat": str(infra), "u": str(usuario.id)},
    )

    await semanal.executa(conexao_de_teste, hoje=HOJE)
    corpo = (
        await conexao_de_teste.execute(
            text("""
                select corpo from notificacoes
                where usuario_id = :u and tipo = 'resumo_semanal'
                """),
            {"u": str(usuario.id)},
        )
    ).scalar_one()

    assert "1.234,00" in corpo, f"O resumo não citou o valor da semana: {corpo}"
    assert Decimal("1234.00")  # sanidade do valor usado acima
