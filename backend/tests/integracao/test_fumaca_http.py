"""Toda leitura da API responde de verdade, pela porta HTTP. Contra Postgres real.

## Por que este arquivo existe

Dois bugs chegaram a produção ao mesmo tempo e nenhum teste os viu (2026-08-02):

1. **`operator does not exist: text %% unknown`** — o SQL escrevia `%%` para escapar o
   percent do paramstyle `pyformat`. O dialeto **asyncpg** usa parâmetro numerado
   (`$1`) e não desescapa nada, então o par ia literal ao Postgres. Derrubava toda
   busca por texto: `/api/busca`, `/api/lancamentos?busca=` e `/api/clientes?busca=`.
2. **`'dict' object has no attribute 'encode'`** — os quatro relatórios declaram
   `response_class=Response` para poderem devolver CSV e PDF, e devolviam o `dict` do
   formato `json`. O Starlette chamava `.encode()` nele. Derrubava a tela de
   Relatórios inteira.

Os testes que havia não podiam pegar nenhum dos dois: os de contrato leem o OpenAPI e
exercitam os exportadores em memória — **nunca executam o endpoint** —, e os de
integração chamam a função da rota direto, o que pula a serialização da resposta.

O buraco, então, não era de asserção: era de **caminho percorrido**. Este arquivo fecha
esse buraco pelo único jeito que fecha — subindo a requisição pela pilha inteira
(roteamento, dependência, SQL, serialização) e afirmando o mínimo: nenhuma leitura
responde 5xx.

## Como roda

`httpx.ASGITransport` fala com o app no **mesmo laço de eventos** do teste. Isso
importa: o `TestClient` roda o app num laço próprio, e a conexão asyncpg da fixture,
criada no laço do pytest, não sobrevive à travessia.

⚠️ Contra o banco de **produção**, como o resto de `tests/integracao` — o `rollback` da
fixture é o que protege. Quase tudo aqui é `GET`; as duas exceções criam o próprio dado
(um cliente novo, um `POST` que tem de ser recusado) e nunca tocam linha que já existia,
que é a regra deste diretório.
"""

from collections.abc import AsyncIterator
from datetime import date
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import obter_conexao
from app.seguranca.auth import UsuarioAutenticado, usuario_atual

pytestmark = pytest.mark.integracao

# Uma entrada por leitura que a interface faz ao abrir cada tela, mais as três buscas
# por texto. `busca`/`q` levam um termo que casa com o acervo real por trigram; o que
# se afirma não é o resultado, é que a consulta **executa**.
LEITURAS = [
    "/api/saude",
    "/api/sessao",
    "/api/saldo",
    "/api/dashboard",
    "/api/extrato",
    "/api/lancamentos",
    "/api/lancamentos?busca=pagamento",
    "/api/lixeira",
    "/api/clientes",
    "/api/clientes?busca=synapse",
    "/api/categorias",
    "/api/funcionarios",
    "/api/servicos",
    "/api/centros-custo",
    "/api/tags",
    "/api/configuracoes",
    "/api/notificacoes",
    "/api/auditoria",
    "/api/recorrencias",
    "/api/usuarios",
    "/api/rotinas/estado",
    "/api/busca?q=pagamento",
    "/api/relatorios/dre",
    "/api/relatorios/clientes",
    "/api/relatorios/matriz-mensal",
    "/api/relatorios/variacao-categorias",
]

# Os quatro relatórios em cada formato que o contrato promete (contracts/consultas.md §3).
# `matriz-mensal` e `variacao-categorias` recusam PDF de propósito (`FR-094`), e a recusa
# é um `400` de validação — não entra aqui.
RELATORIOS_EM_ARQUIVO = [
    ("/api/relatorios/dre", "csv", "text/csv"),
    ("/api/relatorios/dre", "pdf", "application/pdf"),
    ("/api/relatorios/clientes", "csv", "text/csv"),
    ("/api/relatorios/clientes", "pdf", "application/pdf"),
    ("/api/relatorios/matriz-mensal", "csv", "text/csv"),
    ("/api/relatorios/variacao-categorias", "csv", "text/csv"),
]


