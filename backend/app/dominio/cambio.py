"""`RN-12` — conversão USD→BRL. Módulo dono da regra (Princípio III).

O sistema opera **exclusivamente em BRL**. Dólar é conveniência de entrada: entra em
USD, é convertido na hora e guardado em reais, com o valor original, a cotação usada e
a data da cotação registrados junto.

**A cotação é a da data do lançamento, não a de hoje.** É o ponto que mais se erra:
lançar hoje uma assinatura paga em 15/03 com a cotação de hoje dá um valor em reais
que nunca existiu, e o fechamento de março não bate.

Ordem de busca: **cache → fonte primária → fonte alternativa → cotação manual**. Se
todas falharem, o sistema exige a cotação à mão e grava `cotacao_manual = true`.
**Nunca grava valor sem cotação registrada** (data-model §5.5).

As fontes entram por parâmetro em vez de serem importadas aqui. Não é abstração
gratuita: é o que permite testar `RN-12` — alvo obrigatório da constituição — sem
depender de a AwesomeAPI estar no ar. Quem monta as fontes de verdade é
`app/lancamentos/servico.py`; as chaves `cambio_fonte_primaria` e
`cambio_fonte_alternativa` vêm de `configuracoes` (Princípio VII).

Tarefa: T046
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.comum.erros import ErroFonteExternaIndisponivel, ErroValidacao

PAR = "USDBRL"
CENTAVO = Decimal("0.01")

Moeda = Literal["BRL", "USD"]


@dataclass(frozen=True)
class Cotacao:
    data: date
    taxa: Decimal
    fonte: str
    manual: bool = False


# Uma fonte recebe a data e devolve a cotação daquela data, ou `None` se não tiver.
BuscadorDeCotacao = Callable[[date], Awaitable[Cotacao | None]]


def converte(valor_usd: Decimal, taxa: Decimal) -> Decimal:
    """USD → BRL, arredondado ao centavo.

    `ROUND_HALF_UP` é o arredondamento do dinheiro no Brasil. O padrão do Python é
    `ROUND_HALF_EVEN` (bancário), que arredonda 0,005 para o par mais próximo — e daria
    números que não batem com a nota fiscal.
    """
    if taxa <= 0:
        raise ErroValidacao(
            "A cotação precisa ser maior que zero.",
            requisito="RN-12",
            campos={"cotacao": "Informe um valor positivo."},
        )
    return (valor_usd * taxa).quantize(CENTAVO, rounding=ROUND_HALF_UP)


async def _tenta(buscador: BuscadorDeCotacao | None, data: date) -> Cotacao | None:
    """Chama uma fonte tolerando falha — a próxima da fila é quem decide o destino.

    Captura `Exception` de propósito: fonte externa falha de todo jeito imaginável
    (rede, DNS, HTML no lugar de JSON, 500). O que **não** pode acontecer é uma dessas
    derrubar o lançamento antes de a alternativa ser tentada.
    """
    if buscador is None:
        return None
    try:
        return await buscador(data)
    except Exception:
        return None


async def obtem_cotacao(
    data: date,
    *,
    buscar_no_cache: BuscadorDeCotacao | None = None,
    fonte_primaria: BuscadorDeCotacao | None = None,
    fonte_alternativa: BuscadorDeCotacao | None = None,
    cotacao_manual: Decimal | None = None,
) -> Cotacao:
    """Cotação da **data do lançamento**, na ordem cache → primária → alternativa → manual."""
    do_cache = await _tenta(buscar_no_cache, data)
    if do_cache is not None:
        return do_cache

    for fonte in (fonte_primaria, fonte_alternativa):
        obtida = await _tenta(fonte, data)
        if obtida is not None:
            # A manual é ignorada quando a fonte responde. Aceitá-la aqui deixaria
            # alterar o valor em reais à mão com a fonte no ar — o que é exatamente o
            # que a regra não quer.
            return obtida

    if cotacao_manual is not None:
        if cotacao_manual <= 0:
            raise ErroValidacao(
                "A cotação informada precisa ser maior que zero.",
                requisito="RN-12",
                campos={"cotacao_manual": "Informe um valor positivo."},
            )
        return Cotacao(data=data, taxa=cotacao_manual, fonte="manual", manual=True)

    raise ErroFonteExternaIndisponivel(
        (
            f"Não foi possível obter a cotação do dólar de {data.strftime('%d/%m/%Y')}. "
            "Informe a cotação manualmente para salvar este lançamento."
        ),
        requisito="RN-12",
        campos={"cotacao_manual": "Preencha com a cotação do dia do lançamento."},
    )


def campos_do_lancamento(
    *,
    valor_informado: Decimal,
    moeda: str,
    cotacao: Cotacao | None,
) -> dict[str, object]:
    """Os campos de moeda prontos para gravar, conforme as constraints do banco.

    `moeda_origem = 'USD'` exige `valor_origem`, `cotacao` e `cotacao_data` preenchidos;
    `'BRL'` exige os três nulos (data-model §3.10). Montar isso num lugar só evita que
    cada caminho de escrita (criar, importar, duplicar, parcelar) monte à sua maneira e
    esbarre na constraint.
    """
    if moeda == "BRL":
        return {
            "valor": valor_informado.quantize(CENTAVO, rounding=ROUND_HALF_UP),
            "moeda_origem": "BRL",
            "valor_origem": None,
            "cotacao": None,
            "cotacao_data": None,
            "cotacao_manual": False,
        }

    if moeda != "USD":
        raise ErroValidacao(
            f"Moeda '{moeda}' não é aceita.",
            requisito="RN-12",
            campos={"moeda": "Valores aceitos: BRL, USD."},
        )

    if cotacao is None:
        raise ErroValidacao(
            "Um lançamento em dólar não pode ser salvo sem a cotação usada.",
            requisito="RN-12",
            campos={"cotacao": "Obrigatória quando a moeda é USD."},
        )

    return {
        "valor": converte(valor_informado, cotacao.taxa),
        "moeda_origem": "USD",
        "valor_origem": valor_informado.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        "cotacao": cotacao.taxa,
        "cotacao_data": cotacao.data,
        "cotacao_manual": cotacao.manual,
    }
