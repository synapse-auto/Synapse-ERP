"""Conexão com o Postgres do Supabase.

Skill `supabase-postgres-best-practices` acionada antes de escrever (plan.md).
Três decisões saíram dela e valem ser explicadas, porque as três são
contraintuitivas:

1. **`NullPool` — o backend não mantém pool próprio.** A regra `conn-pooling` manda
   usar pooling; a questão é *onde*. Numa função serverless o processo pode ser
   congelado entre requisições e descartado sem aviso, então um pool em memória
   acumula conexões mortas que o Postgres só descobre no timeout. Quem faz o
   pooling é o **pooler do Supabase** (pgbouncer), do lado do banco. O backend abre
   e fecha. Para 3 usuários o custo do handshake é irrelevante; conexão pendurada
   não é.

2. **Prepared statement desligado.** A regra `conn-prepared-statements`: no modo
   *transaction* o pooler devolve a conexão ao fim de cada transação, e a próxima
   requisição pode cair em outra conexão — onde o statement preparado não existe.
   Daí `statement_cache_size=0` no asyncpg e `prepared_statement_cache_size=0` no
   dialeto do SQLAlchemy. As duas são necessárias: são caches diferentes.

3. **`DATABASE_URL` deve apontar para a porta 6543** (pooler, modo transaction), não
   para a 5432 (conexão direta). A direta esgota `max_connections` com pouca
   concorrência.

SQLAlchemy entra no modo **Core** — sem ORM. São 19 tabelas com consultas escritas
à mão, várias com agregação que nenhum mapeamento de objeto ajudaria (Princípio I).

Tarefa: T024
"""

from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import obter_configuracao

# asyncpg não entende estes parâmetros na URL — quem os trata é o driver, por
# argumento de conexão. Deixá-los passar gera "unexpected keyword argument".
_PARAMETROS_IGNORADOS = {"sslmode", "channel_binding", "options", "target_session_attrs"}

_motor: AsyncEngine | None = None


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

    _motor = create_async_engine(
        url,
        poolclass=NullPool,  # ver nota 1 no topo
        connect_args={
            # ver nota 2 — cache do asyncpg
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
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
    """
    motor = obter_motor()
    async with motor.begin() as conexao:
        yield conexao


async def banco_responde() -> bool:
    """Usado por GET /api/saude (contracts/plataforma.md §7)."""
    try:
        motor = obter_motor()
        async with motor.connect() as conexao:
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
