"""`FR-099` — quando o alerta de caixa baixo deve existir. Sem banco.

A regra tem duas metades, e as duas são silenciosas quando erram:

- **sem compromisso não se avisa** — avisar "seu caixa cobre R$ 0,00" é ruído que
  ensina o usuário a ignorar o sino;
- **cobrindo não se avisa** — o alerta é sobre não caber, não sobre ser apertado.

Estas metades moravam num `if` dentro de `rotinas/semanal.py` e eram cobertas por um
teste de integração que precisava de um banco **vazio** para valer. Contra o Postgres
de produção — que tem despesas programadas de verdade — a premissa "sem compromisso
nenhum" é falsa, e o teste ficava vermelho sem defeito nenhum por trás. Um teste que
falha sempre é pior que nenhum: treina a ignorar a suíte inteira.

Aqui a regra é uma função pura e as duas metades são afirmáveis diretamente, incluindo
a fronteira exata em que uma vira a outra.
"""

from decimal import Decimal

import pytest

from app.rotinas.semanal import deve_avisar_caixa_baixo


def _avisa(saldo: str, compromissos: str) -> bool:
    return deve_avisar_caixa_baixo(saldo=Decimal(saldo), compromissos=Decimal(compromissos))


@pytest.mark.parametrize("saldo", ["0.00", "1000.00", "999999.99"])
def test_sem_compromisso_nao_avisa_por_maior_que_seja_o_saldo(saldo):
    """Nada a pagar na janela: não há pergunta a responder."""
    assert _avisa(saldo, "0.00") is False


def test_saldo_que_cobre_nao_avisa():
    assert _avisa("5000.00", "2000.00") is False


def test_saldo_exatamente_igual_nao_avisa():
    """A fronteira: cobrir na régua ainda é cobrir (`saldo < compromissos`)."""
    assert _avisa("2000.00", "2000.00") is False


def test_um_centavo_a_menos_ja_avisa():
    """A outra fronteira, do lado de cá — é aqui que o alerta nasce."""
    assert _avisa("1999.99", "2000.00") is True


def test_saldo_zero_com_conta_na_janela_avisa():
    """O caso que o Dashboard mostra hoje: caixa vazio e folha programada."""
    assert _avisa("0.00", "2100.00") is True


def test_saldo_negativo_avisa():
    """Conta a descoberto é o caso mais grave, não uma exceção a tratar à parte."""
    assert _avisa("-500.00", "300.00") is True
