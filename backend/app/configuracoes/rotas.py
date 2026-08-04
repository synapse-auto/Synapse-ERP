"""Configurações — contracts/plataforma.md §3. `FR-104`–`FR-106`, `RNF-02`.

Esta é a tela que materializa o Princípio VII: rótulo, limite, prazo e multiplicador
moram no banco, e mudá-los é um `PUT`, não um deploy.

**Leitura é de operador também.** O frontend precisa de `anexo_tamanho_max_mb`, de
`alerta_vencimento_dias` e dos rótulos dos cards para montar a tela — sem isso ele
voltaria a ter valores fixos no código, que é o que `RNF-02` proíbe. Escrita é só de
gestor.

## `descricao` vem do banco

O texto de ajuda de cada configuração é dado, não código (`FR-106`). A tela mostra o que
vem; escrever a explicação em TypeScript faria a ajuda divergir do que a chave realmente
faz no dia em que alguém mudasse o comportamento.

## Efeito imediato da tolerância

Alterar `inadimplencia_dias_tolerancia` **reavalia os clientes na hora**, não na próxima
rotina (*edge case* da spec). É barato porque a situação é derivada (`RN-10`): não há
nada a reescrever, só a recontar — e a resposta diz quantos mudaram de situação, para o
gestor ver o efeito do que acabou de fazer.

Tarefa: T130
"""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum import cache_configuracoes
from app.comum.auditoria import registra_auditoria
from app.comum.erros import ErroValidacao
from app.db import obter_conexao
from app.dominio import inadimplencia as mod_inadimplencia
from app.seguranca.auth import UsuarioAutenticado
from app.seguranca.rbac import exige_papel

roteador = APIRouter(prefix="/api/configuracoes", tags=["Plataforma"])

Autenticado = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor", "operador"))]
Gestor = Annotated[UsuarioAutenticado, Depends(exige_papel("gestor"))]
Conexao = Annotated[AsyncConnection, Depends(obter_conexao)]

# Faixas aceitas por chave. **Não é o valor** — é o domínio dele, que é regra de
# integridade e não parâmetro de negócio. Sem isto, `dias = 0` ou multiplicador negativo
# entrariam e quebrariam o cálculo em silêncio, longe daqui.
FAIXAS: dict[str, tuple[int, int]] = {
    "inadimplencia_dias_tolerancia": (0, 90),
    "saude_caixa_horizonte_dias": (1, 365),
    "caixa_baixo_horizonte_dias": (1, 90),
    "lixeira_retencao_dias": (1, 3650),
    "anexo_tamanho_max_mb": (1, 100),
    "anexo_url_assinada_segundos": (30, 86400),
    "variacao_destaque_percentual": (1, 1000),
    "recorrencia_horizonte_meses": (1, 60),
    "recorrencia_aviso_ocorrencias": (1, 1000),
}


async def _todas(conexao: AsyncConnection) -> list[dict[str, Any]]:
    linhas = (
        (
            await conexao.execute(
                text(
                    "select chave, valor, descricao, atualizado_em from configuracoes order by chave"
                )
            )
        )
        .mappings()
        .all()
    )
    return [dict(linha) for linha in linhas]


def _valida(chave: str, valor: Any) -> None:
    if chave in FAIXAS:
        minimo, maximo = FAIXAS[chave]
        if not isinstance(valor, int | float) or isinstance(valor, bool):
            raise ErroValidacao(
                f"'{chave}' espera um número.",
                requisito="RNF-02",
                campos={chave: f"Número entre {minimo} e {maximo}."},
            )
        if not minimo <= valor <= maximo:
            raise ErroValidacao(
                f"'{chave}' aceita valores entre {minimo} e {maximo}. Recebido: {valor}.",
                requisito="RNF-02",
                campos={chave: f"Fora da faixa aceita ({minimo}–{maximo})."},
            )

    if chave == "saude_caixa_multiplicadores":
        if not isinstance(valor, dict) or {"minimo", "folga"} - set(valor):
            raise ErroValidacao(
                "Os multiplicadores precisam trazer `minimo` e `folga`.",
                requisito="RF-46b",
                campos={chave: 'Formato: {"minimo": 1.0, "folga": 1.5}.'},
            )
        if valor["minimo"] <= 0 or valor["folga"] <= 0:
            raise ErroValidacao(
                "Os multiplicadores precisam ser maiores que zero.",
                requisito="RF-46b",
                campos={chave: "Valores positivos."},
            )
        if valor["folga"] < valor["minimo"]:
            raise ErroValidacao(
                "A folga não pode ser menor que o mínimo — o semáforo nunca ficaria amarelo.",
                requisito="RF-46b",
                campos={chave: "folga ≥ minimo."},
            )

    if chave == "alerta_vencimento_dias":
        if (
            not isinstance(valor, list)
            or not valor
            or any(not isinstance(d, int) or d < 0 for d in valor)
        ):
            raise ErroValidacao(
                "As antecedências são uma lista de dias, como `[1, 3, 7]`.",
                requisito="FR-096",
                campos={chave: "Lista de números não negativos."},
            )


