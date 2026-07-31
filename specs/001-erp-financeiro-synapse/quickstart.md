# Quickstart — Plataforma Financeira Synapse

Como colocar o projeto de pé, rodar local e verificar que funciona de verdade.
Escrito para quem não é engenheiro de software: cada comando diz **o que faz** e **como saber
que deu certo**.

**Pré-requisitos**: Python 3.12, Node 22, conta na Vercel, conta no Supabase, CLI do Supabase.

> **Estado atual (2026-07-31, fim do Boss 2)**: o projeto Supabase (`frpbowkoibdgigekrhor`,
> PostgreSQL 17.6) está **com o banco de pé**: **20 tabelas**, 12 tipos, a view
> `lancamentos_ativos`, RLS de negação para as chaves públicas, **18** configurações e os dados
> iniciais aplicados e conferidos por consulta. Bucket privado `anexos` criado.
>
> Três migrações nasceram depois da Fase A, cada uma no commit em que passou a ser necessária:
>
> | Migração | Quando | Por quê |
> |---|---|---|
> | `009_seed_anexo_url_assinada` | B1/T064 | A URL assinada de anexo precisava de um prazo, e prazo não mora no código (é a 18ª configuração) |
> | `010_ocorrencia_unica_por_data` | B2/T083 | Sem o índice único, a idempotência de D-08 não existe |
> | `011_importacoes` | B6/T133 | A importação em três requisições precisa do conteúdo lido sobrevivendo entre elas (é a 20ª tabela) |
>
> **`list_migrations` devolve 12 registros para 11 arquivos**, e isso é esperado: a
> `006a_rls_revoga_execute_rls_auto_enable` foi aplicada à parte quando o `revoke execute`
> entrou no `006_rls.sql` — o arquivo do repositório **já contém** a linha (006, l. 77), então
> recriar o banco pela sequência do repositório chega ao mesmo estado.
>
> **Conferido em 2026-07-31**: zero tabelas sem RLS, zero `EXECUTE` de `rls_auto_enable` para
> `anon`/`authenticated`, e `get_advisors(security)` com 20 avisos `INFO
> rls_enabled_no_policy` — um por tabela, o resultado que D-03a prevê. Nenhum ERROR ou WARN.
>
> **Falta, e depende do painel do Supabase** (não há API para isso):
>
> 1. **Desabilitar o cadastro público** em Authentication → Sign In / Providers. Conferido em
>    2026-07-30: está **habilitado** (`disable_signup: false`), e `FR-102` exige que só o gestor
>    convide. Ver §2.
> 2. **Confirmar o backup gerenciado** em Database → Backups (`RNF-06`, `FR-112`). Ver §2.

---

## 1. Repositório

```powershell
cd "E:\Projetos Synapse\Synapse\ERP Synapse"
git init
git add .
git commit -m "Especificação, plano e artefatos de desenho do ERP Financeiro"
```

**Por que primeiro**: os dois projetos da Vercel são criados a partir de um repositório
remoto. Sem repositório, não há deploy.

**Como saber que deu certo**: `git log --oneline` mostra um commit.

---

## 2. Supabase

No painel do Supabase, criar o projeto e anotar quatro valores:

| Valor | Onde acha | Para quê |
|---|---|---|
| `SUPABASE_URL` | Settings → API | Endereço do projeto |
| `SUPABASE_ANON_KEY` | Settings → API | Login no navegador. **Pública por natureza** |
| `SUPABASE_SERVICE_ROLE_KEY` | Settings → API | Acesso do backend ao banco. **Segredo** |
| `DATABASE_URL` | Settings → Database | Conexão direta do backend |

> ⚠️ `SUPABASE_SERVICE_ROLE_KEY` ignora todas as políticas de segurança do banco. Ela vive
> **só** em variável de ambiente do backend. Nunca em arquivo commitado, nunca em código do
> frontend, nunca em mensagem de chat.

Ainda no painel:

1. **Authentication** → habilitar e-mail + senha; desabilitar cadastro público (só gestor
   convida — `FR-102`).
2. **Storage** → criar bucket `anexos` **privado**. Público exporia nota fiscal da empresa a
   qualquer um com o link.
