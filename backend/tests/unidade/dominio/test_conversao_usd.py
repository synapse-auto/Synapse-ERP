"""`RN-12` — conversão USD→BRL. Alvo obrigatório da constituição (Princípio VI).

O que a regra exige:

- A cotação é a da **data do lançamento**, não a de hoje. Lançar hoje uma despesa de
  15/03 tem que usar a cotação de 15/03 — senão o valor em reais fica errado, e o
  fechamento daquele mês não bate.
- Ordem de busca: cache → fonte primária → fonte alternativa → cotação manual.
- Se todas falharem, o sistema **exige** cotação manual e grava `cotacao_manual = true`.
  Nunca grava valor sem cotação registrada.
- Todo o resto do sistema opera em BRL. USD é conveniência de entrada.

As fontes são injetadas nos testes: teste de regra de negócio não pode depender de a
AwesomeAPI estar no ar.

Tarefa: T040
"""

from datetime import date
from decimal import Decimal

import pytest

from app.comum.erros import ErroFonteExternaIndisponivel, ErroValidacao
from app.dominio import cambio

DATA = date(2026, 3, 15)


def fonte_que_responde(taxa: str, nome: str = "awesomeapi"):
    async def buscar(data: date) -> cambio.Cotacao | None:
        return cambio.Cotacao(data=data, taxa=Decimal(taxa), fonte=nome)

    return buscar


def fonte_que_falha(nome: str = "fonte"):
    async def buscar(data: date) -> cambio.Cotacao | None:
        raise ConnectionError(f"{nome} fora do ar")

    return buscar


def fonte_sem_dado():
    async def buscar(data: date) -> cambio.Cotacao | None:
        return None

    return buscar


def sem_cache():
    async def buscar(data: date) -> cambio.Cotacao | None:
        return None

    return buscar


# ── A conta ──────────────────────────────────────────────────────────────────


def test_converte_usd_para_brl():
    assert cambio.converte(Decimal("50.00"), Decimal("5.432100")) == Decimal("271.61")


def test_conversao_arredonda_para_dois_decimais():
    """O banco guarda numeric(14,2). O arredondamento é o do dinheiro, meio pra cima."""
    assert cambio.converte(Decimal("10.00"), Decimal("5.125000")) == Decimal("51.25")
    assert cambio.converte(Decimal("1.00"), Decimal("5.555000")) == Decimal("5.56")
    assert cambio.converte(Decimal("1.00"), Decimal("5.554000")) == Decimal("5.55")


def test_cotacao_precisa_ser_positiva():
    with pytest.raises(ErroValidacao):
        cambio.converte(Decimal("50.00"), Decimal("0"))
    with pytest.raises(ErroValidacao):
        cambio.converte(Decimal("50.00"), Decimal("-5.43"))


# ── A ordem de busca ─────────────────────────────────────────────────────────


async def test_usa_o_cache_quando_existe():
    """Sem cache, cada lançamento antigo bateria de novo na fonte externa."""
    cotacao = await cambio.obtem_cotacao(
        DATA,
        buscar_no_cache=fonte_que_responde("5.10", nome="cache"),
        fonte_primaria=fonte_que_responde("9.99"),
        fonte_alternativa=fonte_que_responde("8.88"),
    )
    assert cotacao.taxa == Decimal("5.10")
    assert cotacao.fonte == "cache"


async def test_cai_para_a_primaria_sem_cache():
    cotacao = await cambio.obtem_cotacao(
        DATA,
        buscar_no_cache=sem_cache(),
        fonte_primaria=fonte_que_responde("5.20", nome="awesomeapi"),
        fonte_alternativa=fonte_que_responde("8.88"),
    )
    assert cotacao.taxa == Decimal("5.20")
    assert cotacao.fonte == "awesomeapi"


async def test_cai_para_a_alternativa_quando_a_primaria_falha():
    cotacao = await cambio.obtem_cotacao(
        DATA,
        buscar_no_cache=sem_cache(),
        fonte_primaria=fonte_que_falha("awesomeapi"),
        fonte_alternativa=fonte_que_responde("5.30", nome="bcb_ptax"),
    )
    assert cotacao.taxa == Decimal("5.30")
    assert cotacao.fonte == "bcb_ptax"


async def test_primaria_sem_dado_tambem_cai_para_a_alternativa():
    """Fim de semana e feriado: a fonte responde 200 e não traz cotação do dia."""
    cotacao = await cambio.obtem_cotacao(
        DATA,
        buscar_no_cache=sem_cache(),
        fonte_primaria=fonte_sem_dado(),
        fonte_alternativa=fonte_que_responde("5.30", nome="bcb_ptax"),
    )
    assert cotacao.fonte == "bcb_ptax"


