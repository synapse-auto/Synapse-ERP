"""Anexos de lançamento — `FR-013`, contracts/lancamentos.md §5.

Três endpoints, todos `gestor, operador`: quem lança é quem anexa o comprovante.

Duas regras que valem ler antes de mexer:

- **O bucket é privado.** `GET /api/anexos/{id}` responde `302` para uma URL assinada
  que vale poucos minutos (`configuracoes.anexo_url_assinada_segundos`). Não existe
  endereço público — nota fiscal da empresa não fica atrás de link adivinhável.
- **`RF-013a`: o anexo mora no lançamento-pai.** Anexar numa parte de split é
  recusado, com a mensagem apontando o pai. As partes leem por herança, então o mesmo
  comprovante serve às três partes sem ser enviado três vezes.

Limite de tamanho e formatos aceitos vêm de `configuracoes`, nunca do código
(Princípio VII) — mudar o teto de 10 MB é um UPDATE, não um deploy.

Tarefa: T064
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.anexos import armazenamento
from app.comum.auditoria import registra_auditoria
from app.comum.erros import (
    ErroArquivoGrande,
    ErroFormatoNaoSuportado,
    ErroNaoEncontrado,
    ErroRegraViolada,
    ErroValidacao,
)
from app.db import obter_conexao
from app.lancamentos import servico
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/anexos", tags=["Lançamentos"])
roteador_upload = APIRouter(prefix="/api/lancamentos", tags=["Lançamentos"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

BYTES_POR_MB = 1024 * 1024


def para_json(linha: Any) -> dict[str, Any]:
    """Formato do anexo na resposta. Sem URL: o link se pede na hora do download."""
    return {
        "id": str(linha["id"]),
        "nome_arquivo": linha["nome_arquivo"],
        "mime_type": linha["mime_type"],
        "tamanho_bytes": linha["tamanho_bytes"],
        "criado_em": linha["criado_em"].isoformat(),
        "url": f"/api/anexos/{linha['id']}",
    }


async def lista_do_lancamento(
    conexao: AsyncConnection, lancamento_id: UUID, *, lancamento_pai_id: UUID | None
) -> list[dict[str, Any]]:
    """Anexos do lançamento — ou os do pai, quando ele é parte de split (`RF-013a`)."""
    dono = lancamento_pai_id or lancamento_id
    linhas = (
        (
            await conexao.execute(
                text("""
                    select id, nome_arquivo, mime_type, tamanho_bytes, criado_em
                    from anexos where lancamento_id = :id order by criado_em
                    """),
                {"id": str(dono)},
            )
        )
        .mappings()
        .all()
    )
    return [para_json(linha) for linha in linhas]


async def _limites(conexao: AsyncConnection) -> tuple[int, list[str]]:
    tamanho_max_mb = int(await servico.le_configuracao(conexao, "anexo_tamanho_max_mb", padrao=10))
    mimes = await servico.le_configuracao(
        conexao,
        "anexo_mime_permitidos",
        padrao=["image/png", "image/jpeg", "image/webp", "application/pdf"],
    )
    return tamanho_max_mb, list(mimes)


# ── POST /api/lancamentos/{id}/anexos ────────────────────────────────────────


@roteador_upload.post(
    "/{lancamento_id}/anexos",
    status_code=201,
    summary="Anexa comprovantes ao lançamento",
    description=(
        "Papel: gestor, operador. `multipart/form-data`, vários arquivos por chamada. "
        "Acima de `configuracoes.anexo_tamanho_max_mb` → `413 arquivo_grande` com o limite "
        "na mensagem. Formato fora de `anexo_mime_permitidos` → `415 formato_nao_suportado`. "
        "Nunca falha em silêncio. Parte de split → `409`: o anexo mora no pai (`RF-013a`)."
    ),
)
async def enviar(
    lancamento_id: UUID,
    usuario: Autenticado,
    conexao: Conexao,
    arquivos: Annotated[list[UploadFile], File(description="Um ou mais arquivos.")],
) -> dict[str, Any]:
    lancamento = await servico.exige_lancamento(conexao, lancamento_id)

    if lancamento["lancamento_pai_id"] is not None:
        raise ErroRegraViolada(
            (
                "Esta é uma parte de um lançamento dividido. O comprovante fica no "
                "lançamento original e vale para todas as partes."
            ),
            requisito="RF-013a",
            campos={"lancamento": "Anexe no lançamento original."},
        )

    tamanho_max_mb, mimes_permitidos = await _limites(conexao)
    limite_bytes = tamanho_max_mb * BYTES_POR_MB

    # Validação de TODOS os arquivos antes de subir QUALQUER um: metade dos anexos no
    # bucket e a resposta dizendo "deu erro" deixaria lixo que ninguém vai limpar.
    conteudos: list[tuple[UploadFile, bytes]] = []
    for arquivo in arquivos:
        mime = (arquivo.content_type or "").split(";")[0].strip().lower()
        if mime not in mimes_permitidos:
            raise ErroFormatoNaoSuportado(
                (
                    f"'{arquivo.filename}' está em um formato que não aceitamos "
                    f"({mime or 'desconhecido'}). Aceitos: {', '.join(mimes_permitidos)}."
                ),
                requisito="FR-013",
                campos={"arquivos": "Envie imagem (PNG, JPEG, WebP) ou PDF."},
            )

        # Lê um byte a mais que o limite: basta para saber que estourou, sem carregar
        # um arquivo de 500 MB na memória de uma função serverless só para recusá-lo.
        conteudo = await arquivo.read(limite_bytes + 1)
        if len(conteudo) > limite_bytes:
            raise ErroArquivoGrande(
                f"'{arquivo.filename}' passa do limite de {tamanho_max_mb} MB por arquivo.",
                requisito="FR-013",
                campos={"arquivos": f"Máximo {tamanho_max_mb} MB."},
            )
        if not conteudo:
            raise ErroValidacao(
                f"'{arquivo.filename}' está vazio.",
                requisito="FR-013",
                campos={"arquivos": "Arquivo sem conteúdo."},
            )
        conteudos.append((arquivo, conteudo))

    criados: list[dict[str, Any]] = []
    for arquivo, conteudo in conteudos:
        nome = arquivo.filename or "arquivo"
        caminho = armazenamento.monta_caminho(lancamento_id, nome)
        guardado = await armazenamento.sobe(
            caminho, conteudo, (arquivo.content_type or "application/octet-stream").split(";")[0]
        )

        linha = (
            (
                await conexao.execute(
                    text("""
                        insert into anexos (
                          lancamento_id, nome_arquivo, caminho_storage, mime_type,
                          tamanho_bytes, criado_por
                        ) values (
                          :lancamento_id, :nome, :caminho, :mime, :tamanho, cast(:usuario as uuid)
                        )
                        returning id, nome_arquivo, mime_type, tamanho_bytes, criado_em
                        """),
                    {
                        "lancamento_id": str(lancamento_id),
                        "nome": nome,
                        "caminho": guardado.caminho,
                        "mime": (arquivo.content_type or "").split(";")[0],
                        "tamanho": guardado.tamanho_bytes,
                        "usuario": str(usuario.id),
                    },
                )
            )
            .mappings()
            .one()
        )
        criados.append(para_json(linha))

        # Auditado como edição do LANÇAMENTO, não como entidade própria: quem abre a
        # linha do tempo do detalhe (`FR-041`) quer ver "anexou nota-fiscal.pdf" junto
        # das outras mudanças, não numa lista separada.
        await registra_auditoria(
            conexao,
            entidade="lancamentos",
            entidade_id=lancamento_id,
            acao="edicao",
            usuario_id=usuario.id,
            alteracoes={"anexo": {"de": None, "para": nome}},
        )

    return {"itens": criados}


# ── GET /api/anexos/{id} ─────────────────────────────────────────────────────


@roteador.get(
    "/{anexo_id}",
    status_code=302,
    response_class=RedirectResponse,
    summary="Baixa o anexo por URL assinada",
    description=(
        "Papel: gestor, operador. Responde `302` para uma URL assinada de curta "
        "validade (`configuracoes.anexo_url_assinada_segundos`). O bucket é privado: "
        "não existe URL pública (data-model §3.12)."
    ),
)
async def baixar(anexo_id: UUID, usuario: Autenticado, conexao: Conexao) -> RedirectResponse:
    linha = (
        (
            await conexao.execute(
                text("""
                    select a.caminho_storage, a.nome_arquivo
                    from anexos a
                    join lancamentos_ativos l on l.id = a.lancamento_id
                    where a.id = :id
                    """),
                {"id": str(anexo_id)},
            )
        )
        .mappings()
        .first()
    )
    # A junção com `lancamentos_ativos` não é enfeite: sem ela o anexo de um lançamento
    # na lixeira continuaria baixável por quem tivesse o id (`RN-08`).
    if linha is None:
        raise ErroNaoEncontrado("Anexo não encontrado.")

    validade = int(
        await servico.le_configuracao(conexao, "anexo_url_assinada_segundos", padrao=300)
    )
    url = await armazenamento.url_assinada(
        linha["caminho_storage"],
        validade_segundos=validade,
        nome_para_download=linha["nome_arquivo"],
    )
    return RedirectResponse(url=url, status_code=302)


# ── DELETE /api/anexos/{id} ──────────────────────────────────────────────────


@roteador.delete(
    "/{anexo_id}",
    status_code=204,
    summary="Remove o anexo",
    description=(
        "Papel: gestor, operador. Apaga o registro e o objeto no Storage. Anexo é o "
        "único dado do sistema que sai de verdade — `RN-08` protege o lançamento, não "
        "o arquivo, e manter arquivo sem dono só ocuparia o bucket."
    ),
)
async def remover(anexo_id: UUID, usuario: Autenticado, conexao: Conexao) -> None:
    linha = (
        (
            await conexao.execute(
                text(
                    "select id, lancamento_id, nome_arquivo, caminho_storage "
                    "from anexos where id = :id"
                ),
                {"id": str(anexo_id)},
            )
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise ErroNaoEncontrado("Anexo não encontrado.")

    # Ordem deliberada: linha primeiro, objeto depois. Se o Storage falhar, a exceção
    # desfaz a transação e o registro continua apontando para um arquivo que ainda
    # existe — estado consistente. Na ordem inversa, uma falha deixaria o registro
    # apontando para um objeto já apagado, e o download quebraria sem explicação.
    await conexao.execute(text("delete from anexos where id = :id"), {"id": str(anexo_id)})
    await armazenamento.apaga(linha["caminho_storage"])

    await registra_auditoria(
        conexao,
        entidade="lancamentos",
        entidade_id=linha["lancamento_id"],
        acao="edicao",
        usuario_id=usuario.id,
        alteracoes={"anexo": {"de": linha["nome_arquivo"], "para": None}},
    )
