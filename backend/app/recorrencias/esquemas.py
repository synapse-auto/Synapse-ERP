"""Corpos de entrada das recorrências e do parcelamento — contracts §3 e §4.

Mesmas regras de fronteira dos lançamentos: dinheiro é string decimal, data é ISO,
ausência é `null` explícito (contracts/README.md).

Tarefa: T079, T082
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Frequencia = Literal["semanal", "mensal", "anual", "dias"]
EscopoSerie = Literal["apenas_esta", "esta_e_futuras"]
IntervaloParcela = Literal["mensal", "semanal", "quinzenal"]

Dinheiro = Annotated[Decimal, Field(gt=0, decimal_places=2, max_digits=14)]


class RecorrenciaEntrada(BaseModel):
    """Corpo do `POST /api/recorrencias`."""

    mundo: str = Field(description="digital | infra. Obrigatório e imutável (`RN-15`).")
    tipo: Literal["receita", "despesa"]
    descricao: str = Field(min_length=1, max_length=300)
    valor: Dinheiro

    categoria_id: UUID
    subcategoria_id: UUID | None = None
    servico_id: UUID | None = None
    centro_custo_id: UUID | None = None

    frequencia: Frequencia
    intervalo_dias: int | None = Field(default=None, gt=0, le=365)
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    mes_vencimento: int | None = Field(default=None, ge=1, le=12)

    data_inicio: date = Field(
        description="**Pode ser retroativa** (`RF-17a`). Ocorrências até hoje nascem efetivadas."
    )
    data_fim: date | None = None
    total_parcelas: int | None = Field(default=None, gt=0)

    efetivar_automaticamente: bool = Field(
        default=True,
        description=(
            "Herdado pelas ocorrências futuras. Desligado é o que permite a ocorrência "
            "ficar `atrasado` e alimentar a inadimplência (`RN-10`, D-05)."
        ),
    )

    cliente_id: UUID | None = None
    funcionario_id: UUID | None = None

    confirmar_geracao_retroativa: bool = Field(
        default=False,
        description=(
            "Exigido quando a contagem passa de `configuracoes.recorrencia_aviso_ocorrencias` "
            "(`FR-027`). A primeira chamada responde `422` com a prévia."
        ),
    )

    @field_validator("descricao")
    @classmethod
    def _sem_espaco_sobrando(cls, valor: str) -> str:
        limpo = valor.strip()
        if not limpo:
            raise ValueError("A descrição não pode ficar vazia.")
        return limpo


class RecorrenciaEdicao(RecorrenciaEntrada):
    """Corpo do `PUT /api/recorrencias/{id}` (`RN-07`)."""

    escopo_serie: EscopoSerie = Field(
        description=(
            "Obrigatório. `esta_e_futuras` regera só as ocorrências de hoje em diante; "
            "**nenhuma ocorrência passada é alterada** (`RN-07`)."
        )
    )


class PreviaEntrada(BaseModel):
    """Corpo do `POST /api/recorrencias/previa`. **Não grava nada.**

    Só a parte que decide *quando* — valor e categoria não mudam a contagem, e pedi-los
    obrigaria a tela a ter o formulário inteiro preenchido para mostrar a prévia.
    """

    frequencia: Frequencia
    data_inicio: date
    intervalo_dias: int | None = Field(default=None, gt=0, le=365)
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    mes_vencimento: int | None = Field(default=None, ge=1, le=12)
    data_fim: date | None = None
    total_parcelas: int | None = Field(default=None, gt=0)
    valor: Dinheiro | None = Field(
        default=None, description="Opcional: só para somar o total retroativo na prévia."
    )


class ContinuarGeracaoEntrada(BaseModel):
    """Corpo do `POST /api/recorrencias/{id}/continuar-geracao` (D-02a)."""

    cursor: date | None = Field(
        default=None,
        description=(
            "O `cursor` devolvido pela chamada anterior. Informativo: o servidor retoma "
            "de `gerada_ate`, que é o estado real. Serve para o cliente detectar que "
            "está reenviando um cursor velho."
        ),
    )


class ParcelamentoEntrada(BaseModel):
    """Corpo do `POST /api/parcelamentos` (`FR-028`)."""

    mundo: str
    tipo: Literal["receita", "despesa"]
    descricao: str = Field(min_length=1, max_length=300)
    valor_total: Dinheiro = Field(
        description="O total **fechado**. A soma das parcelas bate exatamente com ele."
    )
    total_parcelas: int = Field(ge=2, le=360)
    data_primeira_parcela: date
    intervalo: IntervaloParcela = "mensal"

    categoria_id: UUID
    subcategoria_id: UUID | None = None
    servico_id: UUID | None = None
    centro_custo_id: UUID | None = None

    efetivar_automaticamente: bool = True

    @field_validator("descricao")
    @classmethod
    def _sem_espaco_sobrando(cls, valor: str) -> str:
        limpo = valor.strip()
        if not limpo:
            raise ValueError("A descrição não pode ficar vazia.")
        return limpo
