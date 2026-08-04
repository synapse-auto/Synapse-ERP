"""Cache curto da tabela `configuracoes` — uma consulta no lugar de N.

Skill `supabase-postgres-best-practices` acionada antes de escrever.

## O problema

Princípio VII manda todo parâmetro de negócio vir da tabela `configuracoes`: rótulo
de card, tolerância de inadimplência, horizonte da saúde do caixa, antecedências de
alerta. Está certo, e continua valendo — **este arquivo não muda de onde o valor
vem**, muda quantas vezes ele é buscado.

`le_configuracao` fazia uma ida ao banco **por chave**. `pg_stat_statements` contou
2399 execuções de `select valor from configuracoes where chave = $1`, somando 0,07 ms
de banco cada — irrelevante — mas **uma viagem de rede cada**, que é o que custa. Só
o Dashboard pede quatro chaves e paga quatro viagens.

## A troca

Primeira leitura traz a tabela **inteira** (18 linhas, poucos kB) numa consulta. As
seguintes saem da memória do processo enquanto o prazo não vence.

`VALIDADE_S = 60` não é chute: é o maior atraso aceitável entre um gestor salvar em
`PATCH /api/configuracoes` e a mudança aparecer para os outros dois usuários. Quem
salvou vê na hora — `invalida()` é chamado na própria requisição de escrita.

## O que este cache NÃO promete

Em serverless há vários processos vivos ao mesmo tempo, e `invalida()` só limpa o
**deste**. Outra instância pode servir o valor antigo até o prazo vencer. Para
tolerância de inadimplência e rótulo de card, até 60 segundos de atraso é
indiferente. **Se algum dia entrar aqui uma chave em que o atraso importe** — algo
que decida permissão, por exemplo —, ela não pode passar por este caminho: leia
direto do banco.
"""

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

VALIDADE_S = 60.0

_valores: dict[str, Any] | None = None
_carregado_em: float = 0.0


def invalida() -> None:
    """Descarta o cache. Chamado por quem escreve em `configuracoes`."""
    global _valores, _carregado_em
    _valores = None
    _carregado_em = 0.0


async def _carrega(conexao: AsyncConnection) -> dict[str, Any]:
    global _valores, _carregado_em
    linhas = (await conexao.execute(text("select chave, valor from configuracoes"))).all()
    _valores = {chave: valor for chave, valor in linhas}
    _carregado_em = time.monotonic()
    return _valores


async def todas(conexao: AsyncConnection) -> dict[str, Any]:
    """Toda a tabela, do cache ou do banco."""
    if _valores is not None and (time.monotonic() - _carregado_em) < VALIDADE_S:
        return _valores
    return await _carrega(conexao)


async def le(conexao: AsyncConnection, chave: str, padrao: Any = None) -> Any:
    """Uma chave. `padrao` vale para chave ausente **e** para valor nulo."""
    valor = (await todas(conexao)).get(chave)
    return padrao if valor is None else valor
