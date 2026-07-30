"""`RN-05` / `RN-16` — saldo e projeção. Módulo dono da regra (Princípio III).

    saldo(mundo) = Σ(efetivado, receita) − Σ(efetivado, despesa)

**Não existe saldo inicial** (`FR-114`, research.md D-06). O caixa é exclusivamente o
resultado dos lançamentos efetivados. Consequência que o dono do projeto aceitou: até
o histórico estar carregado, o número na tela fica **menor que a realidade**, e o
semáforo de saúde do caixa fica pessimista. Isso se resolve carregando o passado
(recorrência retroativa ou importação), não informando um saldo de partida.

O que entra em cada número:

| | `efetivado` | `programado` / `pendente` / `atrasado` | `cancelado` / excluído |
|---|---|---|---|
| Saldo (realizado) | ✅ | ❌ | ❌ |
| A pagar / A receber | ❌ | ✅ | ❌ |
| Projeção | ✅ | ✅ | ❌ |

As funções aqui operam sobre linhas já lidas do banco. A agregação de verdade é SQL,
em `app/dashboard/repositorio.py` — mas **a regra de o que conta mora aqui**, e o
repositório a aplica. Assim a regra é testável sem banco, que é o que a constituição
exige dos 6 alvos obrigatórios.

Tarefa: T044
"""

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from app.dominio.mundo import MUNDOS

ZERO = Decimal("0.00")

STATUS_REALIZADO: frozenset[str] = frozenset({"efetivado"})

# O que entra em "A pagar / A receber" e na projeção. `cancelado` fica fora dos dois:
# preserva histórico, mas não é dinheiro que vai se mover (`RN-03`).
STATUS_PREVISTO: frozenset[str] = frozenset({"programado", "pendente", "atrasado"})


def conta_no_realizado(*, status: str, excluido: bool, tem_partes: bool) -> bool:
    """A regra central de `RN-05`, num lugar só.

    `tem_partes` entra aqui por causa de `RN-11`: o pai de um split não conta, só as
    partes — senão o valor é somado duas vezes.
    """
    if excluido or tem_partes:
        return False
    return status in STATUS_REALIZADO


def conta_no_previsto(*, status: str, excluido: bool, tem_partes: bool) -> bool:
    """O que aparece em "A pagar / A receber" e alimenta a projeção."""
    if excluido or tem_partes:
        return False
    return status in STATUS_PREVISTO


def _com_sinal(linha: dict[str, Any]) -> Decimal:
    """Receita soma, despesa subtrai. O valor gravado é sempre positivo (`RN-02`)."""
    valor = Decimal(str(linha["valor"]))
    return valor if linha["tipo"] == "receita" else -valor


def _relevantes(linhas: Iterable[dict[str, Any]], mundo: str | None) -> list[dict[str, Any]]:
    if mundo is None or mundo == "ambos":
        return list(linhas)
    return [linha for linha in linhas if linha.get("mundo") == mundo]


def calcula(linhas: Iterable[dict[str, Any]], mundo: str | None = None) -> Decimal:
    """Saldo realizado. Só `efetivado` entra (`RN-05`)."""
    total = sum(
        (
            _com_sinal(linha)
            for linha in _relevantes(linhas, mundo)
            if conta_no_realizado(
                status=linha["status"],
                excluido=linha.get("excluido", False),
                tem_partes=linha.get("tem_partes", False),
            )
        ),
        ZERO,
    )
    return total.quantize(Decimal("0.01"))


def consolidado(linhas: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Modo "Ambos": total mais a quebra por mundo (`RN-16`, `RF-102`).

    Os dois mundos aparecem sempre na quebra, mesmo zerados — o mundo sem movimento
    tem que mostrar zero, não sumir (edge case da spec).
    """
    linhas = list(linhas)
    por_mundo = {nome: calcula(linhas, nome) for nome in MUNDOS}
    return {
        "total": sum(por_mundo.values(), ZERO).quantize(Decimal("0.01")),
        "por_mundo": por_mundo,
    }


def _previsto(linhas: Iterable[dict[str, Any]], tipo: str, mundo: str | None) -> dict[str, Any]:
    por_situacao: dict[str, Decimal] = {situacao: ZERO for situacao in sorted(STATUS_PREVISTO)}
    total = ZERO

    for linha in _relevantes(linhas, mundo):
        if linha["tipo"] != tipo:
            continue
        if not conta_no_previsto(
            status=linha["status"],
            excluido=linha.get("excluido", False),
            tem_partes=linha.get("tem_partes", False),
        ):
            continue
        valor = Decimal(str(linha["valor"]))
        por_situacao[linha["status"]] += valor
        total += valor

    return {"total": total.quantize(Decimal("0.01")), "por_situacao": por_situacao}


def a_receber(linhas: Iterable[dict[str, Any]], mundo: str | None = None) -> dict[str, Any]:
    """Receitas ainda não efetivadas, com a composição por situação (`FR-056`)."""
    return _previsto(linhas, "receita", mundo)


def a_pagar(linhas: Iterable[dict[str, Any]], mundo: str | None = None) -> dict[str, Any]:
    """Despesas ainda não efetivadas, com a composição por situação (`FR-056`)."""
    return _previsto(linhas, "despesa", mundo)


def projetado(linhas: Iterable[dict[str, Any]], mundo: str | None = None) -> Decimal:
    """Saldo se tudo que está previsto se confirmar.

    Alimenta o gráfico de fluxo de caixa (`FR-059`), onde a projeção aparece
    **visualmente distinta** do realizado — misturar os dois numa linha só seria
    apresentar expectativa como fato.
    """
    realizado = calcula(linhas, mundo)
    entra = a_receber(linhas, mundo)["total"]
    sai = a_pagar(linhas, mundo)["total"]
    return (realizado + entra - sai).quantize(Decimal("0.01"))
