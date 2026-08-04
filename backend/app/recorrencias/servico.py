"""Serviço de recorrências: liga o cálculo de datas ao banco (Princípio IV).

As regras (`RN-05a`, `RN-07`, horizonte, clamp do dia do mês) moram em
`app/dominio/recorrencia.py` e o SQL mora em `repositorio.py`. Aqui se decide a
**ordem**: quantas gerar de uma vez, o que fazer quando o lote acaba antes do horizonte
e quando parar.

## Geração em lotes com cursor (D-02a)

Uma recorrência cadastrada com início 5 anos atrás gera ~60 ocorrências passadas mais o
horizonte. Isso cabe numa invocação. Uma diária de 3 anos gera ~1.100 — não cabe, e a
função da Vercel seria cortada no meio, sem mensagem.

Então a materialização é **por lote**: gera até `LOTE_DE_GERACAO`, grava `gerada_ate` e
devolve `{concluida: false, cursor}`. O cliente chama `continuar-geracao` com o cursor
até vir `concluida: true`, mostrando progresso (edge case "a interface não trava").

O cursor **é** o `gerada_ate`: não existe estado extra guardado em lugar nenhum. Uma
invocação perdida no meio não deixa lixo — a próxima continua de onde o banco diz.

Tarefa: T078, T081
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from app.comum.erros import ErroNaoEncontrado
from app.dominio import recorrencia as mod_recorrencia
from app.lancamentos.servico import le_configuracao
from app.recorrencias import repositorio

# Quantas ocorrências uma invocação materializa antes de devolver o cursor. **Não é
# regra de negócio**: é o que cabe com folga na duração máxima da função (plan.md
# §Constraints). Cada ocorrência é um INSERT simples.
LOTE_DE_GERACAO = 200


@dataclass
class ResultadoDaGeracao:
    """O que a resposta devolve em `geracao` (contracts §3)."""

    geradas: int
    total: int
    concluida: bool
    cursor: date | None

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "concluida": self.concluida,
            "cursor": self.cursor.isoformat() if self.cursor else None,
            "geradas": self.geradas,
            "total": self.total,
        }


def regra_de(linha: dict[str, Any]) -> mod_recorrencia.Regra:
    """Traduz a linha do banco na regra que o domínio entende."""
    return mod_recorrencia.Regra(
        frequencia=linha["frequencia"],
        data_inicio=linha["data_inicio"],
        dia_vencimento=linha["dia_vencimento"],
        mes_vencimento=linha["mes_vencimento"],
        intervalo_dias=linha["intervalo_dias"],
        data_fim=linha["data_fim"],
        total_parcelas=linha["total_parcelas"],
    )


async def horizonte_configurado(conexao: AsyncConnection, hoje: date | None = None) -> date:
    """Até onde materializar — `configuracoes.recorrencia_horizonte_meses` (padrão 12)."""
    meses = int(await le_configuracao(conexao, "recorrencia_horizonte_meses", padrao=12))
    return mod_recorrencia.horizonte(hoje or date.today(), meses=meses)


async def limiar_de_aviso(conexao: AsyncConnection) -> int:
    """A partir de quantas ocorrências o `422` de `FR-027` aparece."""
    return int(await le_configuracao(conexao, "recorrencia_aviso_ocorrencias", padrao=24))


async def materializa(
    conexao: AsyncConnection,
    linha: dict[str, Any],
    *,
    usuario_id: UUID,
    ate: date,
    hoje: date | None = None,
    limite_do_lote: int = LOTE_DE_GERACAO,
    grava_cursor: bool = True,
) -> ResultadoDaGeracao:
    """Gera as ocorrências que faltam, de `gerada_ate` até `ate`, em um lote.

    Idempotente por construção: o `desde` sai de `gerada_ate` e o `insert` tem
    `on conflict do nothing` sobre `(recorrencia_id, data)`. Rodar duas vezes no mesmo
    dia não cria nada — e nem custa consulta extra para descobrir isso (D-08).

    As ocorrências do lote inteiro vão numa ida ao banco só, não uma por data — ver
    `repositorio.insere_ocorrencias`.

    `grava_cursor=False` deixa o avanço de `gerada_ate` para quem chamou. Serve a **um**
    caso: a rotina diária processa até 100 recorrências de uma vez e grava os 100
    marcadores num `UPDATE` só. O cursor calculado sai em `ResultadoDaGeracao.cursor`,
    então quem desliga isto tem tudo o que precisa para gravá-lo — e **precisa** gravar,
    senão a rotina seguinte regera o que já existe.
    """
    hoje = hoje or date.today()
    regra = regra_de(linha)

    desde = None if linha["gerada_ate"] is None else linha["gerada_ate"] + timedelta(days=1)
    if desde is not None and desde > ate:
        return ResultadoDaGeracao(geradas=0, total=0, concluida=True, cursor=linha["gerada_ate"])

    pendentes = list(mod_recorrencia.datas_das_ocorrencias(regra, ate=ate, desde=desde))
    do_lote = pendentes[:limite_do_lote]

    # `RN-05a`: o que está no passado nasce efetivado, **independente** do checkbox —
    # o dinheiro já se moveu.
    geradas = await repositorio.insere_ocorrencias(
        conexao,
        recorrencia=linha,
        ocorrencias=[
            (
                quando,
                "efetivado" if mod_recorrencia.nasce_efetivada(quando, hoje=hoje) else "programado",
            )
            for quando in do_lote
        ],
        usuario_id=usuario_id,
    )

    concluida = len(do_lote) == len(pendentes)
    # Quando o lote acabou antes do fim, o marcador para na última data gerada — não em
    # `ate`. Avançar até `ate` faria a continuação pular o que ficou faltando.
    cursor = ate if concluida else (do_lote[-1] if do_lote else linha["gerada_ate"])
    if cursor is not None and grava_cursor:
        await repositorio.marca_gerada_ate(conexao, linha["id"], cursor)

    return ResultadoDaGeracao(
        geradas=geradas, total=len(pendentes), concluida=concluida, cursor=cursor
    )


async def exige_recorrencia(conexao: AsyncConnection, recorrencia_id: UUID) -> dict[str, Any]:
    linha = await repositorio.por_id(conexao, recorrencia_id)
    if linha is None:
        raise ErroNaoEncontrado("Recorrência não encontrada.")
    return linha


# ── Serialização para a fronteira ───────────────────────────────────────────


def _dinheiro(valor: Any) -> str | None:
    from decimal import Decimal

    return None if valor is None else f"{Decimal(str(valor)):.2f}"


def rotulo_da_regra(linha: dict[str, Any]) -> str:
    """ "Mensal, dia 10" — texto pronto para a tela, montado no servidor.

    Fica aqui e não no frontend porque `RNF-02` diz que a tela mostra o que vem: montar
    "Mensal, dia {n}" em TypeScript seria regra de negócio (a leitura da frequência)
    escrita duas vezes, em duas línguas.
    """
    frequencia = linha["frequencia"]
    if frequencia == "dias":
        return f"A cada {linha['intervalo_dias']} dias"
    if frequencia == "semanal":
        dias = {
            1: "segunda",
            2: "terça",
            3: "quarta",
            4: "quinta",
            5: "sexta",
            6: "sábado",
            7: "domingo",
        }
        return f"Semanal, toda {dias.get(linha['dia_vencimento'] or 1, 'segunda')}"
    if frequencia == "mensal":
        return f"Mensal, dia {linha['dia_vencimento']}"
    meses = {
        1: "janeiro",
        2: "fevereiro",
        3: "março",
        4: "abril",
        5: "maio",
        6: "junho",
        7: "julho",
        8: "agosto",
        9: "setembro",
        10: "outubro",
        11: "novembro",
        12: "dezembro",
    }
    mes = meses.get(linha["mes_vencimento"] or 1, "janeiro")
    return f"Anual, {linha['dia_vencimento']} de {mes}"


def para_json(linha: dict[str, Any]) -> dict[str, Any]:
    """Formato da lista e do detalhe — contracts/lancamentos.md §3."""
    return {
        "id": str(linha["id"]),
        "mundo": linha["mundo"],
        "tipo": linha["tipo"],
        "descricao": linha["descricao"],
        "valor": _dinheiro(linha["valor"]),
        "frequencia": linha["frequencia"],
        "intervalo_dias": linha["intervalo_dias"],
        "dia_vencimento": linha["dia_vencimento"],
        "mes_vencimento": linha["mes_vencimento"],
        "rotulo": rotulo_da_regra(linha),
        "data_inicio": linha["data_inicio"].isoformat(),
        "data_fim": linha["data_fim"].isoformat() if linha["data_fim"] else None,
        "total_parcelas": linha["total_parcelas"],
        "efetivar_automaticamente": linha["efetivar_automaticamente"],
        "ativa": linha["ativa"],
        "categoria": {
            "id": str(linha["categoria_id"]),
            "nome": linha["categoria_nome"],
            "cor": linha["categoria_cor"],
            "icone": linha["categoria_icone"],
            "especial": linha["categoria_especial"],
            "vinculo": linha["categoria_vinculo"],
        },
        "subcategoria": (
            {"id": str(linha["subcategoria_id"]), "nome": linha["subcategoria_nome"]}
            if linha["subcategoria_id"]
            else None
        ),
        "servico": (
            {"id": str(linha["servico_id"]), "nome": linha["servico_nome"]}
            if linha["servico_id"]
            else None
        ),
        "centro_custo": (
            {"id": str(linha["centro_custo_id"]), "nome": linha["centro_custo_nome"]}
            if linha["centro_custo_id"]
            else None
        ),
        "cliente_id": str(linha["cliente_id"]) if linha["cliente_id"] else None,
        "funcionario_id": str(linha["funcionario_id"]) if linha["funcionario_id"] else None,
        "gerada_ate": linha["gerada_ate"].isoformat() if linha["gerada_ate"] else None,
        "ocorrencias_geradas": linha.get("ocorrencias_geradas", 0),
        "proxima_ocorrencia": (
            linha["proxima_ocorrencia"].isoformat() if linha.get("proxima_ocorrencia") else None
        ),
    }
