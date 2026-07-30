"""Cabeçalho `Idempotency-Key` nos POST de criação — contracts/README.md.

**O problema real**: a Vercel pode repetir uma invocação depois de um timeout de
rede. Um clique lento em "Salvar" viraria dois lançamentos iguais, e num sistema
financeiro isso é um valor contado em dobro no saldo — não um incômodo de interface.

**Como funciona**: o cliente manda uma chave por tentativa. A primeira chamada
registra a chave junto do resultado. Repetição com a mesma chave devolve o resultado
guardado, sem executar de novo.

**Onde a chave é guardada**: na própria tabela `execucoes_rotina`? Não. Numa tabela
nova? Também não — Princípio I. A chave vive numa tabela dedicada mínima, criada
sob demanda pela primeira migração que precisar dela. **Até B1 existir, este módulo
guarda em memória do processo** e diz isso em voz alta abaixo, porque memória de
função serverless não sobrevive entre invocações — que é justamente o caso que a
idempotência precisa cobrir.

⚠️ **LIMITAÇÃO CONHECIDA, a fechar em T056.** O armazenamento em memória protege
contra clique duplo dentro da mesma instância quente, e só. A repetição que a Vercel
faz após timeout costuma cair em instância nova, onde a memória está vazia — o caso
principal ainda não está coberto. O fechamento é uma tabela `chaves_idempotencia`
(`chave` PK, `usuario_id`, `rota`, `resposta` jsonb, `criado_em`) numa migração
`009`, e `T056` (POST /api/lancamentos) é onde ela passa a ser exigida. Registrado
aqui para não passar por pronto o que não está.

Tarefa: T028
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Header

from app.comum.erros import ErroValidacao

# Uma chave repetida depois disso é tratada como tentativa nova. Prazo curto de
# propósito: a janela que interessa é a de uma repetição de rede, medida em
# segundos. Guardar por horas só acumularia lixo.
VALIDADE = timedelta(minutes=10)

TAMANHO_MAXIMO = 200


@dataclass
class _Registro:
    resposta: Any
    criado_em: datetime


@dataclass
class _MemoriaDeChaves:
    """Guarda em memória do processo. Ver a limitação declarada no topo do módulo."""

    registros: dict[tuple[str, str, str], _Registro] = field(default_factory=dict)

    def _limpa_expirados(self, agora: datetime) -> None:
        vencidos = [
            chave for chave, reg in self.registros.items() if agora - reg.criado_em > VALIDADE
        ]
        for chave in vencidos:
            del self.registros[chave]

    def obter(self, chave: tuple[str, str, str]) -> Any | None:
        agora = datetime.now(timezone.utc)
        self._limpa_expirados(agora)
        registro = self.registros.get(chave)
        return registro.resposta if registro else None

    def guardar(self, chave: tuple[str, str, str], resposta: Any) -> None:
        self.registros[chave] = _Registro(resposta=resposta, criado_em=datetime.now(timezone.utc))


_memoria = _MemoriaDeChaves()


def chave_de_idempotencia(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    """Dependência do FastAPI. O cabeçalho é opcional (contracts/README.md)."""
    if idempotency_key is None:
        return None
    chave = idempotency_key.strip()
    if not chave:
        return None
    if len(chave) > TAMANHO_MAXIMO:
        raise ErroValidacao(
            "A chave de idempotência é longa demais.",
            campos={"Idempotency-Key": f"Máximo de {TAMANHO_MAXIMO} caracteres."},
        )
    return chave


def resposta_ja_registrada(chave: str | None, *, rota: str, usuario_id: str) -> Any | None:
    """Resultado guardado desta chave, se houver.

    A chave é escopada por rota e por usuário: a mesma chave em endpoints
    diferentes, ou vinda de pessoas diferentes, são operações diferentes.
    """
    if chave is None:
        return None
    return _memoria.obter((usuario_id, rota, chave))


def registra_resposta(chave: str | None, *, rota: str, usuario_id: str, resposta: Any) -> None:
    """Guarda o resultado para que a repetição devolva o mesmo, sem executar de novo."""
    if chave is None:
        return
    _memoria.guardar((usuario_id, rota, chave), resposta)


def limpa_memoria() -> None:
    """Só para os testes — deixa o estado limpo entre casos."""
    _memoria.registros.clear()
