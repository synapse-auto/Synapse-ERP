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
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.anexos.rotas import roteador as roteador_anexos
from app.anexos.rotas import roteador_upload as roteador_anexos_upload
from app.cadastros.centros_custo import roteador as roteador_centros_custo
from app.cadastros.servicos import roteador as roteador_servicos
from app.cadastros.tags import roteador as roteador_tags
from app.categorias.rotas import roteador as roteador_categorias
from app.categorias.rotas import roteador_subcategorias
from app.clientes.rotas import roteador as roteador_clientes
from app.comum.erros import ErroDaApi, ErroValidacao
from app.config import obter_configuracao
from app.dashboard.rotas import roteador as roteador_dashboard
from app.db import banco_responde, encerrar_motor
from app.extrato.rotas import roteador as roteador_extrato
from app.funcionarios.rotas import roteador as roteador_funcionarios
from app.lancamentos.rotas import roteador as roteador_lancamentos
from app.lancamentos.rotas import roteador_lixeira, roteador_saldo
from app.recorrencias.rotas import roteador as roteador_recorrencias
from app.recorrencias.rotas import roteador_parcelamentos
from app.rotinas.rotas import roteador as roteador_rotinas
from app.usuarios.rotas import roteador as roteador_sessao

registrador = logging.getLogger("synapse.erp")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    yield
    await encerrar_motor()


# ── Configuração: falha legível em vez de função morta ──────────────────────
#
# `obter_configuracao()` valida o ambiente e levanta se algo falta. Chamar isso solto
# aqui fazia o **import do módulo** estourar — e função serverless que quebra ao ser
# importada devolve `FUNCTION_INVOCATION_FAILED`, um 500 mudo, sem dizer qual variável
# está faltando. Foi exatamente o que aconteceu no primeiro deploy.
#
# Agora o erro é guardado e o app sobe assim mesmo. `GET /api/saude` — que é público e
# não toca dado de negócio — passa a **nomear as variáveis que faltam**. Os endpoints de
# negócio continuam falhando, como devem: sem banco não há o que responder.
#
# Não é tolerar configuração errada. É trocar "morreu sem dizer nada" por "morreu
# dizendo o quê" (Princípio VI: o que não é verificável não está pronto).

configuracao = None
_erro_de_configuracao: str | None = None

try:
    configuracao = obter_configuracao()
except Exception as erro:  # noqa: BLE001 — qualquer falha aqui precisa virar mensagem
    _erro_de_configuracao = str(erro)
    registrador.error("Configuração inválida: %s", erro)


def _variaveis_faltando() -> list[str]:
    """Nomes das variáveis de ambiente ausentes, para a mensagem de `/api/saude`."""
    from app.config import Configuracao

    return sorted(
        nome.upper()
        for nome, campo in Configuracao.model_fields.items()
        if campo.is_required() and not os.environ.get(nome.upper())
    )


app = FastAPI(
    title="Plataforma Financeira Synapse — API",
    description=(
        "ERP financeiro interno da Synapse. Dois mundos separados: Digital e Infra.\n\n"
        "Contratos acordados em `specs/001-erp-financeiro-synapse/contracts/`. "
        "Esta página é o contrato executável — os dois têm que bater."
    ),
    version=configuracao.versao_publicada if configuracao else "indisponivel",
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


@app.exception_handler(StarletteHTTPException)
async def trata_erro_http(request: Request, erro: StarletteHTTPException) -> JSONResponse:
    """Traz o 404 e o 405 do próprio framework para o formato único.

    Sem isto, caminho inexistente respondia `{"detail":"Not Found"}` — o formato do
    FastAPI, não o de contracts/README.md. Duas formas de erro na mesma API obrigariam
    o frontend a saber tratar as duas, e `RNF-02` diz que ele só mostra o que vem.
    Apareceu no primeiro acesso à raiz do deploy.
    """
    codigos = {404: "nao_encontrado", 405: "metodo_nao_permitido", 401: "nao_autenticado"}
    mensagens = {
        404: "Endereço não encontrado.",
        405: "Esta operação não é permitida neste endereço.",
        401: "Faça login para continuar.",
    }
    return JSONResponse(
        status_code=erro.status_code,
        content={
            "erro": {
                "codigo": codigos.get(erro.status_code, "erro_http"),
                "mensagem": mensagens.get(erro.status_code, str(erro.detail)),
                "requisito": None,
                "campos": None,
            }
        },
        headers=getattr(erro, "headers", None),
    )


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
# Depois de `roteador_lancamentos`: as duas usam o prefixo `/api/lancamentos` e o
# FastAPI casa na ordem de registro. Como o upload é `/{id}/anexos` e não colide com
# nenhuma rota de lançamento, a ordem aqui é só higiene — a que importa de verdade
# está dentro de `lancamentos/rotas.py` (`/lote` e `/exportacao` antes de `/{id}`).
app.include_router(roteador_anexos_upload)
app.include_router(roteador_anexos)
app.include_router(roteador_lixeira)
app.include_router(roteador_saldo)
app.include_router(roteador_dashboard)
app.include_router(roteador_extrato)
app.include_router(roteador_recorrencias)
app.include_router(roteador_parcelamentos)
app.include_router(roteador_rotinas)
app.include_router(roteador_categorias)
app.include_router(roteador_subcategorias)
app.include_router(roteador_clientes)
app.include_router(roteador_funcionarios)
app.include_router(roteador_tags)
app.include_router(roteador_centros_custo)
app.include_router(roteador_servicos)


# ── Raiz: atalho para a documentação ─────────────────────────────────────────
#
# Todo endpoint deste serviço mora sob `/api/...`, então `/` e `/api` não casavam
# rota nenhuma e caíam no handler de 404. Quem abria a URL do deploy no navegador —
# o primeiro reflexo de qualquer um — via
#
#     {"erro":{"codigo":"nao_encontrado","mensagem":"Endereço não encontrado.", …}}
#
# e concluía que o backend estava quebrado, quando na verdade aquela resposta era a
# prova de que ele estava vivo (a mensagem é NOSSA; Vercel com rota inexistente
# devolve HTML). Custou uma investigação inteira. Agora os dois caminhos levam a
# `/api/docs`, que é onde a resposta útil está.
#
# `include_in_schema=False` de propósito: isto é atalho de navegação, não endpoint
# de negócio. Entrar no OpenAPI criaria uma rota em `/api/docs` que
# `contracts/plataforma.md` não declara, e T208 trata divergência entre os dois como
# bug. Registrado em prosa no §7 do contrato e no README do módulo.


@app.get("/", include_in_schema=False)
@app.get("/api", include_in_schema=False)
async def raiz() -> RedirectResponse:
    """Manda quem chega na raiz para a documentação, em vez de um 404 enganoso."""
    return RedirectResponse(url="/api/docs", status_code=307)


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
async def saude() -> dict[str, Any]:
    # Configuração quebrada é a primeira coisa a reportar: sem ela o resto nem é
    # tentado, e o motivo real ficaria escondido atrás de um erro de banco.
    if configuracao is None:
        faltando = _variaveis_faltando()
        return {
            "status": "erro_de_configuracao",
            "banco": "nao_verificado",
            "versao": "indisponivel",
            "variaveis_faltando": faltando,
            "detalhe": (
                f"Faltam variáveis de ambiente: {', '.join(faltando)}."
                if faltando
                else "Alguma variável de ambiente está com valor inválido."
            ),
        }

    banco_ok = await banco_responde()
    return {
        "status": "ok" if banco_ok else "degradado",
        "banco": "ok" if banco_ok else "indisponivel",
        "versao": configuracao.versao_publicada,
    }
