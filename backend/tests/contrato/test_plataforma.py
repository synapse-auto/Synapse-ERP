"""Contrato da plataforma — contracts/plataforma.md §1 a §6, mais busca e importação.

Fecha a conferência de que **todo** endpoint acordado existe no `/api/docs` e declara o
papel. É o teste que T208 vai repetir no fim, e existir agora significa que a divergência
aparece no commit em que nasce, não na conferência final.

Tarefa: T139
"""

import pytest

from app.notificacoes import servico as servico_notificacoes

pytestmark = pytest.mark.contrato

ENDPOINTS_ACORDADOS = [
    # §1 sessão
    ("get", "/api/sessao"),
    ("post", "/api/sessao/preferencias"),
    # §2 usuários
    ("get", "/api/usuarios"),
    ("post", "/api/usuarios"),
    ("put", "/api/usuarios/{usuario_id}"),
    ("post", "/api/usuarios/{usuario_id}/desativar"),
    ("post", "/api/usuarios/{usuario_id}/reativar"),
    # §3 configurações
    ("get", "/api/configuracoes"),
    ("put", "/api/configuracoes"),
    # §4 notificações
    ("get", "/api/notificacoes"),
    ("post", "/api/notificacoes/{notificacao_id}/marcar-lida"),
    ("post", "/api/notificacoes/marcar-todas-lidas"),
    # §5 auditoria
    ("get", "/api/auditoria"),
    # §6 rotinas
    ("post", "/api/rotinas/diaria"),
    ("get", "/api/rotinas/diaria"),
    ("post", "/api/rotinas/semanal"),
    ("get", "/api/rotinas/estado"),
    # consultas §4 — busca global
    ("get", "/api/busca"),
    # lancamentos §6 — importação e exportação completa
    ("post", "/api/importacoes"),
    ("post", "/api/importacoes/{importacao_id}/mapeamento"),
    ("post", "/api/importacoes/{importacao_id}/confirmar"),
    ("post", "/api/exportacoes/completa"),
]


@pytest.fixture
def openapi(cliente) -> dict:
    return cliente.get("/api/openapi.json").json()


@pytest.mark.parametrize(("metodo", "caminho"), ENDPOINTS_ACORDADOS)
def test_endpoint_do_contrato_existe_na_api(openapi, metodo, caminho):
    assert caminho in openapi["paths"], f"{caminho} está em contracts/ e não existe na API."
    assert metodo in openapi["paths"][caminho], f"{metodo.upper()} {caminho} não existe na API."


def test_nao_existe_delete_de_usuario(openapi):
    """contracts §2: usuário desativado precisa existir para a auditoria (`RF-03`)."""
    assert "delete" not in openapi["paths"].get("/api/usuarios/{usuario_id}", {})


def test_nao_existe_post_de_notificacao(openapi):
    """contracts §4: notificação é gerada pelas rotinas, nunca por usuário."""
    assert "post" not in openapi["paths"]["/api/notificacoes"]


def test_auditoria_e_somente_leitura(openapi):
    """contracts §5: não há escrita nem exclusão pela API."""
    metodos = set(openapi["paths"]["/api/auditoria"])
    assert metodos == {"get"}


def test_configuracoes_le_para_operador_e_grava_so_para_gestor(openapi):
    """A tela precisa dos limites e rótulos para montar (`RNF-02`)."""
    leitura = openapi["paths"]["/api/configuracoes"]["get"]["description"].lower()
    escrita = openapi["paths"]["/api/configuracoes"]["put"]["description"].lower()
    assert "operador" in leitura
    assert "gestor" in escrita and "operador" not in escrita


def test_marcar_todas_vem_antes_da_rota_com_id(cliente):
    """`marcar-todas-lidas` não pode ser lido como um id (ordem de registro)."""
    resposta = cliente.post("/api/notificacoes/marcar-todas-lidas")
    assert resposta.json()["erro"]["codigo"] == "nao_autenticado"