3. **Database → Backups** → confirmar que o backup gerenciado está ativo (`RNF-06`).

---

## 3. Banco

As 8 migrações vivem em `backend/migracoes/`, na ordem `001` … `008`, e **já estão aplicadas**
(2026-07-30). Foram aplicadas pelo MCP do Supabase, uma a uma, cada uma registrada no histórico
de migrações do projeto.

> ⚠️ **`supabase db push` não serve para estas migrações.** O CLI do Supabase lê **apenas**
> `supabase/migrations/`, com nome no padrão de timestamp — a pasta não é configurável. Como o
> plano manda os arquivos SQL viverem em `backend/migracoes/` (plan.md §Project Structure),
> `db push` simplesmente não os encontraria. Versão anterior deste guia mandava rodar
> `supabase db push`; era um comando que nunca teria funcionado.
>
> **Para aplicar em um banco novo** (recriar o projeto do zero), rode os arquivos na ordem
> por conexão direta:
>
> ```powershell
> # $env:DATABASE_URL = conexão do passo 2
> Get-ChildItem backend\migracoes\*.sql | Sort-Object Name | ForEach-Object {
>   Write-Host "aplicando $($_.Name)"
>   psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f $_.FullName
> }
> ```
>
> `-v ON_ERROR_STOP=1` é o que importa: sem isso o `psql` segue depois de um erro e o banco
> termina meio aplicado, sem ninguém perceber.

> **Seed `008`**: Dylan e Marcondes entram com `mundo = 'digital'` — confirmado pelo dono do
> projeto em 2026-07-30. O campo é imutável (`RN-15`); mudar depois exige recriar o
> funcionário e a subcategoria dele.

**Como saber que deu certo** — três conferências, não uma:

```sql
-- 1. As chaves de configuração existem (Princípio VII)
select count(*) from configuracoes;                          -- esperado: 17 até a 008, 18 com a 009

-- 2. As categorias especiais nasceram com vínculo (FR-077, FR-078)
select nome, especial, vinculo from categorias where especial;
-- esperado: Clientes/true/cliente e Funcionários/true/funcionario

-- 3. Cada funcionário ganhou subcategoria espelho e recorrência (D-07, FR-088)
select f.nome, s.id as subcategoria, r.id as recorrencia
from funcionarios f
left join subcategorias s on s.funcionario_id = f.id
left join recorrencias  r on r.funcionario_id = f.id;
-- esperado: 2 linhas, nenhuma coluna nula
```

**Conferência de segurança** (research.md D-03a) — com a chave `anon`, não com a de serviço:

```powershell
curl "$env:SUPABASE_URL/rest/v1/lancamentos" -H "apikey: $env:SUPABASE_ANON_KEY"
```

Deve devolver **lista vazia ou erro de permissão**. Se devolver lançamentos, o RLS não está
aplicado e qualquer pessoa com a chave pública lê as finanças da empresa — **pare e corrija
antes de seguir**.

---

## 4. Backend local

```powershell
cd backend
uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r pyproject.toml --extra dev
Copy-Item .env.exemplo .env      # preencher com os valores do passo 2
uvicorn app.main:app --reload --port 8000
```

> ⚠️ **As dependências estão em `pyproject.toml`, não em `requirements.txt`** — este
> não existe mais. Motivo: a Vercel, achando um `pyproject.toml`, instala a partir dele
> e ignora o `requirements.txt`. Com as duas listas coexistindo, a de produção ficaria
> desatualizada sem ninguém notar. Detalhe no cabeçalho de `backend/pyproject.toml`.
>
> `--extra dev` traz uvicorn, pytest, ruff e black; a função publicada recebe só o que
> está em `[project.dependencies]`.
>
> ⚠️ **Não crie o `.env` com `Set-Content` nem com `>`.** O PowerShell escreve UTF-8 com
> BOM, o BOM cola na primeira linha e a primeira variável passa a se chamar
> `﻿DATABASE_URL` — o app sobe reclamando que falta `database_url` com a linha
> visivelmente ali. `Copy-Item` é seguro.

**Como saber que deu certo**:

