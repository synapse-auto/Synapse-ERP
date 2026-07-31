"""PDF dos relatórios (`FR-094`), com reportlab.

**Sem pandas, sem matplotlib, sem weasyprint.** O pacote da função da Vercel tem tamanho
limitado (plan.md §Constraints) e as três alternativas passam disso sozinhas — weasyprint
ainda arrasta bibliotecas de sistema que a função não tem. reportlab desenha a tabela
direto no PDF, sem passar por HTML.

Como no CSV, **os mesmos números do `json`**: estas funções recebem a resposta já montada
pelo endpoint. Um segundo caminho até o dado é um segundo lugar onde ele pode divergir.

O import de reportlab é **preguiçoso**, dentro da função. Assim o resto da API sobe mesmo
se a biblioteca faltar no ambiente, e quem pede PDF recebe um erro em PT-BR dizendo o que
houve — em vez de a função inteira morrer no import com um 500 mudo, que foi o que
aconteceu no primeiro deploy (README do backend).

Tarefa: T120
"""

import io
from typing import Any

from app.comum.erros import ErroDaApi

LARGURA_PAGINA = 595  # A4 em pontos
MARGEM = 40


class ErroDePdf(ErroDaApi):
    """503 — a geração de PDF não está disponível neste ambiente."""

    status = 503
    codigo = "fonte_externa_indisponivel"


def _componentes():
    """Importa reportlab só quando alguém pede PDF de verdade."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as erro:  # pragma: no cover — depende do ambiente
        raise ErroDePdf(
            "A geração de PDF não está disponível agora. Exporte em CSV — são os mesmos "
            "números.",
            requisito="FR-094",
        ) from erro

    return {
        "colors": colors,
        "A4": A4,
        "estilos": getSampleStyleSheet(),
        "mm": mm,
        "Paragraph": Paragraph,
        "SimpleDocTemplate": SimpleDocTemplate,
        "Spacer": Spacer,
        "Table": Table,
        "TableStyle": TableStyle,
    }


def _numero(texto: str | None) -> str:
    if texto is None:
        return ""
    inteiro, _, decimais = str(texto).partition(".")
    negativo = inteiro.startswith("-")
    inteiro = inteiro.lstrip("-")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro or "0")
    return f"{'-' if negativo else ''}R$ {'.'.join(grupos)},{decimais or '00'}"


def monta(
    *, titulo: str, subtitulo: str, cabecalho: list[str], linhas: list[list[str]], rodape: str = ""
) -> bytes:
    """Uma tabela por PDF. Simples de propósito (Princípio I).

    A spec não pede gráfico no PDF; pede os mesmos dados do `json`. Desenhar gráfico
    aqui exigiria matplotlib, que não cabe no pacote da função.
    """
    peças = _componentes()
    buffer = io.BytesIO()

    documento = peças["SimpleDocTemplate"](
        buffer,
        pagesize=peças["A4"],
        leftMargin=MARGEM,
        rightMargin=MARGEM,
        topMargin=MARGEM,
        bottomMargin=MARGEM,
        title=titulo,
        author="Plataforma Financeira Synapse",
    )

    estilos = peças["estilos"]
    corpo = [
        peças["Paragraph"](titulo, estilos["Title"]),
        peças["Paragraph"](subtitulo, estilos["Normal"]),
        peças["Spacer"](1, 12),
    ]

    tabela = peças["Table"]([cabecalho, *linhas], repeatRows=1)
    tabela.setStyle(
        peças["TableStyle"](
            [
                # Roxo do design system (`#8B6CF0`) no cabeçalho: o PDF é material da
                # empresa e sai com a identidade dela.
                ("BACKGROUND", (0, 0), (-1, 0), peças["colors"].HexColor("#8B6CF0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), peças["colors"].white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.25, peças["colors"].HexColor("#DDD8EC")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [peças["colors"].white, peças["colors"].HexColor("#F7F5FB")],
                ),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    corpo.append(tabela)

    if rodape:
        corpo.append(peças["Spacer"](1, 12))
        corpo.append(peças["Paragraph"](rodape, estilos["Italic"]))

    documento.build(corpo)
    return buffer.getvalue()


def dre(resposta: dict[str, Any], *, periodo_rotulo: str) -> bytes:
    linhas: list[list[str]] = []
    for bloco, rotulo in (("receitas", "Receita"), ("despesas", "Despesa")):
        for categoria in resposta.get(bloco, []):
            linhas.append([f"{rotulo} — {categoria['nome']}", _numero(categoria["valor"])])
            for sub in categoria.get("subcategorias", []):
                linhas.append([f"    {sub['nome']}", _numero(sub["valor"])])

    linhas.append(["", ""])
    linhas.append(["Receita bruta", _numero(resposta["receita_bruta"])])
    linhas.append(["Despesa total", _numero(resposta["despesa_total"])])
    linhas.append(["Resultado", _numero(resposta["resultado"])])

    return monta(
        titulo="DRE — Plataforma Financeira Synapse",
        subtitulo=periodo_rotulo,
        cabecalho=["Conta", "Valor"],
        linhas=linhas,
        rodape=resposta.get("leitura_linguagem_natural", ""),
    )


def clientes(resposta: dict[str, Any], *, periodo_rotulo: str) -> bytes:
    linhas = [
        [
            item["nome"],
            _numero(item["total_recebido"]),
            f"{(item.get('percentual_faturamento') or '0').replace('.', ',')}%",
            "Atrasado" if item["situacao"] == "atrasado" else "Em dia",
        ]
        for item in resposta["clientes"]
    ]
    return monta(
        titulo="Clientes por receita",
        subtitulo=periodo_rotulo,
        cabecalho=["Cliente", "Total recebido", "% do faturamento", "Situação"],
        linhas=linhas,
    )
