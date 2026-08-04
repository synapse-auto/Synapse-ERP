"""Configuração do backend, lida de variável de ambiente.

Princípio VII: nenhum `os.environ` solto em nenhum outro arquivo. Quem precisa de
um valor de ambiente importa `configuracao` daqui.

Distinção que importa neste projeto:

- **Segredo** (chave, senha, URL de banco) → variável de ambiente, este arquivo.
- **Parâmetro de negócio** (tolerância de inadimplência, rótulo de card, limite de
  anexo) → tabela `configuracoes` no banco, nunca aqui. Ver `app/configuracoes/`.

Tarefa: T023
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    """Variáveis de ambiente do backend — quickstart.md §4."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Banco ────────────────────────────────────────────────────────────────
    database_url: PostgresDsn = Field(
        description=(
            "Conexão com o Postgres do Supabase. Use o endereço do **pooler em modo "
            "transaction** (porta 6543), não a conexão direta — ver app/db.py."
        )
    )

    # Afinação de conexão. É parâmetro de **infraestrutura**, não de negócio — por
    # isso vive aqui e não na tabela `configuracoes`: quem precisa dele é o processo
    # ao subir, antes de existir banco para consultar.
    db_pool_tamanho: int = Field(
        default=2,
        ge=0,
        description=(
            "Conexões reaproveitadas por processo. `0` volta ao NullPool (uma conexão "
            "nova por requisição). Medido em 2026-08-04: reaproveitar vale 2,1x por "
            "consulta — ver app/db.py."
        ),
    )
    db_pool_transbordo: int = Field(
        default=3,
        ge=0,
        description="Conexões extras além do pool sob pico. Fechadas assim que sobram.",
    )
    db_pool_reciclagem_s: int = Field(
        default=240,
        gt=0,
        description=(
            "Idade máxima de uma conexão. Abaixo do corte de ociosidade do pooler do "
            "Supabase, para o descarte ser nosso e não uma conexão morta na mão."
        ),
    )

    # ── Supabase ─────────────────────────────────────────────────────────────
    supabase_url: str = Field(description="Endereço do projeto Supabase (Settings → API).")

    supabase_service_role_key: str = Field(
        description=(
            "SEGREDO. Ignora todas as políticas do banco. Usada para o Storage dos anexos "
            "e para administrar usuários no Auth. Nunca vai ao frontend."
        )
    )

    # ── Rotinas automáticas ──────────────────────────────────────────────────
    segredo_rotina: str = Field(
        description=(
            "Protege POST /api/rotinas/*, que o Vercel Cron chama sem usuário logado "
            "(contracts/plataforma.md §6). Enviado no cabeçalho X-Segredo-Rotina."
        )
    )

    # ── Câmbio (RN-12) ───────────────────────────────────────────────────────
    cambio_fonte_primaria: str | None = Field(
        default=None,
        description=(
            "Sobrepõe configuracoes.cambio_fonte_primaria em desenvolvimento. "
            "Em produção fica vazia e vale o que está no banco (Princípio VII)."
        ),
    )

    # ── Ambiente ─────────────────────────────────────────────────────────────
    ambiente: Literal["local", "producao"] = Field(default="local")

    versao: str = Field(
        default="0.1.0",
        description="Devolvida por GET /api/saude. Ver `versao_publicada`.",
    )

    # A Vercel injeta esta sozinha. Serve para saber QUAL código está no ar —
    # sem isso, "o deploy subiu" não é verificável (Princípio VI).
    vercel_git_commit_sha: str | None = Field(default=None)

    @field_validator("supabase_url")
    @classmethod
    def _sem_barra_final(cls, valor: str) -> str:
        return valor.rstrip("/")

    @property
    def em_producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def versao_publicada(self) -> str:
        """Versão mais o commit, quando a Vercel informa qual é."""
        if self.vercel_git_commit_sha:
            return f"{self.versao}+{self.vercel_git_commit_sha[:7]}"
        return self.versao

    @property
    def url_jwks(self) -> str:
        """Endereço das chaves públicas que assinam o token do Supabase.

        O projeto usa chave assimétrica (ES256) — conferido em 2026-07-30, o que
        resolve o "a verificar na implementação" de research.md D-03. Por isso não
        existe variável de segredo de JWT aqui: não há segredo compartilhado a
        guardar, só chave pública a buscar.
        """
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"


@lru_cache
def obter_configuracao() -> Configuracao:
    """Lê o ambiente uma vez por processo.

    Em função serverless o processo é reaproveitado entre requisições, então o
    cache evita reler e revalidar o ambiente a cada chamada.
    """
    return Configuracao()  # type: ignore[call-arg]
