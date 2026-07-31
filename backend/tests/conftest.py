"""Configuração dos testes — quickstart.md §6.

Duas famílias, separadas de propósito:

- **Sem marca** — unidade e contrato. Não tocam banco nem rede. É o que roda sempre,
  e onde vivem os 6 alvos obrigatórios da constituição (Princípio VI), porque regra
  de negócio testada contra banco real é teste lento que ninguém roda.
- **`@pytest.mark.integracao`** — usa o `DATABASE_URL`. Sem ele no ambiente, são
  **puladas com aviso**, nunca silenciosamente aprovadas: reportar "tudo passou"
  quando parte nem rodou é o que a constituição proíbe.

## ⚠️ Os testes de integração rodam contra o banco de PRODUÇÃO

Decisão do dono do projeto (2026-07-31): não haverá banco separado para teste. Não
é o arranjo usual, e por isso a proteção precisa estar escrita onde não dá para
ignorar.

**O que protege os dados é a transação desfeita.** Cada teste roda dentro de uma
transação que termina em `rollback`, sempre — mesmo quando o teste falha, porque o
`rollback` está num `finally`. Nada do que os testes escrevem chega a existir para
qualquer outra conexão.

**O que essa proteção NÃO cobre**, e vale saber antes de escrever teste novo:

1. **`commit` explícito dentro de um teste.** Nenhum tem hoje. Um que tivesse
   escreveria em produção de verdade — é a única forma de furar o rollback.
2. **Bloqueio de linha.** Um teste que atualize uma linha real segura o lock até o
   rollback. Com 3 usuários e testes que duram segundos, é desconfortável, não
   perigoso. Os testes daqui criam os próprios dados em vez de mexer nos existentes,
   e é por isso que fazem assim.
3. **`analyze`, sequências e o marcador de migração** não voltam atrás. São
   inofensivos: estatística e contador.

**Regra para teste novo neste diretório**: cria o que precisa (usuário, cliente,
lançamento) e nunca altera nem apaga linha que já estava lá. Quem precisar de um
dado existente, leia — não escreva.

O teste de desempenho (`test_desempenho.py`) insere milhares de linhas e por isso
está marcado `lento`, fora da execução padrão. Rodá-lo contra produção é decisão
consciente, não acidente.

Tarefa: T036
"""

import os
from collections.abc import AsyncIterator, Iterator

import pytest

# Ambiente mínimo, definido ANTES de qualquer import de `app`: `app.config` valida
# na construção, então importar sem isso quebraria a coleta dos testes de unidade —
# que não precisam de banco nenhum.
os.environ.setdefault("DATABASE_URL", "postgresql://sem-banco@localhost:5432/indisponivel")
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


# Valor de espaço reservado do `setdefault` acima. Serve para os testes de unidade
# poderem importar `app.config` sem ambiente nenhum; **não é um banco**. Se a
# `DATABASE_URL` for esta, não há conexão a abrir.
_URL_DE_ESPACO_RESERVADO = "postgresql://sem-banco@localhost:5432/indisponivel"


@pytest.fixture
async def conexao_de_teste() -> AsyncIterator[object]:
    """Conexão em transação **sempre desfeita** — ver o aviso no topo do arquivo.

    Roda contra o `DATABASE_URL`, que é o banco de produção (decisão do dono do
    projeto). O `rollback` no `finally` é o que impede qualquer escrita de existir
    para outra conexão, inclusive quando o teste falha no meio.
    """
    url = os.environ.get("DATABASE_URL")
    if not url or url == _URL_DE_ESPACO_RESERVADO:
        pytest.skip(
            "DATABASE_URL não definida — teste de integração pulado. Defina-a "
            "(backend/.env ou variável de ambiente) para rodar as integrações. "
            "Ver quickstart.md §6."
        )

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.db import _normaliza_url

    url_normalizada, exige_tls = _normaliza_url(url)
    motor = create_async_engine(
        url_normalizada,
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
                # `finally`, não `else`: teste que falha no meio também precisa
                # desfazer. É a única coisa entre a suíte e o banco de produção.
                await transacao.rollback()
    finally:
        await motor.dispose()
