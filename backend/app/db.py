"""Conexão com o Postgres do Supabase.

Skill `supabase-postgres-best-practices` acionada antes de escrever (plan.md).
Três decisões saíram dela e valem ser explicadas, porque as três são
contraintuitivas:

1. **Pool pequeno e reaproveitado — `NullPool` saiu depois de medição.** A regra
   `conn-pooling` manda usar pooling; a questão é *onde*. A versão anterior deste
   arquivo deixava o pooling inteiro para o Supabase e abria uma conexão nova por
   requisição, no medo de que a função serverless congelasse com conexão pendurada.

   **Medido em 2026-08-04**, mesma consulta, mesmo banco, 12 rodadas:

   | Arranjo | Mediana por consulta |
   |---|---|
   | `NullPool` (o de antes) | 2812 ms |
   | Pool reaproveitado | 1328 ms |

   Conexão nova paga três pedágios: handshake TLS, `pgbouncer.get_auth` no pooler e
   a **introspecção de tipos do asyncpg** — que aqui é cara porque o schema usa enums
   próprios (`mundo`, `tipo_lancamento`, `status_lancamento`) e o driver redescobre
   cada um em toda conexão nova. `pg_stat_statements` contava 4634 execuções de
   `WITH RECURSIVE typeinfo_tree`.

   O medo original continua legítimo e é endereçado, não ignorado:
   `pool_pre_ping=True` testa a conexão antes de entregá-la (conexão morta é
   descartada e refeita, não devolvida ao endpoint) e `pool_recycle` a aposenta antes
   do corte de ociosidade do pooler. `DB_POOL_TAMANHO=0` volta ao `NullPool` sem
   tocar em código, caso a plataforma mude.

2. **Prepared statement desligado — e com nome único.** A regra
   `conn-prepared-statements`: no modo *transaction* o pooler devolve a conexão ao fim
   de cada transação, e a próxima requisição pode cair em outra conexão — onde o
   statement preparado não existe. Daí `statement_cache_size=0` no asyncpg e
   `prepared_statement_cache_size=0` no dialeto do SQLAlchemy.

   **As duas não bastam**, e isso custou uma suíte inteira de integração vermelha.
   Mesmo com cache zerado, o asyncpg ainda prepara cada consulta antes de executar e
   nomeia o statement por contador do lado dele: `__asyncpg_stmt_1__`,
   `__asyncpg_stmt_2__`… Como cada requisição abre uma conexão nova (`NullPool`), o
   contador **reinicia do 1**. O pgbouncer, por sua vez, multiplexa várias conexões de
   cliente sobre a **mesma** conexão de servidor. Duas requisições concorrentes caem no
   mesmo servidor pedindo `__asyncpg_stmt_1__`, e a segunda leva:

       asyncpg.exceptions.DuplicatePreparedStatementError:
       prepared statement "__asyncpg_stmt_1__" already exists

   Não é problema de teste: é a configuração de produção. `prepared_statement_name_func`
   troca o contador por um UUID, e o nome deixa de colidir com o de qualquer outra
   conexão que esteja compartilhando o servidor.

   **Conferido em 2026-08-04, com pool ligado**: religar o cache de statement é
   tentador — vale mais 440 ms por consulta na medição — e **não funciona**. Sob
   concorrência o pooler devolve:

       asyncpg.exceptions.InvalidSQLStatementNameError:
       prepared statement "__asyncpg_stmt_e__" does not exist
       NOTE: pgbouncer with pool_mode set to "transaction" … does not support
       prepared statements properly

   O endereço é `aws-0-…​.pooler.supabase.com:6543` (Supavisor), e em modo
   *transaction* ele se comporta como o pgbouncer descrito acima. O cache fica em
   zero. O preço é replanejar toda consulta — `EXPLAIN` real do Dashboard dá
   `Planning 1.45 ms` contra `Execution 0.18 ms` —, e é por isso que **reduzir o
   número de consultas** (não acelerar cada uma) foi o caminho tomado no
   `dashboard/repositorio.py`.

4. **Toda requisição abre transação, inclusive a de leitura — e isso NÃO é desperdício.**
   Parece ser: `motor.begin()` manda `BEGIN` e `COMMIT` como duas viagens extras, e o
   `pg_stat_statements` conta 3274 `begin`. **Tentado em 2026-08-04**: entregar `GET` e
   `HEAD` numa conexão em `AUTOCOMMIT`. Quebra, de forma intermitente:

       asyncpg.exceptions.InvalidSQLStatementNameError:
       prepared statement "__asyncpg_ef24a4fe31834ceb984694aa20dab46e__" does not exist

   O nome é o UUID da nota 2, então **não é colisão** — o statement de fato não existe
   naquela conexão. O motivo: mesmo com o cache zerado, o asyncpg fala com o Postgres em
   duas etapas (`Parse`, depois `Bind`/`Execute`). Em modo *transaction* o pooler só é
   obrigado a manter o cliente na mesma conexão de servidor **enquanto houver transação
   aberta**. Sem transação, o `Parse` vai para uma conexão e o `Bind` pode ir para outra,
   onde aquele statement nunca foi preparado.

   Ou seja: a transação aqui não serve só à atomicidade — ela é o que **prende a conexão
   de servidor** pelo tempo da consulta. Os dois `BEGIN`/`COMMIT` são o preço de usar
   pooler em modo *transaction*, não uma sobra a cortar. Quem tentar esta otimização de
   novo vai encontrar um erro intermitente que passa em teste e falha em produção.

3. **`DATABASE_URL` deve apontar para a porta 6543** (pooler, modo transaction), não
   para a 5432 (conexão direta). A direta esgota `max_connections` com pouca
   concorrência.

SQLAlchemy entra no modo **Core** — sem ORM. São 21 tabelas com consultas escritas
à mão, várias com agregação que nenhum mapeamento de objeto ajudaria (Princípio I).

Tarefa: T024
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import obter_configuracao

# asyncpg não entende estes parâmetros na URL — quem os trata é o driver, por
# argumento de conexão. Deixá-los passar gera "unexpected keyword argument".
_PARAMETROS_IGNORADOS = {"sslmode", "channel_binding", "options", "target_session_attrs"}

_motor: AsyncEngine | None = None


def nome_de_statement() -> str:
    """Nome único por statement preparado — ver nota 2 no topo.

    Sem isto, o contador interno do asyncpg reinicia a cada conexão nova e colide
    com o de outra conexão multiplexada no mesmo servidor pelo pgbouncer.
    """
    return f"__asyncpg_{uuid.uuid4().hex}__"


def _normaliza_url(url: str) -> tuple[str, bool]:
    """Adapta a URL do Supabase ao driver asyncpg.

    Devolve a URL e se TLS deve ser exigido. O Supabase sempre exige TLS; o valor
    de `sslmode` na URL é lido só para não descartar uma intenção explícita.
    """
    partes = urlsplit(url)

    esquema = partes.scheme
    if esquema in ("postgres", "postgresql"):
        esquema = "postgresql+asyncpg"

    consulta = dict(parse_qsl(partes.query))
    sslmode = consulta.pop("sslmode", "require")
    for chave in list(consulta):
        if chave in _PARAMETROS_IGNORADOS:
            consulta.pop(chave)

    limpa = urlunsplit((esquema, partes.netloc, partes.path, urlencode(consulta), partes.fragment))
    return limpa, sslmode != "disable"


def obter_motor() -> AsyncEngine:
    """Motor de conexão, criado uma vez por processo."""
    global _motor
    if _motor is not None:
        return _motor

    configuracao = obter_configuracao()
    url, exige_tls = _normaliza_url(str(configuracao.database_url))

    # ver nota 1 no topo — `DB_POOL_TAMANHO=0` volta ao arranjo antigo
    if configuracao.db_pool_tamanho == 0:
        opcoes_de_pool: dict[str, Any] = {"poolclass": NullPool}
    else:
        opcoes_de_pool = {
            "pool_size": configuracao.db_pool_tamanho,
            "max_overflow": configuracao.db_pool_transbordo,
            "pool_recycle": configuracao.db_pool_reciclagem_s,
            # Conexão que morreu enquanto a função dormia é descartada aqui, não
            # entregue ao endpoint. É o que torna reaproveitar seguro em serverless.
            "pool_pre_ping": True,
            "pool_timeout": 10,
        }

    _motor = create_async_engine(
        url,
        **opcoes_de_pool,
        connect_args={
            # ver nota 2 — cache do asyncpg zerado E nome único por statement
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": nome_de_statement,
            "ssl": "require" if exige_tls else None,
            # A função da Vercel tem duração limitada (plan.md §Constraints). Melhor
            # falhar rápido e devolver erro que ficar pendurado até o corte da
            # plataforma, que não deixa mensagem nenhuma para o usuário.
            "timeout": 10,
            "server_settings": {
                "application_name": f"synapse-erp-api/{configuracao.ambiente}",
            },
        },
        echo=False,
        future=True,
    )
    return _motor


async def obter_conexao() -> AsyncIterator[AsyncConnection]:
    """Dependência do FastAPI: uma conexão por requisição, em transação.

    `engine.begin()` faz commit ao sair sem erro e rollback se subir exceção — que
    é exatamente o que se quer de um endpoint: ou a escrita inteira valeu, ou nada
    valeu. Importa para o espelho de subcategoria (D-07) e para o parcelamento, que
    gravam em mais de uma tabela e não podem ficar pela metade.

    **Vale para leitura também, e não é sobra** — ver nota 4 no topo: no pooler em
    modo *transaction* é a transação aberta que garante que `Parse` e `Bind` do mesmo
    statement cheguem à mesma conexão de servidor.
    """
    motor = obter_motor()
    async with motor.begin() as conexao:
        yield conexao


async def banco_responde() -> bool:
    """Usado por GET /api/saude (contracts/plataforma.md §7)."""
    try:
        motor = obter_motor()
        async with motor.begin() as conexao:
            await conexao.execute(text("select 1"))
        return True
    except Exception:
        # O motivo não vai para a resposta de propósito: /api/saude é público e
        # mensagem de erro de banco entrega topologia interna.
        return False


async def encerrar_motor() -> None:
    """Fecha o motor no desligamento do app (usado por app/main.py e pelos testes)."""
    global _motor
    if _motor is not None:
        await _motor.dispose()
        _motor = None