async def _clientes_inadimplentes(conexao: AsyncConnection, *, tolerancia: int) -> set[str]:
    """Quem está atrasado com uma dada tolerância — usado antes e depois da mudança."""
    hoje = date.today()
    linhas = (
        (
            await conexao.execute(
                text("""
                    select c.id,
                           jsonb_agg(jsonb_build_object(
                             'data', l.data, 'valor', l.valor, 'status', l.status,
                             'efetivar_automaticamente', l.efetivar_automaticamente
                           )) as em_aberto
                    from clientes c
                    join subcategorias s on s.cliente_id = c.id
                    join lancamentos_ativos l on l.subcategoria_id = s.id
                    where c.arquivado_em is null
                      and l.tipo = 'receita' and l.status in ('pendente','atrasado')
                    group by c.id
                    """)
            )
        )
        .mappings()
        .all()
    )

    atrasados = set()
    for linha in linhas:
        situacao = mod_inadimplencia.avalia(
            [
                {
                    "data": date.fromisoformat(item["data"]),
                    "valor": item["valor"],
                    "status": item["status"],
                    "efetivar_automaticamente": item["efetivar_automaticamente"],
                }
                for item in linha["em_aberto"]
            ],
            tolerancia_dias=tolerancia,
            hoje=hoje,
        )
        if situacao.situacao == "atrasado":
            atrasados.add(str(linha["id"]))
    return atrasados


@roteador.get(
    "",
    summary="Todas as configurações, com o texto de ajuda",
    description=(
        "Papel: gestor, **operador também**. O frontend precisa dos limites e dos rótulos "
        "para montar a tela — sem isso ele voltaria a ter valores fixos no código, que é "
        "o que `RNF-02` proíbe. `descricao` vem do banco (`FR-106`)."
    ),
)
async def listar(usuario: Autenticado, conexao: Conexao) -> dict[str, Any]:
    return {
        linha["chave"]: {
            "valor": linha["valor"],
            "descricao": linha["descricao"],
            "faixa": (
                {"minimo": FAIXAS[linha["chave"]][0], "maximo": FAIXAS[linha["chave"]][1]}
                if linha["chave"] in FAIXAS
                else None
            ),
            "atualizado_em": linha["atualizado_em"].isoformat(),
        }
        for linha in await _todas(conexao)
    }


@roteador.put(
    "",
    summary="Atualiza um conjunto de configurações",
    description=(
        "Papel: **gestor**. Chave desconhecida → `400`. Valor fora do domínio → `400` com "
        "a faixa aceita. Alterar `inadimplencia_dias_tolerancia` **reavalia os clientes "
        "na hora** (*edge case*), e a resposta diz quantos mudaram de situação — é barato "
        "porque a situação é derivada, não gravada (`RN-10`)."
    ),
)
async def atualizar(
    usuario: Gestor,
    conexao: Conexao,
    corpo: Annotated[dict[str, Any], Body(description="Mapa `chave: valor`.")],
) -> dict[str, Any]:
    import json

    if not corpo:
        raise ErroValidacao(
            "Nenhuma configuração informada.",
            requisito="FR-105",
            campos={"corpo": "Informe ao menos uma chave."},
        )

    existentes = {linha["chave"]: linha for linha in await _todas(conexao)}
    desconhecidas = sorted(set(corpo) - set(existentes))
    if desconhecidas:
        raise ErroValidacao(
            f"Configuração desconhecida: {', '.join(desconhecidas)}.",
            requisito="FR-105",
            campos={chave: "Chave inexistente." for chave in desconhecidas},
        )

    for chave, valor in corpo.items():
        _valida(chave, valor)

    # Fotografia antes: só faz sentido para a tolerância, e por isso só é tirada quando
    # ela está no corpo — varrer os clientes a cada mudança de rótulo seria desperdício.
    muda_tolerancia = "inadimplencia_dias_tolerancia" in corpo
    antes = (
        await _clientes_inadimplentes(
            conexao, tolerancia=int(existentes["inadimplencia_dias_tolerancia"]["valor"])
        )
        if muda_tolerancia
        else set()
    )

    for chave, valor in corpo.items():
        await conexao.execute(
            text("""
                update configuracoes
                set valor = cast(:valor as jsonb), atualizado_por = cast(:usuario as uuid),
                    atualizado_em = now()
                where chave = :chave
                """),
            {
                "chave": chave,
                "valor": json.dumps(valor, ensure_ascii=False),
                "usuario": str(usuario.id),
            },
        )
        await registra_auditoria(
            conexao,
            entidade="configuracoes",
            entidade_id=usuario.id,  # a tabela é chaveada por texto; o alvo vai no diff
            acao="edicao",
            usuario_id=usuario.id,
            alteracoes={chave: {"de": existentes[chave]["valor"], "para": valor}},
        )

    # Quem acabou de salvar tem que ver o valor novo já na próxima leitura desta mesma
    # requisição (o cálculo de efeitos abaixo depende disso). Ver
    # `app/comum/cache_configuracoes.py` §"O que este cache NÃO promete".
    cache_configuracoes.invalida()

    efeitos: dict[str, Any] = {}
    if muda_tolerancia:
        depois = await _clientes_inadimplentes(
            conexao, tolerancia=int(corpo["inadimplencia_dias_tolerancia"])
        )
        efeitos = {
            "clientes_reavaliados": len(antes | depois),
            "deixaram_de_ser_inadimplentes": len(antes - depois),
            "passaram_a_ser_inadimplentes": len(depois - antes),
        }

    return {"atualizadas": sorted(corpo), "efeitos": efeitos}
