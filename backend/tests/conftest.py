"""Configuração dos testes — quickstart.md §6.

Duas famílias, separadas de propósito:

- **Sem marca** — unidade. Não tocam banco nem rede. É o que roda sempre, e onde
  vivem os 6 alvos obrigatórios da constituição (Princípio VI), porque regra de
  negócio testada contra banco real é teste lento que ninguém roda.
- **`@pytest.mark.integracao`** — precisa de um Postgres de teste. Sem
  `DATABASE_URL_TESTE` no ambiente, são **puladas com aviso**, nunca silenciosamente
  aprovadas: reportar "tudo passou" quando parte nem rodou é o que a constituição
  proíbe.

⚠️ **`DATABASE_URL_TESTE` nunca aponta para o banco de produção.** As integrações
gravam e apagam. O `conftest` recusa uma URL que seja igual à `DATABASE_URL`.

Tarefa: T036
"""

import os
from collections.abc import AsyncIterator, Iterator

import pytest

# Ambiente mínimo, definido ANTES de qualquer import de `app`: `app.config` valida
# na construção, então importar sem isso quebraria a coleta dos testes de unidade —
# que não precisam de banco nenhum.
os.environ.setdefault("DATABASE_URL", "postgresql://teste:teste@localhost:5432/synapse_teste")
os.environ.setdefault("SUPABASE_URL", "https://projeto-de-teste.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "chave-de-teste-nao-usada")
os.environ.setdefault("SEGREDO_ROTINA", "segredo-de-teste")
os.environ.setdefault("AMBIENTE", "local")


@pytest.fixture(autouse=True)
def _limpa_estado_entre_testes() -> Iterator[None]:
    """Zera o que é global no processo, para um teste não influenciar o seguinte."""
    from app.comum.idempotencia import limpa_memoria
    from app.config import obter_configuracao

    obter_configuracao.cache_clear()
    limpa_memoria()
    yield
    limpa_memoria()


@pytest.fixture
def cliente() -> Iterator[object]:
    """Cliente HTTP contra o app, sem subir servidor.

    Os endpoints que dependem de banco não funcionam aqui — para esses existe a
    marca `integracao`. Serve a tratamento de erro, formato de resposta e OpenAPI.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as instancia:
        yield instancia


@pytest.fixture
async def conexao_de_teste() -> AsyncIterator[object]:
    """Conexão com o Postgres de teste, em transação desfeita no fim.

    O `rollback` no final é o que permite rodar a suíte quantas vezes quiser sem o
    banco acumular lixo entre execuções.
    """
    url_teste = os.environ.get("DATABASE_URL_TESTE")
    if not url_teste:
        pytest.skip(
            "DATABASE_URL_TESTE não definida — teste de integração pulado. "
            "Aponte para um Postgres de teste (quickstart.md §6)."
        )

    if url_teste == os.environ.get("DATABASE_URL"):
        pytest.fail(
            "DATABASE_URL_TESTE é igual a DATABASE_URL. Os testes de integração "
            "gravam e apagam — aponte para um banco separado."
        )

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.db import _normaliza_url

    url, exige_tls = _normaliza_url(url_teste)
    motor = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "ssl": "require" if exige_tls else None,
        },
    )
    try:
        async with motor.connect() as conexao:
            transacao = await conexao.begin()
            try:
                yield conexao
            finally:
                await transacao.rollback()
    finally:
        await motor.dispose()