@pytest.fixture
async def api(conexao_de_teste) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP contra o app, autenticado como gestor, na transação do teste."""
    from app.main import app

    gestor = UsuarioAutenticado(
        id=uuid4(),
        nome="Fumaça",
        email="fumaca@synapse.local",
        papel="gestor",
        preferencias={},
    )

    async def _conexao():
        yield conexao_de_teste

    app.dependency_overrides[usuario_atual] = lambda: gestor
    app.dependency_overrides[obter_conexao] = _conexao
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://teste"
        ) as instancia:
            yield instancia
    finally:
        app.dependency_overrides.pop(usuario_atual, None)
        app.dependency_overrides.pop(obter_conexao, None)


@pytest.mark.parametrize("caminho", LEITURAS)
async def test_leitura_nao_responde_erro_de_servidor(api, caminho):
    """`5xx` aqui é sempre defeito nosso: são todos `GET` sem corpo e sem parâmetro ruim."""
    resposta = await api.get(caminho)
    assert (
        resposta.status_code < 500
    ), f"GET {caminho} respondeu {resposta.status_code}. Corpo: {resposta.text[:400]}"
    assert resposta.status_code == 200, f"GET {caminho} respondeu {resposta.status_code}."


@pytest.mark.parametrize("caminho", LEITURAS)
async def test_leitura_devolve_json_utilizavel(api, caminho):
    """Um `200` que não vira JSON é o bug do `response_class` — o `.json()` é a asserção."""
    resposta = await api.get(caminho)
    assert resposta.headers["content-type"].startswith(
        "application/json"
    ), f"GET {caminho} respondeu {resposta.headers.get('content-type')}."
    resposta.json()


@pytest.mark.parametrize(("caminho", "formato", "tipo"), RELATORIOS_EM_ARQUIVO)
async def test_relatorio_em_arquivo_continua_saindo_como_arquivo(api, caminho, formato, tipo):
    """A correção do `json` não pode ter transformado CSV e PDF em JSON."""
    resposta = await api.get(caminho, params={"formato": formato})
    assert resposta.status_code == 200, f"{caminho}?formato={formato} → {resposta.status_code}"
    assert resposta.headers["content-type"].startswith(tipo)
    assert len(resposta.content) > 0


async def test_busca_por_texto_usa_o_operador_de_trigram(api):
    """Regressão do `%%`: o erro era `UndefinedFunctionError`, um `500` mudo.

    Afirma a forma da resposta, não o conteúdo — o acervo do banco muda.
    """
    corpo = (await api.get("/api/busca", params={"q": "pagamento"})).json()
    assert set(corpo) >= {"termo", "lancamentos", "clientes", "categorias"}
    assert isinstance(corpo["lancamentos"], list)


# ── Os dois perfis: o campo que a tela lê tem que existir ───────────────────
#
# Os quatro bugs de 2026-08-02 que a lista `LEITURAS` acima **não** pega são todos da
# mesma família: a resposta chega `200`, e o campo que a tela desenha não está lá — ou
# está com outra forma. Não dá para ver isso com `status < 500`; só afirmando o campo.
#
# `GET /api/categorias` não trazia `uso` nem `subcategorias`; `GET /api/extrato` mandava
# o rótulo do gráfico como `"05/08/2026"` em vez da data ISO; `GET /api/clientes/{id}`
# não trazia `lancamentos`. Cada um derrubava a tela correspondente inteira.


async def test_categoria_traz_uso_e_subcategorias(api):
    """contracts/cadastros.md §1 — a tela lê `c.uso.…` e `c.subcategorias.length`."""
    itens = (await api.get("/api/categorias")).json()["itens"]
    assert itens, "Sem categoria nenhuma não há o que afirmar. Aplique o seed."
    for categoria in itens:
        assert set(categoria["uso"]) == {"quantidade_lancamentos", "total_movimentado"}
        assert isinstance(categoria["subcategorias"], list)
        for filha in categoria["subcategorias"]:
            assert set(filha["uso"]) == {"quantidade_lancamentos", "total_movimentado"}


async def test_rotulo_do_grafico_do_extrato_e_data_iso(api):
    """contracts/consultas.md §2: ISO no gráfico, `dd/mm/aaaa` só no cabeçalho do grupo.

    A tela passa o rótulo do gráfico por um formatador de data; texto pronto ali vira
    `RangeError: Invalid time value` e derruba o Extrato.
    """
    corpo = (await api.get("/api/extrato")).json()
    for ponto in corpo["grafico"]:
        date.fromisoformat(ponto["rotulo"])  # levanta se não for ISO


async def test_perfil_do_cliente_traz_o_envelope_de_lancamentos(api, conexao_de_teste):
    """contracts/cadastros.md §3 promete `"lancamentos": {"itens": [], "paginacao": {}}`.

    Cria o próprio cliente — o banco pode não ter nenhum, e a regra deste diretório é
    nunca depender de linha que já estava lá. A transação do teste desfaz.
    """
    identificador = uuid4()
    await conexao_de_teste.execute(
        text("""
            insert into clientes (id, nome, empresa, tipo_cobranca)
            values (:id, 'Fumaça HTTP', 'QA', 'pontual')
            """),
        {"id": str(identificador)},
    )

    corpo = (await api.get(f"/api/clientes/{identificador}")).json()
    assert set(corpo["lancamentos"]) == {"itens", "paginacao"}
    assert isinstance(corpo["lancamentos"]["itens"], list)
    assert set(corpo["lancamentos"]["paginacao"]) == {
        "pagina",
        "por_pagina",
        "total",
        "total_paginas",
    }


async def test_perfil_do_funcionario_traz_pagamentos_como_lista(api, conexao_de_teste):
    """A tela faz `f.pagamentos.map(...)` e usa `lancamento_id` — não `.itens`, não `id`."""
    identificador = (
        await conexao_de_teste.execute(text("select id from funcionarios limit 1"))
    ).scalar_one_or_none()
    if identificador is None:
        pytest.skip("Nenhum funcionário no banco — nada a afirmar.")

    corpo = (await api.get(f"/api/funcionarios/{identificador}")).json()
    for campo in ("pagamentos", "proximos_pagamentos"):
        assert isinstance(corpo[campo], list), f"`{campo}` deixou de ser lista simples."
        for item in corpo[campo]:
            assert "lancamento_id" in item, f"`{campo}` sem `lancamento_id`."


async def test_enum_invalido_e_400_e_nao_500(api):
    """Valor fora do enum tem que morrer na borda, no formato único de erro.

    Sem o `Literal` no modelo, `tipo_cobranca: "avulso"` atravessava até o
    `cast(... as tipo_cobranca)` e o Postgres devolvia `InvalidTextRepresentationError`
    — um `500 erro_interno` onde contracts/README.md manda `400 validacao`.
    """
    resposta = await api.post("/api/clientes", json={"nome": "X", "tipo_cobranca": "avulso"})
    assert resposta.status_code == 400, f"respondeu {resposta.status_code}"
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "validacao"
    assert "tipo_cobranca" in (erro["campos"] or {})
