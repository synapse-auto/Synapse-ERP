"""Formato único de erro da API — contracts/README.md §Erros.

O contrato:

    { "erro": { "codigo": "regra_violada",
                "mensagem": "A soma das partes (R$ 480,00) não fecha com o valor do
                             lançamento (R$ 500,00).",
                "requisito": "RN-11",
                "campos": { "partes": "Faltam R$ 20,00." } } }

Duas regras que este arquivo existe para garantir:

- **`mensagem` é texto PT-BR pronto para a tela.** O frontend mostra o que veio e
  não monta frase de regra de negócio (`RNF-02`, Princípio VII). Quem sabe por que
  a operação foi recusada é o domínio, então é o domínio que escreve a frase.
- **`requisito` cita o código de origem** (`RN-11`, `FR-027`…), o que torna o erro
  rastreável até o documento-mestre.

Dinheiro aparece na mensagem no formato brasileiro (`R$ 1.234,56`) porque é texto de
apresentação — diferente do transporte de dados, que é string decimal (`"1234.56"`).
`formata_dinheiro` está aqui para as mensagens não divergirem entre módulos.

Tarefa: T025
"""

from decimal import Decimal
from typing import Any


def formata_dinheiro(valor: Decimal | int | str) -> str:
    """`Decimal("1234.5")` → `"R$ 1.234,50"`. Só para texto de mensagem de erro."""
    numero = Decimal(str(valor)).quantize(Decimal("0.01"))
    inteiro, _, centavos = f"{abs(numero):.2f}".partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    sinal = "-" if numero < 0 else ""
    return f"{sinal}R$ {'.'.join(grupos)},{centavos}"


class ErroDaApi(Exception):
    """Base de todo erro que vira resposta de API.

    Quem levanta informa a mensagem em PT-BR e o requisito. O `status` e o `codigo`
    vêm da subclasse — assim não existe endpoint escolhendo o código HTTP na mão e
    errando (por exemplo devolvendo 400 numa regra de negócio, que é 409).
    """

    status: int = 500
    codigo: str = "erro_interno"

    def __init__(
        self,
        mensagem: str,
        *,
        requisito: str | None = None,
        campos: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.requisito = requisito
        self.campos = campos
        # `extra` carrega o que alguns erros precisam anexar ao corpo — hoje só a
        # `previa` do 422 (contracts/README.md §Confirmação em duas etapas).
        self.extra = extra or {}

    def como_corpo(self) -> dict[str, Any]:
        erro: dict[str, Any] = {"codigo": self.codigo, "mensagem": self.mensagem}
        # `null` explícito em vez de campo omitido — contracts/README.md §Ausência.
        erro["requisito"] = self.requisito
        erro["campos"] = self.campos
        erro.update(self.extra)
        return {"erro": erro}


# ── Os 10 códigos da tabela de contracts/README.md ───────────────────────────


class ErroValidacao(ErroDaApi):
    """400 — corpo malformado, tipo errado, valor fora do domínio."""

    status = 400
    codigo = "validacao"


class ErroNaoAutenticado(ErroDaApi):
    """401 — token ausente, expirado ou inválido."""

    status = 401
    codigo = "nao_autenticado"


class ErroSemPermissao(ErroDaApi):
    """403 — papel insuficiente (`RF-02`)."""

    status = 403
    codigo = "sem_permissao"


class ErroNaoEncontrado(ErroDaApi):
    """404 — inexistente, excluído ou de outro escopo.

    "De outro escopo" junto com "inexistente" é deliberado: responder 403 para
    registro que existe mas não é seu já conta que ele existe.
    """

    status = 404
    codigo = "nao_encontrado"


class ErroConflitoVersao(ErroDaApi):
    """409 — edição concorrente (data-model §5.6).

    `mudancas` diz o que mudou desde a leitura, para a tela mostrar em vez de só
    recusar. Sem isso a última gravação apagaria a anterior em silêncio.
    """

    status = 409
    codigo = "conflito_versao"

    def __init__(
        self,
        mensagem: str,
        *,
        versao_atual: int,
        mudancas: dict[str, Any] | None = None,
        requisito: str | None = None,
    ) -> None:
        super().__init__(
            mensagem,
            requisito=requisito,
            extra={"versao_atual": versao_atual, "mudancas": mudancas},
        )


class ErroRegraViolada(ErroDaApi):
    """409 — uma `RN-xx` recusou a operação.

    `requisito` é obrigatório aqui: regra de negócio sem código de origem não é
    rastreável até o documento-mestre, e a constituição exige que seja.
    """

    status = 409
    codigo = "regra_violada"

    def __init__(
        self,
        mensagem: str,
        *,
        requisito: str,
        campos: dict[str, str] | None = None,
    ) -> None:
        super().__init__(mensagem, requisito=requisito, campos=campos)


class ErroArquivoGrande(ErroDaApi):
    """413 — anexo acima de `configuracoes.anexo_tamanho_max_mb` (`FR-013`)."""

    status = 413
    codigo = "arquivo_grande"


class ErroFormatoNaoSuportado(ErroDaApi):
    """415 — anexo fora de `configuracoes.anexo_mime_permitidos` (`FR-013`)."""

    status = 415
    codigo = "formato_nao_suportado"


class ErroConfirmacaoNecessaria(ErroDaApi):
    """422 — a operação exige confirmação explícita antes de executar.

    Primeira chamada responde 422 descrevendo o impacto; o cliente reenvia com o
    campo de confirmação. Usado por `FR-027` (recorrência retroativa), pela edição
    de ocorrência passada e pelo arquivamento de categoria com lançamentos
    (`RN-06`).
    """

    status = 422
    codigo = "confirmacao_necessaria"

    def __init__(
        self,
        mensagem: str,
        *,
        requisito: str,
        previa: dict[str, Any] | None = None,
        campo_confirmacao: str | None = None,
    ) -> None:
        extra: dict[str, Any] = {"previa": previa}
        if campo_confirmacao:
            extra["campo_confirmacao"] = campo_confirmacao
        super().__init__(mensagem, requisito=requisito, extra=extra)


class ErroFonteExternaIndisponivel(ErroDaApi):
    """502 — a cotação de câmbio não respondeu (`RN-12`).

    Não é falha nossa nem do usuário: as duas fontes de cotação falharam. A
    mensagem deve dizer que a saída é informar a cotação à mão, senão o usuário
    fica sem entender o que fazer.
    """

    status = 502
    codigo = "fonte_externa_indisponivel"