- `http://localhost:8000/api/saude` → `{"status":"ok","banco":"ok"}`
- `http://localhost:8000/api/docs` → todos os endpoints listados. Esta página **é** a
  documentação que a constituição exige (Princípio IV: endpoint sem documentação não está
  pronto).
- `http://localhost:8000/` e `http://localhost:8000/api` → redirecionam para `/api/docs`.
  Todo endpoint mora sob `/api/...`, então a raiz não casava rota e respondia
  `{"erro":{"codigo":"nao_encontrado", …}}` — o que parece backend quebrado e é o
  contrário: a mensagem é nossa, ou seja, o app está de pé.

### Variáveis de ambiente do backend

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Conexão com o Postgres |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Storage e administração de usuários |
| `SUPABASE_JWT_MODO` / `SUPABASE_JWT_SEGREDO` | Validação do token — conferir no painel qual modo o projeto usa (research.md D-03) |
| `SEGREDO_ROTINA` | Protege `/api/rotinas/*`, chamado pelo cron sem usuário |
| `CAMBIO_FONTE_PRIMARIA` | Sobrepõe a configuração do banco em desenvolvimento |
| `AMBIENTE` | `local` \| `producao` |

Nenhum segredo em arquivo commitado (Princípio VII). `.env` entra no `.gitignore`; o que se
commita é `.env.exemplo`, sem valores.

---

## 5. Frontend local

```powershell
cd frontend
npm install
Copy-Item .env.local.exemplo .env.local
npm run dev
```

| Variável | Valor local |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | do passo 2 |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | do passo 2 — pública por natureza, `NEXT_PUBLIC_` é correto aqui |
| `BACKEND_URL` | `http://localhost:8000` |

`BACKEND_URL` **não** leva `NEXT_PUBLIC_`: ela é usada pelo `rewrites` do `next.config.ts`,
que roda no servidor. O navegador só conhece `/api/*` da própria origem — sem CORS, sem saber
onde o backend mora.

**Como saber que deu certo**: `http://localhost:3000` mostra a tela de entrar; depois do
login, a barra lateral com as 7 abas de `FR-107` e o seletor de mundo no topo.

---

## 6. Testes

```powershell
cd backend
pytest                             # tudo (integrações pulam sem DATABASE_URL)
pytest -m "not integracao"         # só o que não toca banco — é o que roda sempre
pytest tests/unidade/dominio -v    # as regras de negócio críticas
pytest -k "recorrencia_retroativa" # RN-05a isolado
pytest -m lento                    # medição de SC-007 — ver o aviso abaixo

# Frontend
cd frontend
npm run test
```

### ⚠️ As integrações rodam contra o banco de produção

**Decisão do dono do projeto (2026-07-31): não haverá banco separado para teste.** Não é
o arranjo usual, então a proteção precisa estar escrita onde não dá para ignorar.

**O que protege os dados é a transação desfeita.** Cada teste de integração roda dentro de
uma transação que termina em `rollback`, num `finally` — vale inclusive quando o teste
falha no meio. Nada do que eles escrevem chega a existir para qualquer outra conexão.

**O que a proteção não cobre**, e vale saber antes de escrever teste novo:

| Risco | Situação hoje |
|---|---|
| `commit` explícito dentro de um teste | Nenhum tem. Seria a única forma de furar o rollback |
| Bloqueio de linha durante a execução | Os testes criam os próprios dados em vez de mexer nos existentes — por isso fazem assim |
| `analyze`, sequências e o marcador de migração | Não voltam atrás. São estatística e contador, inofensivos |

**Regra para teste novo em `tests/integracao/`**: cria o que precisa (usuário, cliente,
lançamento) e **nunca altera nem apaga linha que já estava lá**. Quem precisar de um dado
existente, leia — não escreva.

**`pytest -m lento` insere milhares de linhas** para medir `SC-007`. Está fora da execução
padrão de propósito: rodá-lo é decisão consciente, e não com alguém usando o sistema.

O lado bom de medir contra produção: o número **vale**. É o Supabase de verdade, com rede
no meio e pooler em modo *transaction* — exatamente o que `SC-007` cobra.

**Os 6 testes que a constituição exige passar** (Princípio VI):

