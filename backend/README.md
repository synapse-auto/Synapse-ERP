# Backend — Plataforma Financeira Synapse

FastAPI + SQLAlchemy 2 Core + asyncpg sobre o Postgres do Supabase. Publicado como
função Python na Vercel; o Next.js faz proxy de `/api/*` para cá (research.md D-02).

Contexto do projeto: [`CLAUDE.md`](../CLAUDE.md) ·
[constituição](../.specify/memory/constitution.md) ·
[plano](../specs/001-erp-financeiro-synapse/plan.md) ·
[contratos](../specs/001-erp-financeiro-synapse/contracts/)

## Como rodar

```powershell
cd backend
uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r pyproject.toml --extra dev
Copy-Item .env.exemplo .env      # preencher com os valores do Supabase
uvicorn app.main:app --reload --port 8000
```

> **Não existe `requirements.txt` neste projeto, e é de propósito.** As dependências
> vivem em [`pyproject.toml`](pyproject.toml), porque é de lá que a **Vercel** instala:
> havendo um `pyproject.toml`, ela ignora o `requirements.txt` por completo. Manter os
> dois seria manter duas listas da mesma coisa — e a que ficaria desatualizada é
> justamente a que roda em produção. Custou um deploy quebrado para descobrir; o
> histórico está no cabeçalho do `pyproject.toml`.
>
> `--extra dev` traz uvicorn, pytest, ruff e black. **A função da Vercel não os
> instala** — lá vai só o que está em `[project.dependencies]`.

- `http://localhost:8000/api/saude` → `{"status":"ok","banco":"ok","versao":"…"}`
- `http://localhost:8000/api/docs` → a documentação que o Princípio IV exige

> ⚠️ **Não crie o `.env` com `Set-Content` nem com `>` no PowerShell.** O Windows
> PowerShell escreve UTF-8 **com BOM**, e o BOM cola na primeira linha do arquivo: a
> primeira variável passa a se chamar `﻿DATABASE_URL` e o app sobe reclamando que
> `database_url` está faltando — mesmo com a linha visivelmente ali. Custou uma
> depuração real durante o B0.
>
> `Copy-Item .env.exemplo .env` é seguro (copia byte a byte, e o exemplo não tem BOM).
> Se precisar gerar por script:
>
> ```powershell
> [System.IO.File]::WriteAllText("$PWD\.env", $conteudo, (New-Object System.Text.UTF8Encoding($false)))
> ```

```powershell
pytest                       # tudo
pytest -m "not integracao"   # sem precisar de Postgres
ruff check . ; black --check .
```

## Onde as coisas moram

| Pasta | Responsabilidade |
|---|---|
| `app/dominio/` | **Todas** as `RN-xx`, um módulo por regra. Nenhuma regra fora daqui |
| `app/comum/` | Erro, paginação, período, idempotência, auditoria |
| `app/seguranca/` | `auth.py` valida o token; `rbac.py` decide o papel |
| `app/<dominio>/` | `rotas.py` → `servico.py` → `repositorio.py`, nessa ordem de dependência |
| `migracoes/` | SQL versionado, `001`…`008` (data-model §7) |
| `api/index.py` | Só reexporta o app para a Vercel |

Camada de tela **nunca** fala com o banco, e `repositorio.py` **nunca** contém regra de
negócio (Princípio IV).

## Decisões que surpreendem quem lê o código pela primeira vez

**`NullPool` — o backend não mantém pool.** Quem faz o pooling é o pgbouncer do
Supabase. Pool em memória de função serverless acumula conexão morta. Ver o cabeçalho
de [`app/db.py`](app/db.py).

**Prepared statement desligado.** No pooler em modo *transaction* a conexão troca entre
requisições e o statement preparado não existe na nova. `DATABASE_URL` tem que apontar
para a **porta 6543**, não a 5432.

**Só ES256 é aceito no token.** O projeto usa chave assimétrica (JWKS) — conferido em
2026-07-30, fecha o "a verificar" de research.md D-03. Não há segredo de JWT em
ambiente: o que se busca é chave pública. Nenhum caminho HS256 foi escrito.

**Token válido não basta.** O papel mora em `usuarios`, não no token. Sem linha ativa
lá, a resposta é `401` — é o que impede que alguém que se cadastre sozinho no Auth
entre no sistema.

**RLS está ligada sem nenhuma política, e é assim de propósito.** Ver
[`migracoes/006_rls.sql`](migracoes/006_rls.sql). O linter do Supabase aponta
`rls_enabled_no_policy` nas 19 tabelas; é o resultado esperado.

## Por que `vercel.json` não tem `rewrites`

Tentador escrever `{"source": "/(.*)", "destination": "/api/index"}` para mandar tudo
para a função. **Não faça isso.** O build avisa:

> WARNING! Internal rewrites in backend framework projects now route requests using the
> rewritten destination path.

Ou seja: a Vercel entrega ao app o caminho **já reescrito**. Pedindo `/api/saude`, o
FastAPI recebe `/api/index` — que não existe — e devolve 404 em **toda** rota. O sintoma
engana, porque o app está vivo e respondendo; só nunca casa nenhuma rota.

Com o preset **FastAPI** (Settings → General → Framework), a Vercel já roteia todos os
caminhos para o app. O `vercel.json` só declara o cron.

## ⚠️ Duas divergências abertas entre o contrato e a plataforma

Declaradas em voz alta porque a constituição não aceita resolver conflito em silêncio.

### 1. O Vercel Cron não consegue chamar `POST` com `X-Segredo-Rotina`

`contracts/plataforma.md §6` especifica
`POST /api/rotinas/diaria` protegido pelo cabeçalho `X-Segredo-Rotina`. A plataforma
não permite isso: o Vercel Cron invoca o caminho com **`GET`** e **não envia cabeçalho
personalizado** — ele envia `Authorization: Bearer $CRON_SECRET` quando a variável
`CRON_SECRET` existe no projeto.

**Encaminhamento proposto, a implementar em `T084`** (sub-fase B2):

- `POST /api/rotinas/diaria` + `X-Segredo-Rotina` — permanece como o contrato diz,
  para disparo manual.
- `GET /api/rotinas/diaria` — aceito só para o cron, validando
  `Authorization: Bearer <segredo>`.
- Os dois conferem o **mesmo** segredo, com comparação de tempo constante
  (`rbac.exige_segredo_de_rotina`). Na Vercel, `CRON_SECRET` e `SEGREDO_ROTINA`
  recebem o mesmo valor.

`contracts/plataforma.md` precisa registrar o `GET` quando `T084` for feito — senão
`/api/docs` e o contrato divergem, o que T208 trata como bug.

### 2. Idempotência ainda não cobre o caso principal

[`app/comum/idempotencia.py`](app/comum/idempotencia.py) guarda a chave **em memória do
processo**. Isso cobre clique duplo na mesma instância quente e nada mais. A repetição
que a Vercel faz após timeout de rede — o motivo de o mecanismo existir — normalmente
cai em instância nova, com memória vazia.

**Fechamento**: tabela `chaves_idempotencia` numa migração `009`, exigida a partir de
`T056` (`POST /api/lancamentos`). Até lá, o mecanismo está incompleto e isso está dito
no próprio módulo.

## Variáveis de ambiente

Lista completa e comentada em [`.env.exemplo`](.env.exemplo). Nenhum `os.environ` solto
no código: quem precisa importa `app.config.obter_configuracao` (Princípio VII).
