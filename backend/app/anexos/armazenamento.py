"""Conversa com o Supabase Storage. **Só transporte** — nenhuma regra aqui.

O bucket `anexos` é **privado** (data-model §3.12): não existe URL pública. Todo
download passa por uma URL assinada de curta validade, gerada aqui com a chave
`service_role`. É a chave que ignora as políticas do banco, então ela nunca sai do
backend — o frontend recebe o link já assinado, nunca a chave (research.md D-03a).

Por que HTTP direto em vez da biblioteca `supabase-py`: são três chamadas (subir,
assinar, apagar) contra uma API REST estável, e a biblioteca arrasta a `storage3`,
a `gotrue` e a `postgrest` junto — peso que o pacote da função da Vercel não tem
onde colocar (plan.md §Constraints). A pesquisa está registrada no README do módulo
(Princípio II).

Tarefa: T064
"""

import re
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx

from app.comum.erros import ErroDaApi
from app.config import obter_configuracao

BUCKET = "anexos"

# Subir e assinar são operações de arquivo, não consulta de banco: o limite precisa
# caber um PDF de alguns megabytes numa conexão ruim sem cortar no meio.
TEMPO_LIMITE = httpx.Timeout(30.0, connect=10.0)

_CARACTERES_PROIBIDOS = re.compile(r"[^A-Za-z0-9._-]+")


class ErroDeArmazenamento(ErroDaApi):
    """502 — o Storage não respondeu ou recusou.

    Erro de infraestrutura, não do usuário: a mensagem diz que o arquivo **não** foi
    guardado, porque o pior desfecho aqui é a pessoa achar que anexou e não ter
    anexado (*edge case*: "nunca falha em silêncio").
    """

    status = 502
    codigo = "fonte_externa_indisponivel"


@dataclass(frozen=True)
class ArquivoGuardado:
    caminho: str
    tamanho_bytes: int


def nome_seguro(nome_original: str) -> str:
    """Reduz o nome ao que é seguro dentro de um caminho de objeto.

    O nome original **continua** guardado em `anexos.nome_arquivo` e é ele que o
    usuário vê no download. Este aqui só existe para o caminho no bucket: acento,
    espaço e barra em chave de objeto viram erro de codificação ou, pior, um caminho
    diferente do que se pretendia gravar.
    """
    limpo = _CARACTERES_PROIBIDOS.sub("-", nome_original.strip()).strip("-.")
    return (limpo or "arquivo")[:120]


def monta_caminho(lancamento_id: UUID, nome_original: str) -> str:
    """`{lancamento}/{sorteio}-{nome}`.

    O sorteio na frente do nome impede que dois anexos com o mesmo nome no mesmo
    lançamento disputem a mesma chave — `caminho_storage` é UNIQUE, e sem ele o
    segundo upload falharia por conflito em vez de conviver com o primeiro.
    """
    return f"{lancamento_id}/{uuid4().hex}-{nome_seguro(nome_original)}"


def _cabecalhos() -> dict[str, str]:
    configuracao = obter_configuracao()
    return {"Authorization": f"Bearer {configuracao.supabase_service_role_key}"}


def _base() -> str:
    return f"{obter_configuracao().supabase_url}/storage/v1"


async def sobe(caminho: str, conteudo: bytes, mime_type: str) -> ArquivoGuardado:
    """Grava o objeto no bucket privado."""
    try:
        async with httpx.AsyncClient(timeout=TEMPO_LIMITE) as cliente:
            resposta = await cliente.post(
                f"{_base()}/object/{BUCKET}/{caminho}",
                content=conteudo,
                headers=_cabecalhos()
                | {
                    "Content-Type": mime_type,
                    # Sem sobrescrever: o caminho é sorteado, então um conflito aqui
                    # significaria colisão inesperada — melhor falhar que substituir
                    # um comprovante por outro em silêncio.
                    "x-upsert": "false",
                },
            )
            resposta.raise_for_status()
    except httpx.HTTPError as erro:
        raise ErroDeArmazenamento(
            "O arquivo não pôde ser guardado agora. Ele NÃO foi anexado — tente de novo.",
            requisito="FR-013",
        ) from erro

    return ArquivoGuardado(caminho=caminho, tamanho_bytes=len(conteudo))


async def url_assinada(caminho: str, *, validade_segundos: int, nome_para_download: str) -> str:
    """URL temporária de leitura. É o único jeito de ler do bucket privado."""
    try:
        async with httpx.AsyncClient(timeout=TEMPO_LIMITE) as cliente:
            resposta = await cliente.post(
                f"{_base()}/object/sign/{BUCKET}/{caminho}",
                json={"expiresIn": validade_segundos},
                headers=_cabecalhos(),
            )
            resposta.raise_for_status()
            assinada = resposta.json()["signedURL"]
    except (httpx.HTTPError, KeyError) as erro:
        raise ErroDeArmazenamento(
            "Não foi possível gerar o link do arquivo agora. Tente de novo em instantes.",
            requisito="FR-013",
        ) from erro

    # A API devolve o caminho relativo (`/object/sign/...`). `download` faz o navegador
    # salvar com o nome original em vez de abrir com o nome sorteado do bucket.
    return f"{_base()}{assinada}&download={nome_seguro(nome_para_download)}"


async def apaga(caminho: str) -> None:
    """Remove o objeto.

    Falha aqui **não** é engolida: registro apagado com objeto vivo deixaria o
    arquivo pendurado no bucket sem nada apontando para ele, e ninguém descobriria.
    """
    try:
        async with httpx.AsyncClient(timeout=TEMPO_LIMITE) as cliente:
            resposta = await cliente.delete(
                f"{_base()}/object/{BUCKET}/{caminho}", headers=_cabecalhos()
            )
            if resposta.status_code != 404:  # já não existe é o resultado desejado
                resposta.raise_for_status()
    except httpx.HTTPError as erro:
        raise ErroDeArmazenamento(
            "O arquivo não pôde ser removido agora. Nada foi apagado — tente de novo.",
            requisito="FR-013",
        ) from erro
