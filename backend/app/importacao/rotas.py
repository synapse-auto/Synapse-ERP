"""Importação em três etapas — contracts/lancamentos.md §6. `FR-044`.

Papel: gestor, operador nas três. Quem importa extrato é quem lança.

    1. POST /api/importacoes              envia o arquivo. **Não grava lançamento.**
    2. POST /api/importacoes/{id}/mapeamento   diz qual coluna é o quê. Devolve prévia validada.
    3. POST /api/importacoes/{id}/confirmar    grava, em lotes com cursor.

A separação existe para o usuário **ver antes de gravar**. Extrato de banco vem com
coluna em qualquer ordem e data em qualquer formato; importar direto significaria
descobrir o erro depois de 300 lançamentos criados.

O estado entre as etapas vive na tabela `importacoes` (migração `011`) — memória não
sobrevive entre invocações da Vercel, que é o mesmo motivo de o SQLite ter sido
descartado (D-01).

Tarefas: T133, T135, T136
"""

import json
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroNaoEncontrado, ErroRegraViolada, ErroValidacao
from app.db import obter_conexao
from app.dominio import mundo as mod_mundo
from app.importacao import csv as leitor_csv
from app.importacao import mapeamento as mod_mapeamento
from app.importacao import ofx as leitor_ofx
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/importacoes", tags=["Lançamentos"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

# Quantas linhas uma invocação grava antes de devolver o cursor. Mesmo raciocínio do
# lote de recorrências: é o que cabe na duração da função (plan.md §Constraints).
LOTE_DE_GRAVACAO = 200

TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024


class MapeamentoEntrada(BaseModel):
    mapa: dict[str, str] = Field(
        description="Campo → coluna do arquivo. `data`, `descricao` e `valor` são obrigatórios."
    )
    mundo: str = Field(
        description=(
            "**Obrigatório**: o arquivo não traz mundo e `RN-15` não admite nulo. Vale "
            "para o arquivo inteiro."
        )
    )
    categoria_padrao_id: UUID | None = Field(
        default=None,
        description="Usada nas linhas sem categoria reconhecida. Sem ela, elas ficam inválidas.",
    )
    tipo_padrao: str | None = Field(
        default=None,
        description="`receita`|`despesa`. Vazio deduz do sinal do valor, como o extrato traz.",
    )


class ConfirmarEntrada(BaseModel):
    ignorar_invalidas: bool = Field(
        default=False,
        description=(
            "Sem isto, uma linha inválida recusa a confirmação inteira. Ligado, grava as "
            "válidas e o relato diz quantas ficaram de fora."
        ),
    )


async def _exige(conexao: AsyncConnection, importacao_id: UUID, usuario_id: UUID) -> dict[str, Any]:
    linha = (
        (
            await conexao.execute(
                text("""
                    select id, usuario_id, nome_arquivo, formato, colunas, linhas,
                           mapeamento, mundo, cursor, gravados, concluida_em, expira_em
                    from importacoes where id = :id and usuario_id = :usuario
                    """),
                {"id": str(importacao_id), "usuario": str(usuario_id)},
            )
        )
        .mappings()
        .first()
    )
    # Filtrar por `usuario_id` no `where` é a autorização: a importação de outra pessoa
    # responde 404, não 403 — 403 já contaria que ela existe.
    if linha is None:
        raise ErroNaoEncontrado("Importação não encontrada.")
    return dict(linha)


async def _categorias_por_nome(conexao: AsyncConnection) -> dict[str, str]:
    linhas = (
        await conexao.execute(
            text("select id, nome from categorias where arquivada_em is null and not especial")
        )
    ).all()
    return {nome.strip().lower(): str(identificador) for identificador, nome in linhas}


# ── T133 · POST /api/importacoes ────────────────────────────────────────────


