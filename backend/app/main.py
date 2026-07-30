"""Aplicação FastAPI — routers, tratamento de erro e documentação.

`/api/docs` **é** a documentação que a constituição exige (Princípio IV: "endpoint
sem documentação MUST NOT ser considerado pronto"). Ela tem que bater com os arquivos
de `contracts/`; divergência é bug, não detalhe (T208).

**Sem CORS de propósito.** O Next.js faz proxy de `/api/*` para cá (research.md
D-02), então navegador e API compartilham origem. Middleware de CORS aqui só
existiria para permitir chamada de outra origem — que é exatamente o que não se
quer.

Tarefas: T032 (app), T033 (`GET /api/saude`)
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.cadastros.centros_custo import roteador as roteador_centros_custo
from app.cadastros.servicos import roteador as roteador_servicos
from app.cadastros.tags import roteador as roteador_tags
from app.categorias.rotas import roteador as roteador_categorias
from app.comum.erros import ErroDaApi, ErroValidacao
from app.config import obter_configuracao
from app.db import banco_responde, encerrar_motor
from app.lancamentos.rotas import roteador as roteador_lancamentos
from app.lancamentos.rotas import roteador_lixeira, roteador_saldo
from app.usuarios.rotas import roteador as roteador_sessao

registrador = logging.getLogger("synapse.erp")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    yield
    await encerrar_motor()


configuracao = obter_configuracao()

app = FastAPI(
    title="Plataforma Financeira Synapse — API",
    description=(
        "ERP financeiro interno da Synapse. Dois mundos separados: Digital e Infra.\n\n"
        "Contratos acordados em `specs/001-erp-financeiro-synapse/contracts/`. "
        "Esta página é o contrato executável — os dois têm que bater."
    ),
    version=configuracao.versao_publicada,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=ciclo_de_vida,
)


# ── Tratamento de erro: uma resposta, um formato ─────────────────────────────


@app.exception_handler(ErroDaApi)
async def trata_erro_da_api(request: Request, erro: ErroDaApi) -> JSONResponse:
    """Todo erro previsto sai no formato de contracts/README.md §Erros."""
    return JSONResponse(status_code=erro.status, content=erro.como_corpo())


@app.exception_handler(RequestValidationError)
async def trata_erro_de_validacao(request: Request, erro: RequestValidationError) -> JSONResponse:
    """Traduz o erro do Pydantic para o nosso formato, em PT-BR.

    Sem isto, corpo malformado responderia no formato do FastAPI (`detail` com lista
    de dicionários em inglês) — outro formato de erro na mesma API, e o frontend
    teria que saber tratar dois (`RNF-02` proíbe montar texto de erro no cliente).
    """
    campos: dict[str, str] = {}
    for item in erro.errors():
        caminho = ".".join(str(parte) for parte in item["loc"] if parte not in ("body", "query"))
        campos[caminho or "corpo"] = item.get("msg", "Valor inválido.")

    convertido = ErroValidacao(
        "Alguns campos precisam de correção.",
        campos=campos or None,
    )
    return JSONResponse(status_code=convertido.status, content=convertido.como_corpo())


@app.exception_handler(Exception)
async def trata_erro_inesperado(request: Request, erro: Exception) -> JSONResponse:
    """Rede de segurança: erro não previsto também sai no formato único.

    O detalhe vai para o log, não para a resposta — mensagem de exceção entrega
    estrutura interna e às vezes dado de negócio. O usuário recebe uma frase em
    PT-BR que diz o que fazer.
    """
    registrador.exception("Erro não tratado em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "erro": {
                "codigo": "erro_interno",
                "mensagem": "Algo deu errado do nosso lado. Tente de novo em instantes.",
                "requisito": None,
                "campos": None,
            }
        },
    )


# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(roteador_sessao)
app.include_router(roteador_lancamentos)
app.include_router(roteador_lixeira)
app.include_router(roteador_saldo)
app.include_router(roteador_categorias)
app.include_router(roteador_tags)
app.include_router(roteador_centros_custo)
app.include_router(roteador_servicos)


# ── GET /api/saude — contracts/plataforma.md §7 (T033) ───────────────────────


@app.get(
    "/api/saude",
    tags=["Plataforma"],
    summary="Saúde do serviço",
    description=(
        "Público. Sem dado de negócio — só confirma que o deploy subiu e que o banco "
        "responde. `versao` traz o commit publicado, para saber qual código está no ar."
    ),
)
async def saude() -> dict[str, str]:
    banco_ok = await banco_responde()
    return {
        "status": "ok" if banco_ok else "degradado",
        "banco": "ok" if banco_ok else "indisponivel",
        "versao": configuracao.versao_publicada,
    }