| Teste | Regra | O que prova |
|---|---|---|
| `test_ciclo_status` | `RN-03` | Programado→efetivado/pendente→atrasado, cancelado preserva histórico |
| `test_saldo_ignora_nao_efetivado` | `RN-05` | Programado não entra no saldo realizado |
| `test_recorrencia_retroativa` | `RN-05a` | Início 12 meses atrás gera 12 ocorrências efetivadas (`SC-004`) |
| `test_split_soma_exata` | `RN-11` | Partes que não fecham são recusadas |
| `test_conversao_usd` | `RN-12` | Usa a cotação da data do lançamento, não de hoje |
| `test_separacao_por_mundo` | `RN-15` | Nenhum dado de um mundo aparece no outro (`SC-005`) |

Mais o caso de borda que o `dateutil` não resolve sozinho (research.md §5):

| Teste | O que prova |
|---|---|
| `test_recorrencia_dia_31_em_fevereiro` | Mensal "todo dia 31" cai no último dia do mês |

**Se um teste falha, o relato mostra a saída real do erro** — a constituição proíbe reportar
sucesso parcial como sucesso.

---

## 7. Deploy

Dois projetos na Vercel, mesmo repositório:

| Projeto | Root Directory | Framework |
|---|---|---|
| `synapse-erp-api` | `backend` | Other (runtime Python) |
| `synapse-erp-web` | `frontend` | Next.js |

1. Criar `synapse-erp-api` primeiro e anotar a URL do deploy.
2. Criar `synapse-erp-web` com `BACKEND_URL` = a URL do passo 1.
3. Variáveis de ambiente de cada um conforme §4 e §5.
4. `backend/vercel.json` declara o cron diário chamando `/api/rotinas/diaria` com
   `X-Segredo-Rotina`.

**Como saber que deu certo**:

- `https://<web>.vercel.app/api/saude` → responde. Isso prova que o proxy funciona: a
  resposta vem do backend, mas pelo domínio do frontend.
- Login, criar um lançamento, ver aparecer na lista e mudar o saldo.
- `GET /api/rotinas/estado` (como gestor) mostra a última execução da rotina — se estiver
  vazio no dia seguinte ao deploy, o cron não está disparando.

---

## 8. Verificação de aceitação (o que "pronto" significa)

Antes de declarar a v1 entregue, estes são conferidos **rodando**, não por leitura de código
(Princípio VI). Os números vêm dos Success Criteria da spec.

| # | Verificação | Critério |
|---|---|---|
| 1 | Registrar lançamento completo com anexo | menos de 60 s (`SC-001`) |
| 2 | Abrir o Dashboard e dizer se o mês está positivo e se há conta vencida, sem clicar | menos de 10 s (`SC-002`) |
| 3 | Conferir um mês fechado à mão contra o sistema | diferença de R$ 0,00 (`SC-003`) |
| 4 | Recorrência com início 12 meses atrás | exatamente 12 ocorrências efetivadas (`SC-004`) |
| 5 | Alternar Digital / Infra / Ambos em **todas** as telas | zero dado do mundo errado (`SC-005`) |
| 6 | Cliente que ultrapassa a tolerância | destacado no mesmo dia (`SC-006`) |
| 7 | 5.000 lançamentos, aplicar filtro | resposta em menos de 2 s (`SC-007`) |
| 8 | Percorrer **todas** as telas nos temas claro e escuro | 100% legível (`SC-009`) |
| 9 | Entrar como operador | Configurações e usuários inacessíveis, também pela API direta (`SC-010`) |
| 10 | Exportação completa | menos de 5 min (`SC-011`) |
| 11 | Dashboard e Extrato no celular | sem rolagem horizontal, sem ampliar (`SC-012`) |
| 12 | Mudar tolerância, multiplicadores, antecedências e lista de serviços | comportamento muda sem alterar código (`SC-013`) |
| 13 | Criar, editar e excluir um lançamento | autor e data recuperáveis no detalhe (`SC-014`) |

O item 9 é o único que se verifica **duas vezes**: pela tela e chamando a API direto com o
token de operador. Esconder o menu não é autorizar — se o endpoint responder, a permissão
está furada.
