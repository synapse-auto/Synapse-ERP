"""Corpos de entrada e saída dos lançamentos — contracts/lancamentos.md §1.

Regras de fronteira (contracts/README.md):

- **Dinheiro é string decimal** (`"1234.56"`), nunca float. Entra como string e vira
  `Decimal`; sai formatado com duas casas. O `1.234,56` da tela é do frontend.
- **Datas em ISO** (`YYYY-MM-DD`). `dd/mm/aaaa` é apresentação.
- **Ausência é `null` explícito**, não campo omitido.

Tarefa: T052
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

TipoLancamento = Literal["receita", "despesa"]
StatusLancamento = Literal["programado", "pendente", "efetivado", "atrasado", "cancelado"]
Moeda = Literal["BRL", "USD"]
EscopoSerie = Literal["apenas_esta", "esta_e_futuras"]

# Aceita "1234.56" (contrato) e também Decimal/int vindos de teste.
Dinheiro = Annotated[Decimal, Field(gt=0, decimal_places=2, max_digits=14)]


class LancamentoEntrada(BaseModel):
    """Corpo do `POST /api/lancamentos`."""

    mundo: str = Field(
        description=(
            "digital | infra. Obrigatório: o servidor NÃO adivinha do último uso. "
            "O padrão do formulário (mundo ativo, `FR-004`) é do frontend."
        )
    )
    tipo: TipoLancamento
    descricao: str = Field(min_length=1, max_length=300)
    data: date
    valor: Dinheiro = Field(description="Sempre positivo; o sinal vem de `tipo` (`RN-02`).")
    moeda: Moeda = "BRL"
    cotacao_manual: Decimal | None = Field(
        default=None,
        gt=0,
        description="Só aceita quando as duas fontes de câmbio falharam (`RN-12`).",
    )

    categoria_id: UUID
    subcategoria_id: UUID | None = None
    servico_id: UUID | None = None
    centro_custo_id: UUID | None = None
    tag_ids: list[UUID] = Field(default_factory=list)

    observacoes: str | None = None
    efetivar_automaticamente: bool | None = Field(
        default=None,
        description=(
            "Nulo = usa o padrão de `configuracoes` (`efetivacao_automatica_padrao`, ou "
            "`efetivacao_automatica_padrao_receita_cliente` em receita de cliente). "
            "Princípio VII: o padrão é dado, não código."
        ),
    )

    @field_validator("descricao")
    @classmethod
    def _sem_espaco_sobrando(cls, valor: str) -> str:
        limpo = valor.strip()
        if not limpo:
            raise ValueError("A descrição não pode ficar vazia.")
        return limpo


class LancamentoEdicao(LancamentoEntrada):
    """Corpo do `PUT /api/lancamentos/{id}`."""

    versao: int = Field(
        ge=1,
        description=(
            "A versão que você leu. Divergente → `409 conflito_versao` com o que mudou "
            "(data-model §5.6) — em vez de sobrescrever a edição de outra pessoa em silêncio."
        ),
    )
    escopo_serie: EscopoSerie | None = Field(
        default=None,
        description="Obrigatório quando o lançamento veio de recorrência (`RN-07`).",
    )
    confirmar_alteracao_historica: bool = Field(
        default=False,
        description="Exigido para editar ocorrência passada já efetivada (data-model §5.8).",
    )


class ParteDoSplit(BaseModel):
    descricao: str = Field(min_length=1, max_length=300)
    valor: Dinheiro
    categoria_id: UUID
    subcategoria_id: UUID | None = None
    centro_custo_id: UUID | None = None


class DivisaoEntrada(BaseModel):
    """Corpo do `POST /api/lancamentos/{id}/dividir` (`RN-11`)."""

    partes: list[ParteDoSplit] = Field(min_length=2)


# ── Lote e ações em massa — contracts/lancamentos.md §1 (T062, T063) ─────────
#
# Os tetos de 200 e 500 abaixo **não são regra de negócio** e por isso não moram em
# `configuracoes` (Princípio VII fala de parâmetro de negócio: prazo, limiar, rótulo).
# São guarda da plataforma: a função da Vercel tem duração máxima (plan.md
# §Constraints) e um lote sem teto acabaria cortado no meio pela plataforma — que é
# justamente o "meio lote gravado" que o contrato proíbe.


class LoteEntrada(BaseModel):
    """Corpo do `POST /api/lancamentos/lote` (`FR-021`).

    **Tudo ou nada**: uma linha inválida recusa o lote inteiro. Meio lote gravado numa
    tabela editável é pior que nenhum — o usuário não saberia quais linhas repetir.
    """

    lancamentos: list[LancamentoEntrada] = Field(min_length=1, max_length=200)


AcaoEmMassa = Literal[
    "excluir", "mudar_categoria", "mudar_status", "adicionar_tags", "remover_tags"
]

# `RN-03`: das transições do ciclo, só estas duas são pedidas por pessoa. As outras
# (`programado` → `pendente` → `atrasado`) são da rotina diária, na data — não são ação
# de usuário e por isso não entram aqui (data-model §5.8).
StatusEmMassa = Literal["efetivado", "cancelado"]


class ParametrosAcaoEmMassa(BaseModel):
    """O que cada ação precisa. Qual campo é obrigatório depende da `acao`."""

    categoria_id: UUID | None = None
    subcategoria_id: UUID | None = None
    status: StatusEmMassa | None = None
    tag_ids: list[UUID] = Field(default_factory=list)


class AcoesEmMassaEntrada(BaseModel):
    """Corpo do `POST /api/lancamentos/acoes-em-massa` (`FR-040`).

    Também tudo-ou-nada. Exportar em massa não passa por aqui: é
    `GET /api/lancamentos/exportacao`, que já respeita os filtros da tela.
    """

    lancamento_ids: list[UUID] = Field(min_length=1, max_length=500)
    acao: AcaoEmMassa
    parametros: ParametrosAcaoEmMassa = Field(default_factory=ParametrosAcaoEmMassa)

    @model_validator(mode="after")
    def _exige_o_parametro_da_acao(self) -> "AcoesEmMassaEntrada":
        """Recusa no corpo o que só falharia lá na frente, no meio do lote.

        Sem isto, `mudar_categoria` sem `categoria_id` só quebraria ao gravar o
        primeiro lançamento — depois de o usuário já ter esperado a requisição.
        """
        faltando = {
            "mudar_categoria": ("categoria_id", self.parametros.categoria_id is None),
            "mudar_status": ("status", self.parametros.status is None),
            "adicionar_tags": ("tag_ids", not self.parametros.tag_ids),
            "remover_tags": ("tag_ids", not self.parametros.tag_ids),
        }.get(self.acao)

        if faltando and faltando[1]:
            raise ValueError(f"A ação '{self.acao}' exige `parametros.{faltando[0]}`.")
        return self
