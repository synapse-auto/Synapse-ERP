"""Exportação completa — `FR-112`, `SC-011`. ZIP com um CSV por tabela.

Papel: **gestor**. É a cópia de segurança que o dono do projeto leva embora se um dia
quiser trocar de sistema — e por isso não pode depender de nada nosso para ser lida: são
CSVs, abertos em qualquer planilha.

## É síncrono, e isso é uma troca declarada

O desenho original (contracts/plataforma.md §8, T137) previa gravação **por lote com
cursor** e um `GET /api/exportacoes/{id}` para acompanhar — o mesmo padrão das recorrências
longas. Não é o que está aqui: uma chamada monta o ZIP inteiro na memória e devolve.

Para a escala deste sistema — 3 usuários, dezenas a poucas centenas de lançamentos por mês —
o arquivo fica em poucos megabytes e cabe com folga numa invocação. O caminho assíncrono
exigiria estado no banco, URL assinada, objeto a limpar depois e um segundo endpoint; não
paga (Princípio I).

**O limite disso, dito na cara**: quando o histórico crescer o bastante para a montagem
passar da duração máxima da função (plan.md §Constraints), este endpoint passa a **falhar**,
não a ficar lento — e aí o formato por lote volta a ser necessário para garantir `SC-011`.
A medição de T210 é o que detecta isso antes do usuário.

O contrato foi corrigido para descrever o que existe (auditoria de 2026-07-31); não é
divergência silenciosa.

## O que não entra no pacote

- **Os arquivos anexados.** São objetos do bucket privado, e embutir dezenas de PDFs
  estouraria a memória da função. `anexos.csv` traz o caminho de cada um; o link assinado
  sai por `/api/anexos/{id}`, como em qualquer outro lugar. Redução declarada em relação ao
  texto de `RNF-06`/`FR-112` — registrada no §17.1 do documento-mestre.
- **A tabela `importacoes`.** É rascunho de três etapas que expira em 24h, não histórico
  financeiro. Exportar rascunho descartável só confundiria quem abrisse o pacote.

Tarefa: T137
"""

import csv
import io
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# Uma consulta por tabela, na ordem em que faz sentido ler. `lancamentos` primeiro
# porque é o que alguém abre primeiro.
TABELAS: tuple[str, ...] = (
    "lancamentos",
    "recorrencias",
    "parcelamentos",
    "categorias",
    "subcategorias",
    "clientes",
    "clientes_servicos",
    "funcionarios",
    "servicos",
    "centros_custo",
    "tags",
    "lancamentos_tags",
    "anexos",
    "usuarios",
    "configuracoes",
    "auditoria",
    "cotacoes_cambio",
    "execucoes_rotina",
    "notificacoes",
)

# Colunas que não saem: segredo não vai para arquivo que sai da empresa.
COLUNAS_OMITIDAS: dict[str, tuple[str, ...]] = {
    "usuarios": ("preferencias",),
}


def _escreve_csv(colunas: list[str], linhas: list[dict[str, Any]]) -> bytes:
    """Aqui o CSV é **de dados, não de leitura humana**.

    Diferente do CSV de relatório: este é cópia de segurança e pode ser reimportado, então
    sai em formato de transporte — vírgula, `1234.56`, data ISO. Misturar as duas
    convenções faria a cópia perder precisão.
    """
    buffer = io.StringIO(newline="")
    escritor = csv.writer(buffer, lineterminator="\r\n")
    escritor.writerow(colunas)
    for linha in linhas:
        escritor.writerow(
            ["" if linha[coluna] is None else str(linha[coluna]) for coluna in colunas]
        )
    return buffer.getvalue().encode("utf-8")


async def exporta_tabela(conexao: AsyncConnection, tabela: str) -> tuple[list[str], list[dict]]:
    """Uma tabela inteira.

    O nome da tabela entra na consulta por interpolação, e é seguro **porque vem de
    `TABELAS`**, uma tupla fechada no código — nunca do cliente. É o único lugar do
    projeto onde isso acontece, e a razão está aqui escrita.
    """
    if tabela not in TABELAS:
        raise ValueError(f"Tabela '{tabela}' não está na lista de exportação.")

    linhas = (await conexao.execute(text(f"select * from {tabela}"))).mappings().all()  # noqa: S608
    if not linhas:
        return [], []

    omitidas = set(COLUNAS_OMITIDAS.get(tabela, ()))
    colunas = [coluna for coluna in linhas[0].keys() if coluna not in omitidas]
    return colunas, [dict(linha) for linha in linhas]


async def monta_zip(conexao: AsyncConnection) -> tuple[bytes, dict[str, int]]:
    """O ZIP inteiro, com um CSV por tabela. Devolve também a contagem por tabela."""
    buffer = io.BytesIO()
    contagens: dict[str, int] = {}

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as pacote:
        for tabela in TABELAS:
            colunas, linhas = await exporta_tabela(conexao, tabela)
            contagens[tabela] = len(linhas)
            if not colunas:
                # Tabela vazia entra assim mesmo, com o cabeçalho: a ausência do arquivo
                # faria quem abrir o ZIP achar que a exportação falhou.
                pacote.writestr(f"{tabela}.csv", _escreve_csv(["(vazia)"], []))
                continue
            pacote.writestr(f"{tabela}.csv", _escreve_csv(colunas, linhas))

        pacote.writestr(
            "LEIA-ME.txt",
            (
                "Exportação completa — Plataforma Financeira Synapse\n"
                f"Gerada em {datetime.now(timezone.utc).isoformat()}\n\n"
                "Um CSV por tabela, em formato de dados (separador vírgula, decimal com "
                "ponto, datas em ISO 8601). É a sua cópia: abre em qualquer planilha e não "
                "depende de nada nosso para ser lida.\n\n"
                "Os arquivos anexados NÃO estão neste pacote — anexos.csv traz o caminho "
                "de cada um no armazenamento.\n\n"
                "Também fica de fora a tabela de importações: ela guarda o rascunho de um "
                "arquivo em processo de importação, expira em 24 horas e não é histórico "
                "financeiro. O que virou lançamento está em lancamentos.csv.\n\n"
                "Contagem por tabela:\n"
                + "\n".join(f"  {tabela}: {total}" for tabela, total in contagens.items())
            ).encode("utf-8"),
        )

    return buffer.getvalue(), contagens
