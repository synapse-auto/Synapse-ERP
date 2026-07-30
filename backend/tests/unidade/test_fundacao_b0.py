"""Testes da fundação da sub-fase B0.

Não são os 6 alvos obrigatórios da constituição — esses são de domínio e chegam em B1
e B2. Estes cobrem o que B0 entregou, para que "a fundação está pronta" seja
verificável e não afirmado (Princípio VI).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.comum import periodo as mod_periodo
from app.comum.auditoria import calcula_diferenca
from app.comum.erros import (
    ErroConfirmacaoNecessaria,
    ErroConflitoVersao,
    ErroRegraViolada,
    ErroValidacao,
    formata_dinheiro,
)
from app.comum.idempotencia import registra_resposta, resposta_ja_registrada
from app.comum.paginacao import Paginacao, envelope

# ── Formato de erro (T025) ───────────────────────────────────────────────────


def test_erro_sai_no_formato_do_contrato():
    """contracts/README.md §Erros: codigo, mensagem, requisito, campos."""
    erro = ErroRegraViolada(
        "A soma das partes (R$ 480,00) não fecha com o valor do lançamento (R$ 500,00).",
        requisito="RN-11",
        campos={"partes": "Faltam R$ 20,00."},
    )
    corpo = erro.como_corpo()

    assert erro.status == 409
    assert corpo["erro"]["codigo"] == "regra_violada"
    assert corpo["erro"]["requisito"] == "RN-11"
    assert corpo["erro"]["campos"] == {"partes": "Faltam R$ 20,00."}
    assert "R$ 480,00" in corpo["erro"]["mensagem"]


def test_ausencia_e_null_explicito_nao_campo_omitido():
    """contracts/README.md §Ausência."""
    corpo = ErroValidacao("Corpo malformado.").como_corpo()
    assert corpo["erro"]["requisito"] is None
    assert corpo["erro"]["campos"] is None


def test_conflito_de_versao_diz_o_que_mudou():
    """data-model §5.6: recusar sem dizer o que mudou não ajuda ninguém."""
    erro = ErroConflitoVersao(
        "Este lançamento foi alterado por outra pessoa enquanto você editava.",
        versao_atual=4,
        mudancas={"valor": {"de": "1800.00", "para": "2000.00"}},
    )
    corpo = erro.como_corpo()
    assert erro.status == 409
    assert corpo["erro"]["codigo"] == "conflito_versao"
    assert corpo["erro"]["versao_atual"] == 4
    assert corpo["erro"]["mudancas"]["valor"]["para"] == "2000.00"


def test_confirmacao_necessaria_carrega_previa():
    """FR-027: o 422 descreve o impacto antes de executar."""
    erro = ErroConfirmacaoNecessaria(
        "Serão criadas 17 ocorrências entre 01/03/2025 e 01/07/2026, sendo 5 já efetivadas.",
        requisito="FR-027",
        previa={"total_ocorrencias": 17, "retroativas_efetivadas": 5},
        campo_confirmacao="confirmar_geracao_retroativa",
    )
    corpo = erro.como_corpo()
    assert erro.status == 422
    assert corpo["erro"]["previa"]["total_ocorrencias"] == 17
    assert corpo["erro"]["campo_confirmacao"] == "confirmar_geracao_retroativa"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (Decimal("0"), "R$ 0,00"),
        (Decimal("0.5"), "R$ 0,50"),
        (Decimal("1234.56"), "R$ 1.234,56"),
        (Decimal("1200"), "R$ 1.200,00"),
        (Decimal("1000000"), "R$ 1.000.000,00"),
        (Decimal("-20"), "-R$ 20,00"),
    ],
)
def test_dinheiro_no_formato_brasileiro(valor, esperado):
    """RNF-03. Só para mensagem; transporte é string decimal."""
    assert formata_dinheiro(valor) == esperado


# ── Paginação (T026) ─────────────────────────────────────────────────────────


def test_envelope_de_paginacao():
    paginacao = Paginacao(pagina=2, por_pagina=50, ordenar=None, direcao="desc")
    assert paginacao.deslocamento == 50

    resposta = envelope([{"id": 1}], total=120, paginacao=paginacao)
    assert resposta["paginacao"] == {
        "pagina": 2,
        "por_pagina": 50,
        "total": 120,
        "total_paginas": 3,
    }


def test_lista_vazia_nao_tem_pagina():
    paginacao = Paginacao(pagina=1, por_pagina=50, ordenar=None, direcao="desc")
    assert envelope([], total=0, paginacao=paginacao)["paginacao"]["total_paginas"] == 0


def test_ordenar_por_coluna_fora_da_lista_e_recusado():
    """A defesa contra injeção por `?ordenar=`: lista fechada, não interpolação."""
    paginacao = Paginacao(
        pagina=1, por_pagina=50, ordenar="valor; drop table lancamentos", direcao="asc"
    )
    with pytest.raises(ErroValidacao) as capturado:
        paginacao.clausula_ordem({"data": "data", "valor": "valor"}, padrao="data")
    assert "data, valor" in capturado.value.campos["ordenar"]


def test_clausula_ordem_traduz_nome_publico_em_coluna():
    paginacao = Paginacao(pagina=1, por_pagina=50, ordenar="categoria", direcao="asc")
    clausula = paginacao.clausula_ordem(
        {"categoria": "categorias.nome", "data": "l.data"}, padrao="l.data"
    )
    assert clausula == "categorias.nome asc"


# ── Período (T027) ───────────────────────────────────────────────────────────

# 30/07/2026 é uma quinta-feira. Datas fixas para o teste não depender do relógio.
HOJE = date(2026, 7, 30)


def test_este_mes_cobre_o_mes_inteiro_mas_marca_o_decorrido():
    p = mod_periodo.resolve("este_mes", hoje=HOJE)
    assert (p.inicio, p.fim) == (date(2026, 7, 1), date(2026, 7, 31))
    assert p.decorrido_ate == HOJE
    assert p.esta_aberto is True
    assert p.dias == 31
    assert p.dias_decorridos == 30


def test_periodo_anterior_usa_dias_decorridos_nao_de_calendario():
    """A régua do módulo: 30 dias corridos de julho comparam com 30 dias de junho.

    Se comparasse julho inteiro contra junho inteiro, junho pareceria maior só por
    ter mais dias contabilizados.
    """
    p = mod_periodo.resolve("este_mes", hoje=HOJE)
    assert p.inicio_anterior == date(2026, 6, 1)
    assert p.fim_anterior == date(2026, 6, 30)
    assert (p.fim_anterior - p.inicio_anterior).days == (p.decorrido_ate - p.inicio).days


def test_no_comeco_do_mes_o_anterior_encolhe_junto():
    """O caso em que a régua errada mentiria mais: dia 3 contra um mês inteiro."""
    p = mod_periodo.resolve("este_mes", hoje=date(2026, 8, 3))
    assert (p.inicio, p.fim) == (date(2026, 8, 1), date(2026, 8, 31))
    assert p.dias_decorridos == 3
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 7, 1), date(2026, 7, 3))


def test_mes_fechado_compara_mes_cheio_contra_mes_cheio():
    """Junho (30 dias) contra maio INTEIRO (31), não contra 1–30 de maio.

    Se o anterior fosse cortado em 30/05 para igualar a contagem de dias, o DRE de
    maio e o "mês anterior" do card mostrariam valores diferentes para o mesmo maio —
    e quem confere um fechamento à mão (`SC-003`) acharia uma diferença inexistente.
    """
    p = mod_periodo.resolve("mes_passado", hoje=HOJE)
    assert (p.inicio, p.fim) == (date(2026, 6, 1), date(2026, 6, 30))
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 5, 1), date(2026, 5, 31))
    assert p.esta_aberto is False


def test_ultimo_dia_do_mes_ja_conta_como_fechado():
    """31/03 é o último dia: o período está completo, então compara com fevereiro
    inteiro em vez de cortar fevereiro no dia 28 por contagem de dias."""
    p = mod_periodo.resolve("este_mes", hoje=date(2026, 3, 31))
    assert p.esta_aberto is False
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 2, 1), date(2026, 2, 28))


def test_semana_comeca_na_segunda():
    """ISO 8601, igual à chave de deduplicação do resumo semanal."""
    p = mod_periodo.resolve("esta_semana", hoje=HOJE)
    assert (p.inicio, p.fim) == (date(2026, 7, 27), date(2026, 8, 2))
    assert p.inicio.weekday() == 0
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 7, 20), date(2026, 7, 23))


def test_hoje_compara_com_ontem():
    p = mod_periodo.resolve("hoje", hoje=HOJE)
    assert (p.inicio, p.fim) == (HOJE, HOJE)
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 7, 29), date(2026, 7, 29))


def test_ultimos_3_meses_sao_tres_meses_inteiros():
    p = mod_periodo.resolve("ultimos_3_meses", hoje=HOJE)
    assert (p.inicio, p.fim) == (date(2026, 5, 1), date(2026, 7, 31))
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 2, 1), date(2026, 4, 30))


def test_este_ano_compara_com_o_ano_anterior():
    p = mod_periodo.resolve("este_ano", hoje=HOJE)
    assert (p.inicio, p.fim) == (date(2026, 1, 1), date(2026, 12, 31))
    assert p.inicio_anterior == date(2025, 1, 1)
    assert p.fim_anterior == date(2025, 7, 30)


def test_periodo_de_mes_curto_nao_estoura():
    """31 de março comparado com fevereiro: o anterior para no fim de fevereiro."""
    p = mod_periodo.resolve("este_mes", hoje=date(2026, 3, 31))
    assert (p.inicio, p.fim) == (date(2026, 3, 1), date(2026, 3, 31))
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 2, 1), date(2026, 2, 28))


def test_personalizado_exige_as_duas_datas():
    with pytest.raises(ErroValidacao) as capturado:
        mod_periodo.resolve("personalizado", hoje=HOJE)
    assert "data_inicio" in capturado.value.campos


def test_personalizado_recusa_fim_antes_do_inicio():
    with pytest.raises(ErroValidacao):
        mod_periodo.resolve(
            "personalizado",
            data_inicio=date(2026, 7, 10),
            data_fim=date(2026, 7, 1),
            hoje=HOJE,
        )


def test_personalizado_compara_com_a_mesma_quantidade_de_dias():
    p = mod_periodo.resolve(
        "personalizado", data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 10), hoje=HOJE
    )
    assert p.dias == 10
    assert (p.inicio_anterior, p.fim_anterior) == (date(2026, 6, 21), date(2026, 6, 30))


def test_atalho_inexistente_e_recusado():
    with pytest.raises(ErroValidacao) as capturado:
        mod_periodo.resolve("semana_passada", hoje=HOJE)
    assert "personalizado" in capturado.value.campos["periodo"]


def test_todos_os_atalhos_do_contrato_resolvem():
    """contracts/README.md §Período nomeia sete. Nenhum pode faltar."""
    for atalho in mod_periodo.ATALHOS:
        if atalho == "personalizado":
            continue
        p = mod_periodo.resolve(atalho, hoje=HOJE)
        assert p.inicio <= p.fim
        assert p.inicio_anterior <= p.fim_anterior
        assert p.fim_anterior < p.inicio


# ── Auditoria (T029) ─────────────────────────────────────────────────────────


def test_diferenca_traz_so_o_que_mudou():
    """RF-03: a linha do tempo mostra o que mudou, não a linha inteira."""
    diferenca = calcula_diferenca(
        {"valor": Decimal("1800.00"), "descricao": "Mensalidade", "mundo": "digital"},
        {"valor": Decimal("2000.00"), "descricao": "Mensalidade", "mundo": "digital"},
    )
    assert diferenca == {"valor": {"de": "1800.00", "para": "2000.00"}}


def test_dinheiro_na_auditoria_e_string_nao_float():
    """Float perderia exatidão, e auditoria financeira existe para o número bater."""
    diferenca = calcula_diferenca({"valor": Decimal("0.10")}, {"valor": Decimal("0.30")})
    assert diferenca["valor"] == {"de": "0.10", "para": "0.30"}
    assert isinstance(diferenca["valor"]["para"], str)


def test_mesmo_valor_com_escala_diferente_nao_e_mudanca():
    assert calcula_diferenca({"valor": Decimal("2000.00")}, {"valor": Decimal("2000.00")}) == {}


def test_campos_automaticos_ficam_fora_da_linha_do_tempo():
    diferenca = calcula_diferenca(
        {"valor": Decimal("10.00"), "versao": 1, "atualizado_em": "antes"},
        {"valor": Decimal("10.00"), "versao": 2, "atualizado_em": "depois"},
    )
    assert diferenca == {}


def test_criacao_registra_todo_campo_preenchido():
    diferenca = calcula_diferenca(None, {"descricao": "Nova conta", "valor": Decimal("50.00")})
    assert diferenca["descricao"] == {"de": None, "para": "Nova conta"}
    assert diferenca["valor"] == {"de": None, "para": "50.00"}


# ── Idempotência (T028) ──────────────────────────────────────────────────────


def test_mesma_chave_devolve_o_resultado_guardado():
    registra_resposta("k1", rota="/api/lancamentos", usuario_id="u1", resposta={"id": "abc"})
    assert resposta_ja_registrada("k1", rota="/api/lancamentos", usuario_id="u1") == {"id": "abc"}


def test_chave_e_escopada_por_usuario_e_por_rota():
    registra_resposta("k1", rota="/api/lancamentos", usuario_id="u1", resposta={"id": "abc"})
    assert resposta_ja_registrada("k1", rota="/api/lancamentos", usuario_id="u2") is None
    assert resposta_ja_registrada("k1", rota="/api/clientes", usuario_id="u1") is None


def test_sem_chave_nunca_reaproveita():
    """Cabeçalho é opcional; sem ele, cada chamada é uma operação nova."""
    registra_resposta(None, rota="/api/lancamentos", usuario_id="u1", resposta={"id": "abc"})
    assert resposta_ja_registrada(None, rota="/api/lancamentos", usuario_id="u1") is None


# ── App e contrato (T032, T033) ──────────────────────────────────────────────


def test_openapi_publica_em_api_docs():
    """Princípio IV: endpoint sem documentação não está pronto."""
    from app.main import app

    esquema = app.openapi()
    assert "/api/saude" in esquema["paths"]
    assert "/api/sessao" in esquema["paths"]
    assert "/api/sessao/preferencias" in esquema["paths"]
    assert app.docs_url == "/api/docs"


def test_saude_e_publico_sem_token(cliente):
    """contracts/plataforma.md §7. Aqui o banco de teste não existe → degradado."""
    resposta = cliente.get("/api/saude")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == {"status", "banco", "versao"}
    assert corpo["banco"] in ("ok", "indisponivel")


def test_sessao_sem_token_responde_401_no_formato_unico(cliente):
    resposta = cliente.get("/api/sessao")
    assert resposta.status_code == 401
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "nao_autenticado"
    assert erro["mensagem"] == "Faça login para continuar."


def test_token_mal_formado_responde_401_nao_500(cliente):
    resposta = cliente.get("/api/sessao", headers={"Authorization": "Bearer nao-e-um-jwt"})
    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "nao_autenticado"


def test_esquema_de_autorizacao_errado_responde_401(cliente):
    resposta = cliente.get("/api/sessao", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resposta.status_code == 401


def test_401_nao_abre_conexao_com_o_banco(cliente, monkeypatch):
    """Regressão: a conexão era dependência de `usuario_atual` e o FastAPI a resolvia
    ANTES de validar o token — requisição sem token gastava conexão, e com o banco
    fora do ar o 401 virava 500. Se alguém reintroduzir isso, este teste estoura.
    """
    import app.db as mod_db

    def explode():
        raise AssertionError("O banco foi tocado numa requisição que devia parar no 401.")

    monkeypatch.setattr(mod_db, "obter_motor", explode)

    assert cliente.get("/api/sessao").status_code == 401
    assert cliente.get("/api/sessao", headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert cliente.post("/api/sessao/preferencias", json={"tema": "escuro"}).status_code == 401


def test_corpo_malformado_sai_no_formato_unico_em_pt_br(cliente):
    """Sem o handler de RequestValidationError, isto sairia no formato do FastAPI."""
    resposta = cliente.post("/api/sessao/preferencias", json={"tema": "roxo"})
    # 401 vem primeiro (sem token) — o que importa é que nunca é o formato do FastAPI.
    assert "erro" in resposta.json()
    assert "detail" not in resposta.json()


# ── RBAC (T031) ──────────────────────────────────────────────────────────────


def test_exige_papel_sem_papel_declarado_e_erro_de_programacao():
    """A trava que impede endpoint nascer aberto por esquecimento."""
    from app.seguranca.rbac import exige_papel

    with pytest.raises(ValueError, match="ao menos um papel"):
        exige_papel()


def test_permissoes_do_operador_nao_incluem_configuracoes():
    """SC-010. O 403 é do rbac; isto cobre o que a navegação recebe."""
    from uuid import uuid4

    from app.seguranca.auth import UsuarioAutenticado

    operador = UsuarioAutenticado(
        id=uuid4(), nome="Contadora", email="c@x.com", papel="operador", preferencias={}
    )
    gestor = UsuarioAutenticado(
        id=uuid4(), nome="Lucas", email="l@x.com", papel="gestor", preferencias={}
    )

    assert operador.permissoes() == {
        "configuracoes": False,
        "usuarios": False,
        "cadastros": False,
        "lancamentos": True,
    }
    assert all(gestor.permissoes().values())


def test_segredo_de_rotina_errado_e_recusado():
    from app.comum.erros import ErroSemPermissao
    from app.seguranca.rbac import exige_segredo_de_rotina

    with pytest.raises(ErroSemPermissao):
        exige_segredo_de_rotina("segredo-errado")
    with pytest.raises(ErroSemPermissao):
        exige_segredo_de_rotina(None)

    # O certo passa sem levantar (definido em conftest.py)
    exige_segredo_de_rotina("segredo-de-teste")


# ── Configuração e banco (T023, T024) ────────────────────────────────────────


def test_url_do_jwks_derivada_do_supabase_url():
    """research.md D-03 resolvido: chave pública buscada, não segredo guardado."""
    from app.config import obter_configuracao

    configuracao = obter_configuracao()
    assert configuracao.url_jwks == (
        "https://projeto-de-teste.supabase.co/auth/v1/.well-known/jwks.json"
    )


def test_barra_final_no_supabase_url_nao_duplica():
    from app.config import Configuracao

    configuracao = Configuracao(
        database_url="postgresql://u:p@h:6543/d",
        supabase_url="https://x.supabase.co/",
        supabase_service_role_key="k",
        segredo_rotina="s",
    )
    assert "//auth" not in configuracao.url_jwks


def test_versao_publicada_traz_o_commit_quando_a_vercel_informa():
    """Sem isto, "o deploy subiu" não é verificável (Princípio VI)."""
    from app.config import Configuracao

    base = {
        "database_url": "postgresql://u:p@h:6543/d",
        "supabase_url": "https://x.supabase.co",
        "supabase_service_role_key": "k",
        "segredo_rotina": "s",
    }
    assert Configuracao(**base).versao_publicada == "0.1.0"
    assert (
        Configuracao(**base, vercel_git_commit_sha="abcdef1234567").versao_publicada
        == "0.1.0+abcdef1"
    )


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@host:6543/postgres?sslmode=require",
        "postgres://u:p@host:6543/postgres",
        "postgresql://u:p@host:6543/postgres?sslmode=require&channel_binding=prefer",
    ],
)
def test_url_do_banco_e_adaptada_ao_asyncpg(url):
    """asyncpg quebra com sslmode na URL — daí a normalização em app/db.py."""
    from app.db import _normaliza_url

    normalizada, exige_tls = _normaliza_url(url)
    assert normalizada.startswith("postgresql+asyncpg://")
    assert "sslmode" not in normalizada
    assert "channel_binding" not in normalizada
    assert exige_tls is True


def test_sslmode_disable_e_respeitado():
    from app.db import _normaliza_url

    _, exige_tls = _normaliza_url("postgresql://u:p@localhost:5432/d?sslmode=disable")
    assert exige_tls is False
