"""`RF-64`/`RN-05a` — "cliente desde": carregar o passado de um cliente antigo.

**Nada aqui toca o banco.** A função central é `resolve_inicio`, que recebe o mês
digitado e devolve a `data_inicio` que a recorrência da mensalidade deve ter. Quem grava
é `app/clientes/rotas.py`; quem gera as datas é `dominio/recorrencia.py`, sem alteração
nenhuma.

## Por que este módulo é tão pequeno — e por que isso é o ponto

Cliente retroativo **não é um caminho novo de gravação**. A recorrência já sabe fazer
tudo o que o caso pede:

- `datas_das_ocorrencias` gera de `data_inicio` até o horizonte, mês a mês;
- `nasce_efetivada` (`RN-05a`) faz **toda ocorrência de data passada nascer
  `efetivado`** — que é exatamente o que "o cliente já pagou" significa, e o que faz o
  histórico entrar no saldo (`RN-05`);
- o *clamp* do dia 31 em fevereiro é o mesmo, porque é a mesma regra;
- `insere_ocorrencias` grava o lote inteiro num `insert … select from unnest(…)` — uma
  ida ao banco para 18, 24 ou 36 meses;
- o índice único `(recorrencia_id, data)` com `on conflict do nothing` garante a
  idempotência (D-08).

A única coisa que faltava era **deixar `data_inicio` ser no passado**: o cadastro de
cliente fixava `date.today()`. Este módulo é a regra que decide qual data passada é
aceitável — não um segundo gerador de ocorrências.

## As três recusas

1. **Mês no futuro** não é histórico, é projeção — e a projeção já é a mensalidade
   normal.
2. **Mês antigo demais** vira um número que ninguém consegue conferir. O limite **não é
   fixo no código** (`RNF-02`, Princípio VII): vem de
   `configuracoes.cliente_retroativo_meses_maximo` (seed na migração `014`).
3. **Mês atual** não é recusa: é `None`. O comportamento passa a ser o de sempre —
   nenhuma ocorrência retroativa, só a mensalidade daqui para a frente. Devolver
   `date(ano, mes, 1)` daria a **mesma** série (o `_primeira_data` da recorrência
   reposiciona no `dia_vencimento` do mês de qualquer jeito), mas devolver `None` deixa
   o caso explícito em vez de depender dessa coincidência.

Tarefa: cliente retroativo (2026-08-04)
"""

import re
from datetime import date

from dateutil.relativedelta import relativedelta

from app.comum.erros import ErroValidacao

# Padrão do limite quando `configuracoes` ainda não tem a chave — 10 anos. O valor de
# verdade vem do banco; este número existe para o sistema subir antes da migração `014`.
PADRAO_MESES_MAXIMO = 120

# `AAAA-MM`. Mês e ano bastam: o dia de cada cobrança sai de `dia_cobranca`, que o
# cadastro já tem, e escolher um dia aqui só criaria a chance de os dois discordarem.
FORMATO = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

REQUISITO = "RN-05a"


def mes_como_data(mes: str) -> date:
    """`"2025-03"` → `date(2025, 3, 1)`. Recusa qualquer outra forma."""
    if not FORMATO.match(mes):
        raise ErroValidacao(
            f"'{mes}' não é um mês válido.",
            requisito=REQUISITO,
            campos={"cliente_desde": "Use o formato AAAA-MM, por exemplo 2025-03."},
        )
    ano, numero = mes.split("-")
    return date(int(ano), int(numero), 1)


def meses_entre(inicio: date, fim: date) -> int:
    """Quantos meses de calendário separam as duas datas. Negativo se `inicio` é depois."""
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month)


def resolve_inicio(
    mes: str | None,
    *,
    tipo_cobranca: str,
    meses_maximo: int,
    hoje: date | None = None,
) -> date | None:
    """A `data_inicio` da recorrência quando o cliente já era cliente antes do sistema.

    Devolve `None` quando não há retroativo a carregar — sem mês informado ou mês
    corrente. Nesse caso quem chama usa `date.today()`, como sempre fez.

    Recusa com `400 validacao` mês no futuro, mês além do limite configurado e
    retroativo em cobrança que não é recorrente.
    """
    if mes is None:
        return None

    hoje = hoje or date.today()

    if tipo_cobranca != "recorrente":
        # Pontual e parcelada não têm série mensal para reconstruir: o histórico delas é
        # lançamento avulso, que já existe e se cadastra direto.
        raise ErroValidacao(
            "Histórico retroativo só existe para cobrança recorrente.",
            requisito=REQUISITO,
            campos={"cliente_desde": "Disponível apenas com tipo_cobranca = recorrente."},
        )

    inicio = mes_como_data(mes)
    distancia = meses_entre(inicio, hoje)

    if distancia < 0:
        raise ErroValidacao(
            "O cliente não pode ser cliente desde uma data que ainda não chegou.",
            requisito=REQUISITO,
            campos={"cliente_desde": "Escolha o mês atual ou um mês passado."},
        )

    if distancia > meses_maximo:
        limite = hoje - relativedelta(months=meses_maximo)
        raise ErroValidacao(
            f"O histórico retroativo vai até {meses_maximo} meses atrás "
            f"(a partir de {limite.month:02d}/{limite.year}).",
            requisito=REQUISITO,
            campos={
                "cliente_desde": (
                    f"Máximo de {meses_maximo} meses, definido em "
                    "configuracoes.cliente_retroativo_meses_maximo."
                )
            },
        )

    if distancia == 0:
        # Mês corrente: o comportamento é o de sempre. Ver o cabeçalho do módulo.
        return None

    return inicio


def resumo(*, desde: date, ocorrencias: int, valor_unitario: str | None) -> dict[str, object]:
    """O bloco `retroativo` da resposta do `POST` — texto de negócio montado no servidor.

    A tela precisa conseguir dizer "18 meses carregados, R$ 36.000,00 entraram no saldo"
    sem remontar a conta em TypeScript (`RNF-02`).
    """
    return {
        "desde": desde.isoformat(),
        "ocorrencias_efetivadas": ocorrencias,
        "valor_total": valor_unitario,
        "mensagem": (
            f"{ocorrencias} " + ("cobrança" if ocorrencias == 1 else "cobranças") + " do "
            f"histórico {'foi lançada' if ocorrencias == 1 else 'foram lançadas'} como "
            "efetivada" + ("" if ocorrencias == 1 else "s") + " e já contam no saldo."
        ),
    }