def test_busca_com_menos_de_dois_caracteres_nao_varre_a_base(cliente):
    """`FR-046`. Uma letra casa com quase tudo — resultado inútil e caro."""
    from app.busca.rotas import MINIMO_DE_CARACTERES

    assert MINIMO_DE_CARACTERES == 2


# ── As quatro chaves de deduplicação (data-model §3.16) ────────────────────


def test_chaves_de_deduplicacao_seguem_o_formato_do_modelo():
    """Sem elas, a rotina rodando duas vezes duplicaria o mesmo aviso."""
    from datetime import date

    quando = date(2026, 7, 30)  # quinta da semana ISO 31

    assert servico_notificacoes.chave_de_vencimento("abc", 3) == "vencimento:abc:3"
    assert (
        servico_notificacoes.chave_de_inadimplencia("cli", quando) == "inadimplencia:cli:2026-07-30"
    )
    assert servico_notificacoes.chave_de_resumo_semanal(quando) == "resumo_semanal:2026-W31"
    assert (
        servico_notificacoes.chave_de_caixa_baixo("digital", quando)
        == "caixa_baixo:digital:2026-W31"
    )


def test_a_antecedencia_faz_parte_da_chave_de_vencimento():
    """ "Vence em 7" e "vence em 3" são avisos diferentes do mesmo lançamento."""
    assert servico_notificacoes.chave_de_vencimento("abc", 7) != (
        servico_notificacoes.chave_de_vencimento("abc", 3)
    )


def test_resumo_semanal_e_o_mesmo_para_qualquer_dia_da_semana():
    """Idempotência por semana ISO: rodar cinco vezes na segunda dá um resumo só."""
    from datetime import date

    segunda = date(2026, 7, 27)
    domingo = date(2026, 8, 2)
    assert servico_notificacoes.chave_de_resumo_semanal(segunda) == (
        servico_notificacoes.chave_de_resumo_semanal(domingo)
    )


# ── Importação ─────────────────────────────────────────────────────────────


def test_leitor_de_csv_reconhece_formato_brasileiro():
    from app.importacao import csv as leitor

    assert leitor.converte_valor("R$ 1.234,56") == __import__("decimal").Decimal("1234.56")
    assert leitor.converte_valor("-1.234,56") == __import__("decimal").Decimal("-1234.56")
    assert leitor.converte_valor("1234.56") == __import__("decimal").Decimal("1234.56")


def test_data_ambigua_e_lida_como_brasileira():
    """`01/02/2026` é 1º de fevereiro aqui. Trocar isso produz fechamento errado."""
    from datetime import date

    from app.importacao import csv as leitor

    assert leitor.converte_data("01/02/2026") == date(2026, 2, 1)
    assert leitor.converte_data("2026-02-01") == date(2026, 2, 1)
    assert leitor.converte_data("não é data") is None


def test_leitura_de_csv_detecta_separador_e_sugere_colunas():
    from app.importacao import csv as leitor

    arquivo = (
        "Data;Histórico;Valor\r\n"
        "10/07/2026;Mensalidade CRM;2.000,00\r\n"
        "11/07/2026;Servidor;-500,00\r\n"
    ).encode()

    leitura = leitor.le(arquivo)
    assert leitura.separador == ";"
    assert leitura.total_de_linhas == 2
    assert leitura.sugestoes["data"] == "Data"
    assert leitura.sugestoes["descricao"] == "Histórico"
    assert leitura.sugestoes["valor"] == "Valor"


def test_csv_em_cp1252_nao_quebra_acento():
    """Extrato de banco brasileiro ainda vem assim."""
    from app.importacao import csv as leitor

    arquivo = "Data;Histórico;Valor\r\n10/07/2026;Manutenção;100,00\r\n".encode("cp1252")
    leitura = leitor.le(arquivo)
    assert leitura.linhas[0]["Histórico"] == "Manutenção"