@roteador.post(
    "",
    status_code=201,
    summary="Envia o arquivo. **Não grava lançamento nenhum**",
    description=(
        "Papel: gestor, operador. `FR-044`. Aceita CSV e OFX. Devolve `importacao_id`, as "
        "colunas detectadas, um palpite de mapeamento e a prévia das primeiras linhas. "
        "**Nada é gravado nesta etapa** — a gravação é o `confirmar`."
    ),
)
async def enviar(
    usuario: Autenticado,
    conexao: Conexao,
    arquivo: Annotated[UploadFile, File(description="CSV ou OFX do banco.")],
) -> dict[str, Any]:
    conteudo = await arquivo.read(TAMANHO_MAXIMO_BYTES + 1)
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        raise ErroValidacao(
            f"O arquivo passa de {TAMANHO_MAXIMO_BYTES // (1024 * 1024)} MB. Divida em partes.",
            requisito="FR-044",
            campos={"arquivo": "Arquivo grande demais."},
        )
    if not conteudo:
        raise ErroValidacao(
            "O arquivo está vazio.", requisito="FR-044", campos={"arquivo": "Sem conteúdo."}
        )

    nome = arquivo.filename or "arquivo"
    formato = "ofx" if nome.lower().endswith(".ofx") else "csv"
    leitura = (leitor_ofx if formato == "ofx" else leitor_csv).le(conteudo)

    identificador = (
        await conexao.execute(
            text("""
                insert into importacoes (usuario_id, nome_arquivo, formato, colunas, linhas)
                values (cast(:usuario as uuid), :nome, :formato,
                        cast(:colunas as jsonb), cast(:linhas as jsonb))
                returning id
                """),
            {
                "usuario": str(usuario.id),
                "nome": nome,
                "formato": formato,
                "colunas": json.dumps(leitura.colunas, ensure_ascii=False),
                "linhas": json.dumps(leitura.linhas, ensure_ascii=False),
            },
        )
    ).scalar_one()

    return {
        "importacao_id": str(identificador),
        "nome_arquivo": nome,
        "formato": formato,
        "codificacao": leitura.codificacao,
        "separador": leitura.separador,
        "colunas": leitura.colunas,
        "total_de_linhas": leitura.total_de_linhas,
        "sugestoes_de_mapeamento": leitura.sugestoes,
        "previa": leitor_csv.monta_previa(leitura),
        "gravou_algo": False,
    }


# ── T135 · POST /api/importacoes/{id}/mapeamento ────────────────────────────


@roteador.post(
    "/{importacao_id}/mapeamento",
    summary="Diz qual coluna é o quê e devolve a prévia validada",
    description=(
        "Papel: gestor, operador. `mundo` é **obrigatório** — o arquivo não traz e "
        "`RN-15` não admite nulo. Categoria não reconhecida é **apontada**, nunca criada. "
        "Continua sem gravar lançamento."
    ),
)
async def mapear(
    importacao_id: UUID,
    corpo: MapeamentoEntrada,
    usuario: Autenticado,
    conexao: Conexao,
) -> dict[str, Any]:
    importacao = await _exige(conexao, importacao_id, usuario.id)
    if importacao["concluida_em"] is not None:
        raise ErroRegraViolada(
            "Esta importação já foi concluída.",
            requisito="FR-044",
            campos={"importacao": "Já gravada."},
        )

    mundo_validado = mod_mundo.exige("lancamentos", corpo.mundo)
    mod_mapeamento.valida_mapeamento(corpo.mapa, importacao["colunas"])

    if corpo.tipo_padrao is not None and corpo.tipo_padrao not in ("receita", "despesa"):
        raise ErroValidacao(
            f"Tipo '{corpo.tipo_padrao}' não existe.",
            requisito="FR-044",
            campos={"tipo_padrao": "Aceitos: receita, despesa."},
        )

    mapeadas = mod_mapeamento.mapeia(
        importacao["linhas"],
        mapa=corpo.mapa,
        categorias_por_nome=await _categorias_por_nome(conexao),
        tipo_padrao=corpo.tipo_padrao,
    )

    await conexao.execute(
        text("""
            update importacoes
            set mapeamento = cast(:mapeamento as jsonb), mundo = cast(:mundo as mundo)
            where id = :id
            """),
        {
            "id": str(importacao_id),
            "mundo": mundo_validado,
            "mapeamento": json.dumps(
                {
                    "mapa": corpo.mapa,
                    "categoria_padrao_id": (
                        str(corpo.categoria_padrao_id) if corpo.categoria_padrao_id else None
                    ),
                    "tipo_padrao": corpo.tipo_padrao,
                },
                ensure_ascii=False,
            ),
        },
    )

    return {
        "importacao_id": str(importacao_id),
        "mundo": mundo_validado,
        "resumo": mod_mapeamento.resumo(mapeadas),
        "previa": [linha.como_dicionario() for linha in mapeadas[:20]],
        "gravou_algo": False,
    }


# ── T136 · POST /api/importacoes/{id}/confirmar ─────────────────────────────