async def test_as_duas_fontes_falhando_exige_cotacao_manual():
    """`502 fonte_externa_indisponivel`, com a saída dita na mensagem."""
    with pytest.raises(ErroFonteExternaIndisponivel) as capturado:
        await cambio.obtem_cotacao(
            DATA,
            buscar_no_cache=sem_cache(),
            fonte_primaria=fonte_que_falha("awesomeapi"),
            fonte_alternativa=fonte_que_falha("bcb_ptax"),
        )
    erro = capturado.value
    assert erro.status == 502
    assert erro.requisito == "RN-12"
    assert "manual" in erro.mensagem.lower()


async def test_cotacao_manual_e_aceita_quando_as_fontes_falham():
    cotacao = await cambio.obtem_cotacao(
        DATA,
        buscar_no_cache=sem_cache(),
        fonte_primaria=fonte_que_falha(),
        fonte_alternativa=fonte_que_falha(),
        cotacao_manual=Decimal("5.40"),
    )
    assert cotacao.taxa == Decimal("5.40")
    assert cotacao.manual is True


async def test_cotacao_manual_e_ignorada_quando_a_fonte_responde():
    """Fonte no ar manda. Aceitar a manual aqui deixaria alterar o valor à mão."""
    cotacao = await cambio.obtem_cotacao(
        DATA,
        buscar_no_cache=sem_cache(),
        fonte_primaria=fonte_que_responde("5.20"),
        fonte_alternativa=fonte_que_falha(),
        cotacao_manual=Decimal("99.00"),
    )
    assert cotacao.taxa == Decimal("5.20")
    assert cotacao.manual is False


# ── A data é a do lançamento, não a de hoje ──────────────────────────────────


async def test_busca_a_cotacao_da_data_do_lancamento():
    """O coração de `RN-12`: a data pedida à fonte é a do lançamento."""
    datas_pedidas: list[date] = []

    async def fonte(data: date) -> cambio.Cotacao | None:
        datas_pedidas.append(data)
        return cambio.Cotacao(data=data, taxa=Decimal("5.20"), fonte="awesomeapi")

    cotacao = await cambio.obtem_cotacao(
        DATA, buscar_no_cache=sem_cache(), fonte_primaria=fonte, fonte_alternativa=fonte
    )

    assert datas_pedidas == [DATA]
    assert cotacao.data == DATA
    assert cotacao.data != date.today()


# ── O que é gravado ──────────────────────────────────────────────────────────


def test_lancamento_em_usd_grava_valor_original_cotacao_e_data():
    """data-model §3.10: USD exige valor_origem, cotacao e cotacao_data preenchidos."""
    campos = cambio.campos_do_lancamento(
        valor_informado=Decimal("50.00"),
        moeda="USD",
        cotacao=cambio.Cotacao(data=DATA, taxa=Decimal("5.4321"), fonte="awesomeapi"),
    )
    assert campos == {
        "valor": Decimal("271.61"),
        "moeda_origem": "USD",
        "valor_origem": Decimal("50.00"),
        "cotacao": Decimal("5.4321"),
        "cotacao_data": DATA,
        "cotacao_manual": False,
    }


def test_lancamento_em_brl_deixa_os_campos_de_cambio_nulos():
    """A constraint do banco exige os três nulos quando a moeda é BRL."""
    campos = cambio.campos_do_lancamento(
        valor_informado=Decimal("1234.56"), moeda="BRL", cotacao=None
    )
    assert campos == {
        "valor": Decimal("1234.56"),
        "moeda_origem": "BRL",
        "valor_origem": None,
        "cotacao": None,
        "cotacao_data": None,
        "cotacao_manual": False,
    }


def test_usd_sem_cotacao_nunca_e_gravado():
    """ "Nunca grava valor sem cotação registrada" — data-model §5.5."""
    with pytest.raises(ErroValidacao):
        cambio.campos_do_lancamento(valor_informado=Decimal("50.00"), moeda="USD", cotacao=None)


def test_cotacao_manual_marca_a_linha():
    campos = cambio.campos_do_lancamento(
        valor_informado=Decimal("50.00"),
        moeda="USD",
        cotacao=cambio.Cotacao(data=DATA, taxa=Decimal("5.40"), fonte="manual", manual=True),
    )
    assert campos["cotacao_manual"] is True