def test_mapeamento_acumula_todos_os_problemas_da_linha():
    """Parar no primeiro erro faria o usuário reenviar o arquivo dez vezes."""
    from app.importacao import mapeamento as mod

    mapeadas = mod.mapeia(
        [{"d": "data ruim", "h": "", "v": "xyz"}],
        mapa={"data": "d", "descricao": "h", "valor": "v"},
        categorias_por_nome={},
    )
    assert len(mapeadas[0].problemas) == 3


def test_sinal_do_extrato_vira_tipo_e_o_valor_fica_positivo():
    """`RN-02`: valor sempre positivo, o sinal vem de `tipo`."""
    from app.importacao import mapeamento as mod

    mapeadas = mod.mapeia(
        [
            {"d": "10/07/2026", "h": "Mensalidade", "v": "2.000,00"},
            {"d": "11/07/2026", "h": "Servidor", "v": "-500,00"},
        ],
        mapa={"data": "d", "descricao": "h", "valor": "v"},
        categorias_por_nome={},
    )
    assert mapeadas[0].tipo == "receita"
    assert mapeadas[1].tipo == "despesa"
    assert mapeadas[1].como_dicionario()["valor"] == "500.00"


def test_categoria_desconhecida_e_apontada_e_nao_criada():
    from app.importacao import mapeamento as mod

    mapeadas = mod.mapeia(
        [{"d": "10/07/2026", "h": "Anúncio", "v": "100,00", "c": "Marketing Digital"}],
        mapa={"data": "d", "descricao": "h", "valor": "v", "categoria": "c"},
        categorias_por_nome={"marketing": "id-existente"},
    )
    assert not mapeadas[0].valida
    assert "não cria categoria" in " ".join(mapeadas[0].problemas)

    resumo = mod.resumo(mapeadas)
    assert resumo["categorias_nao_reconhecidas"] == ["Marketing Digital"]


def test_ofx_e_lido_sem_dependencia_externa():
    """A troca declarada: regex sobre `<STMTTRN>` em vez de ofxparse (lxml + bs4)."""
    from app.importacao import ofx

    arquivo = (
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260710120000[-3:BRT]"
        "<TRNAMT>-500.00<FITID>001<MEMO>Servidor de produção</STMTTRN>"
        "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260711<TRNAMT>2000.00"
        "<FITID>002<NAME>Mensalidade</STMTTRN>"
        "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
    ).encode()

    leitura = ofx.le(arquivo)
    assert leitura.total_de_linhas == 2
    assert leitura.linhas[0]["data"] == "2026-07-10"
    assert leitura.linhas[0]["descricao"] == "Servidor de produção"
    assert leitura.linhas[0]["valor"] == "-500.00"
    # Sem MEMO, cai no NAME.
    assert leitura.linhas[1]["descricao"] == "Mensalidade"
    # OFX já vem estruturado: o mapeamento chega preenchido.
    assert leitura.sugestoes["data"] == "data"


def test_ofx_sem_transacao_explica_a_saida():
    import pytest as _pytest

    from app.comum.erros import ErroValidacao
    from app.importacao import ofx

    with _pytest.raises(ErroValidacao) as capturado:
        ofx.le(b"<OFX></OFX>")
    assert "CSV" in capturado.value.campos["arquivo"]


# ── Exportação completa ────────────────────────────────────────────────────


def test_exportacao_completa_cobre_as_19_tabelas():
    """`FR-112`: é a cópia que sai da empresa — faltar tabela a torna inútil."""
    from app.relatorios import exportacao_completa

    assert len(exportacao_completa.TABELAS) == 19


def test_exportacao_completa_omite_preferencias_do_usuario():
    """Arranjo de cards não é dado financeiro e não precisa sair da empresa."""
    from app.relatorios import exportacao_completa

    assert "preferencias" in exportacao_completa.COLUNAS_OMITIDAS["usuarios"]