@roteador.post(
    "/{importacao_id}/confirmar",
    summary="Grava, em lotes com cursor",
    description=(
        "Papel: gestor, operador. Grava até 200 linhas por chamada e devolve o cursor; "
        "chame de novo até `concluida: true`, mostrando progresso (mesmo padrão das "
        "recorrências, D-02a). Linha inválida recusa a chamada inteira, a menos que "
        "`ignorar_invalidas` esteja ligado."
    ),
)
async def confirmar(
    importacao_id: UUID,
    corpo: ConfirmarEntrada,
    usuario: Autenticado,
    conexao: Conexao,
) -> dict[str, Any]:
    importacao = await _exige(conexao, importacao_id, usuario.id)

    if importacao["mapeamento"] is None:
        raise ErroRegraViolada(
            "Esta importação ainda não foi mapeada. Diga qual coluna é o quê antes de gravar.",
            requisito="FR-044",
            campos={"mapeamento": "Etapa anterior não concluída."},
        )
    if importacao["concluida_em"] is not None:
        return {
            "importacao_id": str(importacao_id),
            "concluida": True,
            "cursor": importacao["cursor"],
            "gravados": importacao["gravados"],
            "total": len(importacao["linhas"]),
            "ja_concluida": True,
        }

    configuracao = importacao["mapeamento"]
    mapeadas = mod_mapeamento.mapeia(
        importacao["linhas"],
        mapa=configuracao["mapa"],
        categorias_por_nome=await _categorias_por_nome(conexao),
        tipo_padrao=configuracao.get("tipo_padrao"),
    )

    padrao = configuracao.get("categoria_padrao_id")
    for linha in mapeadas:
        if linha.categoria_id is None and padrao:
            linha.categoria_id = padrao
            linha.problemas = [
                problema
                for problema in linha.problemas
                if "Categoria" not in problema and "categoria" not in problema
            ]

    invalidas = [linha for linha in mapeadas if not linha.valida]
    if invalidas and not corpo.ignorar_invalidas:
        raise ErroRegraViolada(
            (
                f"{len(invalidas)} linhas têm problema. Corrija o arquivo ou reenvie com "
                "`ignorar_invalidas` para gravar só as válidas."
            ),
            requisito="FR-044",
            campos={"linhas": f"{len(invalidas)} de {len(mapeadas)} inválidas."},
        )

    validas = [linha for linha in mapeadas if linha.valida and linha.categoria_id]
    inicio = importacao["cursor"]
    do_lote = validas[inicio : inicio + LOTE_DE_GRAVACAO]

    gravados = 0
    for linha in do_lote:
        await conexao.execute(
            text("""
                insert into lancamentos (
                  mundo, tipo, descricao, valor, data, status, categoria_id,
                  efetivar_automaticamente, efetivado_em, efetivado_por, criado_por
                ) values (
                  cast(:mundo as mundo), cast(:tipo as tipo_lancamento), :descricao,
                  :valor, :data,
                  case when :data <= :hoje then 'efetivado' else 'programado' end::status_lancamento,
                  cast(:categoria as uuid), true,
                  case when :data <= :hoje then now() end,
                  case when :data <= :hoje then cast(:usuario as uuid) end,
                  cast(:usuario as uuid)
                )
                """),
            {
                "mundo": importacao["mundo"],
                "tipo": linha.tipo,
                "descricao": linha.descricao,
                # `RN-02`: valor sempre positivo; o sinal do extrato virou `tipo`.
                "valor": abs(linha.valor),
                "data": linha.data,
                "hoje": date.today(),
                "categoria": linha.categoria_id,
                "usuario": str(usuario.id),
            },
        )
        gravados += 1

    novo_cursor = inicio + len(do_lote)
    concluida = novo_cursor >= len(validas)

    await conexao.execute(
        text("""
            update importacoes
            set cursor = :cursor, gravados = gravados + :gravados,
                concluida_em = case when :concluida then now() else null end
            where id = :id
            """),
        {
            "id": str(importacao_id),
            "cursor": novo_cursor,
            "gravados": gravados,
            "concluida": concluida,
        },
    )

    return {
        "importacao_id": str(importacao_id),
        "concluida": concluida,
        "cursor": novo_cursor,
        "gravados": importacao["gravados"] + gravados,
        "total": len(validas),
        "ignoradas": len(invalidas),
    }
