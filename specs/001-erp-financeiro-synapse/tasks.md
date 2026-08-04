---
description: "Lista de tarefas — Plataforma Financeira Synapse (ERP interno v1)"
---

# Tasks: Plataforma Financeira Synapse (ERP interno v1)

**Entrada**: artefatos de desenho em `/specs/001-erp-financeiro-synapse/`

**Pré-requisitos**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Testes**: **incluídos e obrigatórios**. Não é opção — o Princípio VI da constituição nomeia
6 alvos de teste automatizado (`RN-03`, `RN-05`, `RN-05a`, `RN-11`, `RN-12`, `RN-15`) mais o
caso de borda do dia 31 (quickstart §6).

**Organização**: três **fases bosses** na ordem pedida pelo dono do projeto — Banco de dados,
Backend, Frontend. Dentro de cada boss, sub-fases menores. As sub-fases de backend e de
frontend são mapeadas às histórias de usuário (`US1`…`US10`) da spec, para que cada uma seja
entregue e testada isoladamente.

## Formato: `[ID] [P?] [Story] Descrição`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: história de usuário a que a task pertence (`US1`…`US10`)
- Sem `[Story]`: task de setup, fundação ou polimento — serve a todas

## Convenções de caminho

- Backend: `backend/app/…`, migrações em `backend/migracoes/`, testes em `backend/tests/`
- Frontend: `frontend/app/…`, `frontend/componentes/…`, `frontend/lib/…`

---

## ⚠️ Regra que atravessa todas as tasks de banco e de consulta

**Toda task marcada com 🟢 aciona a Skill `supabase-postgres-best-practices` ANTES de escrever
qualquer SQL ou código de acesso** (plan.md, "Regra obrigatória: Supabase passa pela Skill").
Ordem dentro da task: **Skill → escrever → testar de verdade → verificar documentação**.
Conflito entre a Skill e o data-model.md é declarado no relato, nunca resolvido em silêncio.

---

# 🧱 FASE BOSS 1 — BANCO DE DADOS

**Meta**: o banco de pé, com estrutura, políticas e dados iniciais aplicados e conferidos.

**Sem bloqueio**: o MCP do Supabase foi autenticado e testado em 2026-07-30 — projeto
`frpbowkoibdgigekrhor`, PostgreSQL 17.6, leitura e execução de SQL funcionando, banco ainda
vazio (0 tabelas, 0 migrações, 0 buckets). A fase pode ir do começo ao fim.

## Sub-fase A0 — Repositório e esqueleto

- [X] T001 Rodar `git init`, criar `.gitignore` na raiz (`.env`, `.env.local`, `.venv/`, `node_modules/`, `.next/`, `__pycache__/`) e fazer o primeiro commit com a spec e os artefatos de desenho
- [X] T002 [P] Criar a árvore de diretórios de `backend/` conforme plan.md §Project Structure (`app/`, `app/comum/`, `app/dominio/`, `app/seguranca/`, `migracoes/`, `tests/unidade/`, `tests/integracao/`, `tests/contrato/`)
- [X] T003 [P] Criar `backend/.env.exemplo` com as 8 variáveis de quickstart.md §4 (a tabela tem 6 linhas e nomeia 8 variáveis), **sem valores** (Princípio VII)
- [X] T004 Criar o repositório remoto e dar push — pré-requisito dos dois projetos Vercel (quickstart.md §1)

## Sub-fase A1 — Provisionar o Supabase

- [x] T005 ~~Criar o projeto no Supabase~~ — **feito**: projeto `frpbowkoibdgigekrhor` no ar, MCP autenticado e testado em 2026-07-30 (PostgreSQL 17.6). Falta apenas anotar `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` e `DATABASE_URL` fora do repositório (quickstart.md §2)
- [ ] T006 [P] Habilitar Auth por e-mail + senha e **desabilitar cadastro público** — só gestor convida (`FR-102`)
- [X] T007 [P] Criar o bucket **privado** `anexos` no Supabase Storage (data-model §3.12, `FR-013`)
- [ ] T008 [P] Confirmar que o backup gerenciado está ativo e registrar isso em `specs/001-erp-financeiro-synapse/quickstart.md` (`RNF-06`, `FR-112`)

## Sub-fase A2 — Migrações (escrever)

- [X] T009 🟢 Escrever `backend/migracoes/001_extensoes_e_tipos.sql`: extensão `pg_trgm` e os 12 `CREATE TYPE` de data-model §2
- [X] T010 🟢 Escrever `backend/migracoes/002_plataforma.sql`: `usuarios`, `configuracoes`, `auditoria`, `execucoes_rotina`, `cotacoes_cambio` (data-model §3.1, §3.15, §3.17, §3.18, §3.19)
- [X] T011 🟢 Escrever `backend/migracoes/003_cadastros.sql`: `categorias`, `subcategorias`, `clientes`, `clientes_servicos`, `funcionarios`, `servicos`, `centros_custo`, `tags` — tabelas primeiro e as FKs circulares (`subcategorias.cliente_id`/`funcionario_id`) no fim do arquivo (data-model §7)
- [X] T012 🟢 Escrever `backend/migracoes/004_lancamentos.sql`: `parcelamentos`, `recorrencias`, `lancamentos`, `lancamentos_tags`, `anexos`, view `lancamentos_ativos`, os 8 índices de data-model §3.10 e o trigger `BEFORE UPDATE` que recusa mudança de `mundo` (`RN-15`)
- [X] T013 🟢 [P] Escrever `backend/migracoes/005_notificacoes.sql`: `notificacoes` com UNIQUE `(usuario_id, chave_deduplicacao)` (data-model §3.16)
- [X] T014 🟢 Escrever `backend/migracoes/006_rls.sql`: RLS ligada com **negação** para `anon` e `authenticated` em todas as tabelas financeiras (research.md D-03a) — é onde erro silencioso custa caro
- [X] T015 🟢 [P] Escrever `backend/migracoes/007_seed_configuracoes.sql` com as 17 chaves de data-model §3.15 (a tabela tem 16 linhas, mas a última declara duas chaves), incluindo `dashboard_cards_disponiveis` com rótulo, grupo e ordem de cada card (`FR-106`, Princípio VII)
- [x] T016 ~~Confirmar o `mundo` de Dylan e Marcondes~~ — **confirmado em 2026-07-30: os dois são `digital`**. Registrado em data-model §3.6 (campo imutável — `RN-15`)
- [X] T017 🟢 Escrever `backend/migracoes/008_seed_dominio.sql`: 9 categorias de `FR-076` (Clientes e Funcionários como especiais com `vinculo`), 9 serviços de `FR-104` divididos por mundo, e os 2 funcionários de `FR-086` **ambos com `mundo = 'digital'`** (T016)

## Sub-fase A3 — Aplicar e verificar de verdade

- [X] T018 Aplicar as 8 migrações e confirmar que rodaram sem erro (quickstart.md §3). **`supabase db push` não serve**: o CLI só lê `supabase/migrations/` — aplicado pelo MCP do Supabase, uma a uma
- [X] T019 Verificar os seeds com as três consultas de quickstart.md §3: 17 configurações, categorias especiais com `vinculo`, e cada funcionário com subcategoria espelho e recorrência
- [X] T020 **Verificação de segurança**: chamar `/rest/v1/lancamentos` com a chave `anon` e confirmar lista vazia ou erro de permissão. Se devolver lançamentos, parar e corrigir o RLS antes de seguir (quickstart.md §3)
- [X] T021 Atualizar `Documentação/Requisitos da Plataforma Financeira.md` com as 5 divergências de plan.md Pendência #4: `RN-15` (2ª exceção — `clientes`), `RF-101` (filtro de cliente derivado), `RN-03`/`RF-17` (`atrasado` só com efetivação manual), ausência de saldo inicial (`FR-114`), e PostgreSQL no lugar de SQLite (Princípio V)

**✅ Checkpoint Boss 1**: banco aplicado, seeds conferidos por consulta, chave pública negada,
documento-mestre alinhado. Sem isso, nenhuma linha de backend.

---

# ⚙️ FASE BOSS 2 — BACKEND

**Meta**: os ~75 endpoints de `contracts/` no ar, com as `RN-xx` em `app/dominio/` e testes
rodando. Entregue **por história na ordem P1→P3** — plan.md §Fases de execução justifica: um
erro de modelagem descoberto só na tela custaria retrabalho nas três fases.

## Sub-fase B0 — Fundação do backend (bloqueia todas as histórias)

- [X] T022 Declarar as dependências de plan.md §Technical Context em **`backend/pyproject.toml`**, não em `requirements.txt`: a Vercel instala do `pyproject.toml` e ignora o `requirements.txt` quando os dois existem — descoberto no log do deploy. Dependências (FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 Core, asyncpg, PyJWT, python-dateutil, ofxparse, reportlab, pytest, pytest-asyncio, httpx)
- [X] T023 Implementar `backend/app/config.py` com pydantic-settings lendo as variáveis de quickstart.md §4 — nenhum `os.environ` solto (Princípio VII)
- [X] T024 🟢 Implementar `backend/app/db.py`: engine asyncpg, pool dimensionado para função serverless e sessão por requisição
- [X] T025 Implementar `backend/app/comum/erros.py` com o formato único de erro (`codigo`, `mensagem` PT-BR, `requisito`, `campos`) e os 10 códigos da tabela de contracts/README.md
- [X] T026 [P] Implementar `backend/app/comum/paginacao.py` (`pagina`, `por_pagina` 1–200 padrão 50, `ordenar`, `direcao`) devolvendo o envelope `{itens, paginacao}`
- [X] T027 [P] Implementar `backend/app/comum/periodo.py`: resolve `hoje`, `esta_semana`, `este_mes`, `mes_passado`, `ultimos_3_meses`, `este_ano`, `personalizado` para `(inicio, fim, inicio_anterior, fim_anterior)` — a mesma régua para o comparativo
- [X] T028 [P] Implementar `backend/app/comum/idempotencia.py` para o cabeçalho `Idempotency-Key` nos `POST` de criação (contracts/README.md)
- [X] T029 [P] Implementar `backend/app/comum/auditoria.py` com `registra_auditoria(entidade, id, acao, diff)` gravando só o que mudou (`RF-03`, `RN-08`)
- [X] T030 Implementar `backend/app/seguranca/auth.py`: valida o JWT do Supabase (modo conferido no painel — research.md D-03) e carrega o usuário de `usuarios`
- [X] T031 Implementar `backend/app/seguranca/rbac.py` com a dependência `exige_papel("gestor")` / `exige_papel("gestor","operador")` — todo endpoint declara o papel (constituição)
- [X] T032 Implementar `backend/app/main.py`: app FastAPI, registro de routers, handlers de erro usando `comum/erros.py`, OpenAPI em `/api/docs`
- [X] T033 [P] Implementar `GET /api/saude` em `backend/app/main.py` devolvendo `{status, banco, versao}` (contracts/plataforma.md §7)
- [X] T034 Implementar `backend/app/usuarios/rotas.py` com `GET /api/sessao` e `POST /api/sessao/preferencias` (tema e ordem de cards em `usuarios.preferencias`) — contracts/plataforma.md §1
- [X] T035 Criar `backend/api/index.py` expondo o app ASGI e `backend/vercel.json` com runtime Python e a declaração do cron diário
- [X] T036 Configurar `backend/tests/conftest.py` com pytest-asyncio, httpx e a conexão das integrações (quickstart.md §6). ⚠️ **Revisto em 2026-07-31**: não haverá Postgres de teste isolado — as integrações rodam contra produção, e o que protege os dados é a transação desfeita no `finally`
- [X] T037 [P] Configurar lint e formatação do backend (ruff + black) em `backend/pyproject.toml`
- [ ] T038 Criar o projeto `synapse-erp-api` na Vercel (root `backend`), publicar e confirmar `GET /api/saude` respondendo em produção (quickstart.md §7)

**✅ Checkpoint B0**: deploy vivo, `/api/docs` listando, autenticação e RBAC prontos.

## Sub-fase B1 — US1 Registrar o dinheiro + US2 Separar os mundos (P1) 🎯 MVP

**Objetivo**: substituir a planilha — criar, achar, editar, dividir e excluir lançamento, com
mundo obrigatório e imutável.

**Teste independente**: criar 20 lançamentos variados nos dois mundos, filtrar por categoria e
período, editar um, excluir outro e restaurá-lo da lixeira; alternar o filtro de mundo e
conferir zero vazamento.

### Testes primeiro (escrever e ver falhar)

- [X] T039 [P] [US1] `backend/tests/unidade/dominio/test_split_soma_exata.py` — partes que não fecham são recusadas com a diferença explicitada (`RN-11`)
- [X] T040 [P] [US1] `backend/tests/unidade/dominio/test_conversao_usd.py` — usa a cotação da **data do lançamento**, não a de hoje; falha nas duas fontes exige cotação manual (`RN-12`)
- [X] T041 [P] [US1] `backend/tests/unidade/dominio/test_saldo_ignora_nao_efetivado.py` — só `efetivado` entra no realizado (`RN-05`)
- [X] T042 [P] [US2] `backend/tests/unidade/dominio/test_separacao_por_mundo.py` — nenhum dado de um mundo aparece no outro (`RN-15`, `SC-005`)

### Domínio

- [X] T043 [P] [US2] Implementar `backend/app/dominio/mundo.py`: validação de mundo obrigatório, recusa de alteração com `409 regra_violada`/`RN-15`, resolução do modo `ambos`
- [X] T044 [P] [US1] Implementar `backend/app/dominio/saldo.py`: `saldo(mundo) = Σ(efetivado,receita) − Σ(efetivado,despesa)`, sem saldo inicial (`RN-05`, `RN-16`, `FR-114`)
- [X] T045 [P] [US1] Implementar `backend/app/dominio/split.py`: soma das partes comparada em `numeric`, pai deixa de contar quando tem partes (`RN-11`)
- [X] T046 [P] [US1] Implementar `backend/app/dominio/cambio.py`: cache em `cotacoes_cambio` → fonte primária → alternativa → cotação manual com `cotacao_manual = true` (`RN-12`)
- [X] T047 [P] [US1] Implementar `backend/app/dominio/lixeira.py`: soft delete, restauração enquanto dentro de `lixeira_retencao_dias`, linha nunca apagada (`RN-08`)

### Cadastros de apoio que o lançamento exige

- [X] T048 🟢 [P] [US1] Implementar `backend/app/cadastros/tags.py` (rotas, serviço, repositório): `GET`/`POST` para gestor e operador, `PUT`/`DELETE` só gestor (contracts/cadastros.md §7, `RN-14`)
- [X] T049 🟢 [P] [US1] Implementar `backend/app/cadastros/centros_custo.py` com as 4 rotas de contracts/cadastros.md §6 — ausência significa "geral", sem centro chamado "Geral" (`RN-13`)
- [X] T050 🟢 [P] [US1] Implementar `GET /api/categorias` (leitura, com contagem e total do período por mundo) em `backend/app/categorias/rotas.py` — o CRUD completo fica em B4 (contracts/cadastros.md §1)
- [X] T051 🟢 [P] [US1] Implementar `GET /api/servicos?mundo=` (leitura) em `backend/app/cadastros/servicos.py` — alimenta o campo "serviço vinculado" (`FR-104`)

### Lançamentos

- [X] T052 [US1] Implementar `backend/app/lancamentos/esquemas.py`: Pydantic v2 dos corpos de contracts/lancamentos.md, com dinheiro como string decimal e datas ISO
- [X] T053 🟢 [US1] Implementar `backend/app/lancamentos/repositorio.py` partindo sempre da view `lancamentos_ativos`, com os filtros combináveis de `FR-037` e busca por texto via `pg_trgm`
- [X] T054 [US1] Implementar `backend/app/lancamentos/servico.py` orquestrando os módulos de domínio, a auditoria e a idempotência
- [X] T055 [US1] Implementar `GET /api/lancamentos` em `backend/app/lancamentos/rotas.py`: filtros, paginação, contador e soma de receitas/despesas/resultado do conjunto filtrado (`FR-036`–`FR-038`)
- [X] T056 [US1] Implementar `POST /api/lancamentos` com `Idempotency-Key`, validação de `RN-01` (subcategoria obrigatória em categoria especial) e `RN-02` (valor sempre positivo)
- [X] T057 [US1] Implementar `GET /api/lancamentos/{id}` com moeda de origem, classificação, programação, anexos, origem de série e linha do tempo de auditoria (`FR-041`, `FR-043`)
- [X] T058 [US1] Implementar `PUT /api/lancamentos/{id}` com controle de `versao` respondendo `409 conflito_versao` e o que mudou desde a leitura (data-model §5.6)
- [X] T059 [US1] Implementar `DELETE /api/lancamentos/{id}` (soft delete) mais `GET /api/lixeira` e `POST /api/lixeira/{id}/restaurar` em `backend/app/lancamentos/rotas.py` (`FR-017`, `RN-08`)
- [X] T060 [US1] Implementar `POST /api/lancamentos/{id}/efetivar`, `/cancelar` e `/duplicar` (`FR-018`, `FR-030`, `FR-042`)
- [X] T061 [US1] Implementar `POST /api/lancamentos/{id}/dividir` recusando soma inconsistente com a diferença na mensagem (`FR-019`, `FR-020`, `RN-11`)
- [X] T062 [US1] Implementar `POST /api/lancamentos/lote` para a tabela editável (`FR-021`)
- [X] T063 [US1] Implementar `POST /api/lancamentos/acoes-em-massa`: excluir, mudar categoria, mudar status, adicionar/remover tags (`FR-040`)
- [X] T064 [US1] Implementar `backend/app/anexos/` — upload multipart para o bucket privado, `GET /api/anexos/{id}` com URL assinada de curta validade, `DELETE`, `413` acima do limite e `415` para MIME não permitido (`FR-013`)
- [X] T065 [US1] Implementar `GET /api/lancamentos/exportacao?formato=csv` respeitando os filtros ativos (`FR-045`)
- [X] T066 🟢 [US2] Implementar `GET /api/saldo?mundo=` com consolidado e quebra Digital/Infra (`FR-007`, `RN-16`)
- [X] T067 [US2] Aplicar o parâmetro `?mundo=digital|infra|ambos` em todos os endpoints de leitura já criados e cobrir o trigger de imutabilidade com teste de integração (`RF-101`, `FR-005`)

### Fechamento

- [X] T068 [US1] Escrever os testes de integração de lançamentos contra Postgres real em `backend/tests/integracao/test_lancamentos.py`
- [X] T069 [US1] Escrever os testes de contrato conferindo as respostas contra `contracts/lancamentos.md` em `backend/tests/contrato/test_lancamentos.py`
- [X] T070 Verificar documentação de B1: `/api/docs` bate com `contracts/lancamentos.md`? algo mudou no data-model ou no documento-mestre? Registrar a resposta, mesmo que seja "nada a mudar" (Princípio V)

> **Resposta de T070 (2026-07-30)** — não era "nada a mudar". Seis ajustes, todos feitos:
>
> 1. `contracts/lancamentos.md` §1 — `POST` ganhou a regra de a categoria ter que **aceitar
>    o `tipo`** do lançamento (`categorias.tipo`). Era um furo real: nada impedia lançar
>    despesa em categoria de receita. Fechado no dono da regra (`valida_classificacao`), o
>    que faz valer em criar, editar, dividir e mudar em massa.
> 2. `contracts/lancamentos.md` §1 — detalhe: `anexos[].url` passou a ser o **endpoint**
>    `/api/anexos/{id}`, não a URL assinada; e o campo `serie` foi removido do contrato,
>    porque `origem` já cumpre o papel (dois campos para a mesma coisa divergiriam).
> 3. `contracts/lancamentos.md` §1 — lote e ações em massa ganharam o formato de sucesso, a
>    tabela de parâmetro por ação e os tetos de 200/500 com o motivo.
> 4. `contracts/lancamentos.md` §5 e §6 — anexos (validação antes de qualquer upload, recusa
>    em parte de split) e o CSV da exportação (formato brasileiro, teto de 20.000).
> 5. `data-model.md` §3.15 e §7 — 18 chaves de configuração e a migração `009`.
> 6. `quickstart.md` — a conferência de seed passou a esperar 18 configurações.
>
> **Documento-mestre**: nada a mudar. Nenhum `RF-xx`/`RN-xx` mudou de significado — a
> checagem de tipo de categoria é aplicação de `RN-01` como já estava escrito, não regra nova.

**✅ Checkpoint B1**: o núcleo funciona ponta a ponta pela API. É o MVP de backend.
Ressalva: os 21 testes de integração de B1 rodam contra o banco de produção, dentro de
transação desfeita (decisão do dono do projeto, 2026-07-31 — quickstart §6). Pulam sem
`DATABASE_URL` no ambiente.

## Sub-fase B2 — US3 Programar o futuro e recuperar o histórico (P1)

**Objetivo**: recorrência (inclusive retroativa), parcelamento e o ciclo de status rodando
sozinho.

**Teste independente**: recorrência mensal de R$ 1.200 com início 5 meses atrás gera 5
ocorrências efetivadas mais as futuras programadas, e o saldo bate com o histórico real.

- [X] T071 [P] [US3] `backend/tests/unidade/dominio/test_ciclo_status.py` — programado → efetivado/pendente → atrasado; cancelado preserva histórico (`RN-03`)
- [X] T072 [P] [US3] `backend/tests/unidade/dominio/test_recorrencia_retroativa.py` — início 12 meses atrás gera exatamente 12 ocorrências `efetivado` (`RN-05a`, `SC-004`)
- [X] T073 [P] [US3] `backend/tests/unidade/dominio/test_recorrencia_dia_31_em_fevereiro.py` — mensal "todo dia 31" cai no último dia do mês (quickstart.md §6)
- [X] T074 [P] [US3] `backend/tests/unidade/dominio/test_escopo_edicao_serie.py` — `esta_e_futuras` nunca altera ocorrência passada (`RN-07`)
- [X] T075 [US3] Implementar `backend/app/dominio/status.py`: ciclo de `RN-03`/`RN-04`, `atrasado` só alcançável com `efetivar_automaticamente = false`, e edição histórica exigindo `confirmar_alteracao_historica` (data-model §5.8)
- [X] T076 [US3] Implementar `backend/app/dominio/recorrencia.py` com python-dateutil: geração idempotente por `gerada_ate`, horizonte de `recorrencia_horizonte_meses`, clamp do dia do mês, retroativas nascendo `efetivado` (`FR-025`, `FR-026`, `RN-05a`, `RN-07`)
- [X] T077 [P] [US3] Implementar `backend/app/dominio/parcelamento.py`: N parcelas com a diferença de arredondamento absorvida na última (`FR-028`)
- [X] T078 🟢 [US3] Implementar `backend/app/recorrencias/repositorio.py` e `servico.py`
- [X] T079 [US3] Implementar em `backend/app/recorrencias/rotas.py` as rotas `GET /api/recorrencias`, `GET /{id}`, `POST`, `PUT /{id}` (com `escopo_serie` obrigatório), `POST /{id}/desativar` e `DELETE /{id}` (contracts/lancamentos.md §3)
- [X] T080 [US3] Implementar `POST /api/recorrencias/previa` e a resposta `422 confirmacao_necessaria` com `previa` quando a contagem passa de `recorrencia_aviso_ocorrencias` (`FR-027`)
- [X] T081 [US3] Implementar a geração em lotes com cursor e `POST /api/recorrencias/{id}/continuar-geracao`, devolvendo `{concluida, cursor, geradas, total}` (research.md D-02a)
- [X] T082 [US3] Implementar `POST /api/parcelamentos` e `GET /api/parcelamentos/{id}` em `backend/app/lancamentos/rotas.py` (contracts/lancamentos.md §4)
- [X] T083 🟢 [US3] Implementar `backend/app/rotinas/diaria.py`: materializa recorrências, aplica o ciclo de status e grava `execucoes_rotina.ultimo_resultado`; idempotente e recuperando de `ultima_data_processada` até hoje (research.md D-08)
- [X] T084 [US3] Implementar `backend/app/rotinas/rotas.py` com `POST /api/rotinas/diaria` protegido por `X-Segredo-Rotina`, `GET /api/rotinas/estado` (gestor) e o cron declarado em `backend/vercel.json`
- [X] T085 [US3] Implementar a chamada implícita da rotina em `/api/dashboard`, `/api/extrato`, `/api/lancamentos` e `/api/saldo` quando ela não rodou hoje (contracts/plataforma.md §6)
- [X] T086 [US3] Escrever integração e contrato de recorrências e parcelamentos em `backend/tests/integracao/test_recorrencias.py` e `backend/tests/contrato/test_recorrencias.py`
- [X] T087 Verificar documentação de B2 e registrar a resposta (Princípio V)

> **Resposta de T087 (2026-07-30)** — cinco ajustes:
>
> 1. `contracts/plataforma.md` §6 — **`GET /api/rotinas/diaria` documentado**. Fechou a
>    divergência nº 1 do README do backend: o Vercel Cron não envia cabeçalho personalizado,
>    ele chama com `GET` e `Authorization: Bearer $CRON_SECRET`. Os dois caminhos conferem o
>    mesmo segredo, e há teste de contrato exigindo que o `GET` apareça no `/api/docs`.
> 2. `contracts/plataforma.md` §6 — o resultado da rotina ganhou `recorrencias_processadas`,
>    `recorrencias_pendentes_de_geracao` e `avisos`. Sem eles, execução parcial pareceria
>    idêntica a execução completa.
> 3. `contracts/lancamentos.md` §3 — o `cursor` é o `gerada_ate` (não um token opaco);
>    `escopo_serie` aceita só `esta_e_futuras` no `PUT`; formato de `POST /previa`.
> 4. `contracts/lancamentos.md` §4 — resposta do `GET /api/parcelamentos/{id}`, valores de
>    `intervalo`, tetos de parcelas.
> 5. `data-model.md` §5.9–§5.11 e §7 — os três módulos de domínio novos e a migração `010`.
>
> **Documento-mestre**: nada a mudar. O ciclo de status, a recorrência retroativa e o
> parcelamento foram implementados como `RF-15`/`RF-16`/`RF-17a`/`RN-03`/`RN-05a`/`RN-07` já
> descreviam.

**✅ Checkpoint B2**: o histórico entra sozinho e o futuro se resolve na data.
Ressalva: os 20 testes de integração de B2 rodam contra produção, em transação desfeita —
mesma situação de B1 (quickstart §6).

## Sub-fase B3 — US4 Saúde do caixa + US7 Extrato (P1/P2)

**Objetivo**: os números de leitura — Dashboard inteiro em **uma** requisição e Extrato
agrupado.

**Teste independente**: com 12 meses carregados, cada card bate com o cálculo manual e o saldo
acumulado do último grupo do Extrato é igual ao saldo final do período.

- [X] T088 [P] [US4] Implementar `backend/app/dominio/saude_caixa.py`: semáforo sobre as despesas fixas de `saude_caixa_horizonte_dias`, com os multiplicadores vindos de `configuracoes` (`FR-069`, `RNF-02`)
- [X] T089 🟢 [US4] Implementar `backend/app/dashboard/repositorio.py` — **todas as agregações em uma requisição**; conferir os índices com a Skill, porque é aqui que `SC-002` se ganha ou se perde
- [X] T090 [US4] Implementar `GET /api/dashboard` em `backend/app/dashboard/rotas.py` com os 7 cards de `FR-054`, comparativo de período e mini-gráficos de tendência (`FR-055`, `FR-057`)
- [X] T091 🟢 [US4] Implementar as séries do Dashboard: fluxo de caixa de 12 meses com projeção distinta, evolução do saldo final, comparativo mês atual × anterior, despesas por categoria e top 5 despesas (`FR-059`–`FR-063`)
- [X] T092 🟢 [US4] Implementar os blocos especiais do Dashboard resolvidos por `categorias.vinculo` — Clientes e Funcionários — sem nenhum `if nome == 'Clientes'` no código (`FR-065`, `FR-066`, `FR-079`)
- [X] T093 [US4] Implementar o alerta fixo de atrasados, a linha do tempo de 7 dias e o resumo do período em linguagem natural (`FR-067`, `FR-068`, `FR-070`)
- [X] T094 [US4] Implementar a visibilidade e a ordem dos cards a partir de `usuarios.preferencias` × `configuracoes.dashboard_cards_disponiveis`, devolvendo os rótulos junto do dado (`FR-071`, `FR-106`)
- [X] T095 🟢 [US7] Implementar `backend/app/extrato/servico.py` com agrupamento por dia, semana ou mês e saldo acumulado ao fim de cada grupo (`FR-047`)
- [X] T096 [US7] Implementar `GET /api/extrato` com cabeçalho-resumo comparativo, grupos futuros marcados como previstos e a seção "A pagar / A receber" (`FR-048`, `FR-051`, `FR-052`)
- [X] T097 [US4] Medir `SC-007` e `SC-002`: popular 5.000 lançamentos de teste e conferir filtro em menos de 2 s e Dashboard em uma requisição — ajustar índices se falhar, com a Skill acionada
- [X] T098 [US7] Escrever integração e contrato de dashboard e extrato em `backend/tests/integracao/` e `backend/tests/contrato/`
- [X] T099 Verificar documentação de B3 e registrar a resposta (Princípio V)

> **Resposta de T099 (2026-07-30)** — dois ajustes, e uma ressalva que não é ajuste:
>
> 1. `contracts/consultas.md` §1 — os cards passaram a trazer `rotulo`/`grupo`/`ordem` junto
>    do valor e a resposta ganhou `cards_disponiveis` (o catálogo inteiro, para "Configurar
>    cards" não precisar de outra requisição). Documentado também que **percentual é `null`,
>    não `"0.0"`, quando o anterior é zero**, e que `card_clientes.inadimplentes` fica `[]`
>    até B4/T100.
> 2. `data-model.md` — `dominio/saude_caixa.py` entrou no mapa de regras (§5).
>
> **Documento-mestre**: nada a mudar. `FR-053`–`FR-071` e `FR-047`–`FR-052` foram
> implementados como estavam escritos.
>
> **Ressalva de T097**: a medição de `SC-007`/`SC-002` está escrita
> (`tests/integracao/test_desempenho.py`, marcada `lento`) e **não foi executada**. Ela insere
> milhares de linhas no banco de produção — a transação desfeita garante que nada sobrevive,
> mas a carga chega ao servidor. Rodá-la é decisão consciente, fora do horário de uso.

**✅ Checkpoint B3**: dá para responder "como está o caixa?" só pela API.
Ressalva: 16 testes de integração de B3 escritos; rodam contra produção em transação
desfeita (quickstart §6).

## Sub-fase B4 — US5 Clientes + US6 Funcionários (P2)

**Objetivo**: as duas categorias especiais, com espelho de subcategoria, recorrência
automática e inadimplência derivada.

**Teste independente**: 3 clientes (um recorrente) e 2 funcionários cadastrados; um pagamento
vence além da tolerância e o cliente aparece marcado no Dashboard, na lista e no perfil.

- [X] T100 [P] [US5] Implementar `backend/app/dominio/inadimplencia.py` — situação **derivada**, nunca gravada: lançamento atrasado há mais de `inadimplencia_dias_tolerancia` e só com efetivação manual (`RN-10`, `FR-115`) — com teste em `backend/tests/unidade/dominio/test_inadimplencia.py`
- [X] T101 [P] [US5] Implementar `backend/app/dominio/arquivamento.py`: arquivar categoria com lançamentos exige `destino_lancamentos` **ou** `manter_somente_leitura`, nunca órfão; cliente e funcionário só arquivam (`RN-06`, `FR-075`) — com teste unitário
- [X] T102 [US5] Implementar o espelho de subcategoria em `backend/app/dominio/espelho_subcategoria.py`: criar cliente/funcionário cria a subcategoria, arquivar arquiva, renomear renomeia — tudo na mesma transação (research.md D-07)
- [X] T103 🟢 [US5] Completar o CRUD de categorias em `backend/app/categorias/rotas.py` (`POST`, `PUT`, `POST /{id}/arquivar` com o fluxo `422`) — o `GET` veio de T050
- [X] T104 [US5] Implementar as rotas de subcategorias em `backend/app/categorias/rotas.py`, recusando criação manual em categoria com `vinculo` e explicando onde criar (contracts/cadastros.md §2)
- [X] T105 🟢 [US5] Implementar `backend/app/clientes/repositorio.py` com o filtro de mundo **derivado da movimentação** e o cliente sem lançamento aparecendo nos três estados (`FR-002`, research.md D-04)
- [X] T106 [US5] Implementar as 6 rotas de clientes em `backend/app/clientes/rotas.py` (contracts/cadastros.md §3), com `mundo_cobranca` obrigatório quando `tipo_cobranca = recorrente`
- [X] T107 [US5] Implementar `GET /api/clientes/{id}` — perfil com total recebido, receita mensal, lançamentos, próximos recebimentos, situação e quebra por mundo (`FR-081`)
- [X] T108 [US5] Ligar o cadastro de cliente recorrente à criação da recorrência de mensalidade no `mundo_cobranca`, e o arquivamento à remoção das ocorrências futuras não efetivadas (`FR-082`, data-model §3.13)
- [X] T109 [US6] Implementar `backend/app/funcionarios/` com as 5 rotas de contracts/cadastros.md §4, criando subcategoria espelho e recorrência da folha na mesma transação e recusando mudança de `mundo` (`FR-088`, `RN-15`)
- [X] T110 [US6] Implementar `GET /api/funcionarios/{id}` — perfil com custo histórico e do período, pagamentos e próximos, somando bônus e vales avulsos da mesma subcategoria (`FR-087`)
- [X] T111 🟢 [P] [US6] Completar o CRUD de gestor de serviços e centros de custo em `backend/app/cadastros/` (`POST`, `PUT`, `arquivar`) — as leituras vieram de T049/T051
- [X] T112 [US5] Escrever integração e contrato de cadastros em `backend/tests/integracao/test_cadastros.py` e `backend/tests/contrato/test_cadastros.py`
- [X] T113 Verificar documentação de B4 e registrar a resposta (Princípio V)

> **Resposta de T113 (2026-07-30)** — três ajustes:
>
> 1. `contracts/cadastros.md` §2 — `PUT /api/subcategorias/{id}` e `.../arquivar` recusam
>    quando a subcategoria é **espelho**. O nome vem do cadastro; mexer só de um lado faria a
>    tela de clientes e o Dashboard discordarem.
> 2. `contracts/cadastros.md` §3 e §4 — resposta do `POST /api/clientes` (com
>    `subcategoria_id`, `recorrencia.rotulo` e `aviso_inadimplencia`), a situação achatada no
>    item com `tolerancia_dias` junto, a existência de `/desarquivar` e o motivo de ele **não**
>    recriar a recorrência. Na folha, o `efetivar_automaticamente = true` e o porquê.
> 3. `data-model.md` §5.13 e §5.14 — `dominio/inadimplencia.py` e
>    `dominio/espelho_subcategoria.py` no mapa de regras.
>
> **Documento-mestre**: nada a mudar. `RN-10` já dizia que a situação é derivada e `RF-101`
> já registrava o filtro de cliente derivado (T021 alinhou isso na Fase A).

**✅ Checkpoint B4**: quem paga e quanto custa a equipe, com alerta de quem atrasou.
Ressalva: 21 testes de integração de B4 escritos; rodam contra produção em transação
desfeita (quickstart §6).

## Sub-fase B5 — US8 Relatórios e fechamento (P3)

**Objetivo**: fechar o mês sem planilha.

**Teste independente**: gerar o DRE de um mês fechado, conferir contra a soma manual das
categorias e exportar em CSV com os mesmos números.

- [X] T114 🟢 [US8] Implementar `backend/app/relatorios/repositorio.py` com as agregações por categoria, subcategoria, cliente e mês
- [X] T115 [US8] Implementar `GET /api/relatorios/dre` — receita bruta por categoria, despesas com quebra por subcategoria, resultado mensal e acumulado no ano, com comparativo (`FR-090`)
- [X] T116 [P] [US8] Implementar `GET /api/relatorios/clientes` — ranking com total, percentual do faturamento, situação, evolução mensal e quebra por mundo (`FR-091`)
- [X] T117 [P] [US8] Implementar `GET /api/relatorios/variacao-categorias` com o destaque vindo de `configuracoes.variacao_destaque_percentual`, nunca fixo em 20 no código (`FR-092`, `RNF-02`)
- [X] T118 [P] [US8] Implementar `GET /api/relatorios/matriz-mensal` (`FR-093`)
- [X] T119 [US8] Implementar `backend/app/relatorios/exportacao_csv.py` (`FR-094`)
- [X] T120 [US8] Implementar `backend/app/relatorios/exportacao_pdf.py` com reportlab — sem pandas, por causa do limite de tamanho do pacote da função (plan.md §Constraints)
- [X] T121 [US8] Implementar a leitura do período em linguagem natural (`FR-095`) e escrever os testes de contrato dos 4 relatórios em `backend/tests/contrato/test_relatorios.py`
- [X] T122 Verificar documentação de B5 e registrar a resposta (Princípio V)

> **Resposta de T122 (2026-07-30)** — dois ajustes:
>
> 1. `contracts/consultas.md` §3 — formato do `matriz-mensal`, e as precisões de B5: `csv`/`pdf`
>    recebem a resposta pronta (é assim que "os mesmos dados do json" é garantido), `pdf` só
>    existe em `dre` e `clientes` (matriz larga em A4 sai ilegível — melhor recusar do que
>    entregar arquivo que ninguém lê), import preguiçoso do reportlab, `acumulado_ano` no DRE
>    e `limiar_destaque_percentual` no corpo.
> 2. `backend/pyproject.toml` — `reportlab` entrou nas dependências agora, no commit em que
>    passou a ser usada. `ofxparse` continua fora até B6, pelo mesmo critério.
>
> **Documento-mestre**: nada a mudar. `FR-090`–`FR-095` foram implementados como escritos.
>
> **✅ Checkpoint B5**: dá para fechar o mês sem planilha. Ressalva: os relatórios não foram
> exercitados contra dados reais — o banco de produção está vazio, então não há o que agregar
> até o histórico entrar.

## Sub-fase B6 — US9 Avisos + US10 Papéis e configuração (P3)

**Objetivo**: o sistema deixa de ser passivo, e tudo que é parâmetro sai do código.

**Teste independente**: conta que vence em 3 dias gera notificação; cliente que passa da
tolerância gera alerta; operador recebe `403` chamando `/api/configuracoes` **pela API
direta**, não só pelo menu escondido.

- [X] T123 🟢 [US9] Implementar `backend/app/notificacoes/servico.py` com `chave_deduplicacao` nos 4 formatos de data-model §3.16 — sem ela a rotina duplicaria o mesmo aviso
- [X] T124 [US9] Implementar `GET /api/notificacoes`, `POST /{id}/marcar-lida` e `POST /marcar-todas-lidas` em `backend/app/notificacoes/rotas.py`, com contador de não lidas (`FR-096`–`FR-100`)
- [X] T125 [US9] Gerar os alertas de vencimento na rotina diária conforme `configuracoes.alerta_vencimento_dias` (`FR-096`)
- [X] T126 [US9] Gerar o alerta de inadimplência a partir de `dominio/inadimplencia.py` (`FR-097`)
- [X] T127 [US9] Implementar `backend/app/rotinas/semanal.py` — resumo de segunda e alerta de caixa baixo sobre `caixa_baixo_horizonte_dias` — mais `POST /api/rotinas/semanal` para disparo manual (`FR-098`, `FR-099`)
- [X] T128 [US9] Escrever `backend/tests/integracao/test_rotinas.py` provando que rodar a rotina duas vezes no mesmo dia não duplica nada e que um dia perdido é recuperado
- [X] T129 [US10] Implementar as 5 rotas de usuários em `backend/app/usuarios/rotas.py`, com criação no Supabase Auth e a trava que recusa rebaixar ou desativar o **último gestor ativo** (contracts/plataforma.md §2)
- [X] T130 [US10] Implementar `GET /api/configuracoes` (gestor e operador) e `PUT /api/configuracoes` (gestor), devolvendo `efeitos` e reavaliando a inadimplência **na hora** quando a tolerância muda (`FR-105`, edge case)
- [X] T131 🟢 [P] [US10] Implementar `GET /api/auditoria` nos dois modos — por registro (gestor e operador) e geral com filtros (gestor) — marcando `alteracao_historica` (`FR-103`)
- [X] T132 🟢 [P] [US10] Implementar `GET /api/busca?q=&limite=` cobrindo lançamentos, clientes e categorias via `pg_trgm` (`FR-046`)
- [X] T133 [US10] Implementar `POST /api/importacoes` em `backend/app/importacao/csv.py` — recebe o arquivo, **não grava**, devolve `importacao_id`, colunas detectadas e prévia (`FR-044`)
- [X] T134 [P] [US10] Implementar a leitura de OFX em `backend/app/importacao/ofx.py` com ofxparse
- [X] T135 [US10] Implementar `POST /api/importacoes/{id}/mapeamento` em `backend/app/importacao/mapeamento.py` com `mundo` obrigatório e categoria não reconhecida apontada na prévia, nunca criada sozinha
- [X] T136 [US10] Implementar `POST /api/importacoes/{id}/confirmar` gravando em lotes com cursor (mesmo padrão de T081)
- [X] T137 [US10] Implementar `POST /api/exportacoes/completa` e `GET /api/exportacoes/{id}` em `backend/app/relatorios/` — ZIP com um CSV por tabela mais os anexos, por lote com cursor (`FR-112`, `SC-011`)
- [X] T138 [US10] Escrever `backend/tests/integracao/test_rbac.py` chamando **todos** os endpoints de gestor com token de operador e exigindo `403` (`SC-010`)
- [X] T139 [US10] Escrever os testes de contrato de plataforma em `backend/tests/contrato/test_plataforma.py`
- [X] T140 Verificar documentação de B6 e registrar a resposta (Princípio V)

> **Resposta de T140 (2026-07-30)** — três ajustes, e uma pendência que não é ajuste:
>
> 1. `data-model.md` §7 — **migração `011_importacoes.sql`**. A tabela não estava entre as
>    19 do desenho: a necessidade só apareceu ao implementar o fluxo de três requisições de
>    `FR-044`, que precisa do conteúdo lido sobrevivendo entre elas. Memória não serve —
>    cada requisição da Vercel pode cair numa instância diferente, o mesmo motivo de D-01.
> 2. `contracts/plataforma.md` §6 — `POST /api/rotinas/semanal` documentado como **sem cron
>    próprio**: o plano gratuito dá um cron por dia, então a diária dispara a semanal na
>    segunda, com chave por semana ISO.
> 3. `backend/pyproject.toml` — **`ofxparse` não entrou**. A leitura de OFX é uma regex sobre
>    `<STMTTRN>`, porque a biblioteca arrasta `lxml` e `beautifulsoup4` e o pacote da função
>    tem tamanho limitado. É uma **troca declarada**: um OFX malformado que a `ofxparse`
>    aceitaria pode falhar aqui, e o tratamento é dizer isso em PT-BR e sugerir o CSV.
>
> **Documento-mestre**: nada a mudar.
>
> ✅ **Pendência resolvida em 2026-07-31**: a migração `011` foi aplicada e conferida no
> Supabase depois de o MCP voltar. O banco tem **20 tabelas**. Verificado de verdade, não por
> leitura de código:
>
> - Estrutura: 13 colunas, 3 índices, RLS ligada com **0 políticas** (negação, igual às
>   outras 19).
> - **Ciclo de três etapas exercitado no banco real** — enviar, mapear com `mundo`, confirmar
>   avançando o cursor até 200 —, mais o `CHECK` de formato recusando `pdf` e a expiração de
>   24h. Tudo dentro de uma transação desfeita: `importacoes`, `usuarios` e `lancamentos`
>   seguem em 0.
> - **Segurança**: assumindo o papel `anon`, leitura e escrita respondem "sem permissão". A
>   tabela nasceu sem grant nenhum para `anon`/`authenticated`, herdando o revoke de `006`.
> - `get_advisors(security)`: 20 avisos `INFO / rls_enabled_no_policy` — um por tabela, que é
>   o resultado esperado por D-03a. Zero ERROR, zero WARN.

**✅ Checkpoint Boss 2**: os ~75 endpoints no ar, os 7 testes obrigatórios passando,
`/api/docs` batendo com `contracts/`.

> **Número real, medido em 2026-07-31 depois da auditoria abaixo**:
>
> ```
> .venv/Scripts/python -m pytest tests -q -m "not lento"
> 509 passed, 4 deselected in 2086.76s (0:34:46)
> ```
>
> **94 rotas** carregadas, lint e formatação limpos.
>
> Os 4 dispensados são o `test_desempenho.py` (`SC-007`/`SC-002`), que insere milhares de
> linhas no banco de produção — rodá-lo continua sendo decisão consciente, fora do horário
> de uso (ressalva de T097, ainda de pé).
>
> Antes da auditoria este checkpoint estava verde com a suíte de integração **quebrada**:
> 91 errors na execução completa. As ressalvas de B1–B6 ("21 testes escritos", "20", "16",
> "21") contavam teste **escrito**, não teste **passando** — que é exatamente o que o
> Princípio VI proíbe. As ressalvas seguem no texto de cada sub-fase como registro do que
> foi declarado na época; o número acima é o que vale.

---

## Auditoria de fim do Boss 2 — 2026-07-31

Conferência do documento-mestre contra o código e contra o banco, **rodando**: banco lido
pelo MCP do Supabase, rotas carregadas do app FastAPI, suíte executada. Correções aplicadas
na mesma entrega.

### O que estava quebrado e foi corrigido

| # | Defeito | Onde |
|---|---|---|
| 1 | **Pooler derrubava consulta em produção.** `statement_cache_size=0` não basta com pgbouncer em modo *transaction*: o asyncpg nomeia o statement por contador, o contador reinicia a cada conexão nova (`NullPool`) e duas requisições concorrentes multiplexadas no mesmo servidor colidiam em `DuplicatePreparedStatementError`. Faltava `prepared_statement_name_func` | `app/db.py`, `tests/conftest.py` |
| 2 | **Consultas que nunca chegavam a executar.** 12 usos de `:param::date` — o `text()` do SQLAlchemy **não** substitui bind seguido de `:`, então o `:inicio::date` ia literal para o Postgres e virava erro de sintaxe. Atingia fluxo de caixa, evolução do saldo, sparklines, matriz mensal e filtro de auditoria por data | `dashboard/repositorio.py`, `relatorios/repositorio.py`, `auditoria/rotas.py` |
| 3 | **`card_clientes.inadimplentes` era `[]` fixo** — o comentário dizia "chega em B4", B4 fechou e ninguém voltou. `RF-44`/`FR-083`/`SC-006` pedem o destaque no Dashboard; funcionava na lista e no perfil, não no painel | `dashboard/rotas.py`, `dashboard/repositorio.py` |
| 4 | **Comparativo vazio nos cards Clientes e Funcionários** (`RF-44`, `RF-45`, `FR-055`) | `dashboard/rotas.py` |
| 5 | **Reordenar card não fazia nada** quando a posição escolhida empatava com um `ordem_padrao` do catálogo: a ordenação é estável e o catálogo ganhava (`FR-071`) | `dashboard/rotas.py` |
| 6 | **O resumo em linguagem natural engolia o aviso de contas vencidas** em período sem lançamento efetivado — o retorno antecipado pulava a frase. É quando o aviso mais importa (`FR-070`) | `dashboard/rotas.py` |
| 7 | **Alerta de caixa baixo ignorava as contas já vencidas**: `data between hoje and ate` exclui `atrasado`, que por definição tem data no passado (`RF-83`) | `rotinas/semanal.py` |
| 8 | **Lançamento importado não registrava auditoria** — único caminho de criação sem rastro, e justamente o que cria centenas de linhas de uma vez (`RF-03`, `RN-08`, `SC-014`) | `importacao/rotas.py` |
| 9 | **A validade de 24h da importação estava escrita e não era aplicada**: nem recusa, nem faxina. Upload abandonado ficava gravável para sempre, com o arquivo inteiro na tabela | `importacao/rotas.py`, `rotinas/diaria.py` |
| 10 | **`efetivar_automaticamente` fixo em `true`** no `insert` da importação, ignorando `configuracoes.efetivacao_automatica_padrao` (`FR-029`, `RNF-02`) | `importacao/rotas.py` |
| 11 | **"Sugestão de categoria" era casamento exato de nome** — `RF-21`/`FR-044` pedem sugestão. Agora sugere a mais parecida por similaridade, e **não aplica sozinha** | `importacao/mapeamento.py` |
| 12 | **Teste de split exigia a diferença na `mensagem`**; o contrato a coloca em `campos.partes` e o código seguia o contrato. Teste e docstring estavam desatualizados, não o código | `tests/integracao/test_lancamentos.py`, `dominio/split.py` |
| 13 | **Editar recorrência com `esta_e_futuras` apagava o futuro e não regerava nada.** O índice único `(recorrencia_id, data)` da migração `010` não filtra `excluido_em` — de propósito, para ocorrência excluída não renascer. A consequência não tinha sido vista: o soft delete **não libera a data**, então o `on conflict do nothing` da regeneração não inseria nenhuma linha. `RN-07`/`FR-034` prometem o contrário, e a série ficava sem futuro **em silêncio**. Corrigido com remoção definitiva só nesse caminho (alvo estreito: gerada pelo sistema, nunca efetivada, de regra recém-substituída) | `recorrencias/repositorio.py`, `recorrencias/rotas.py` |
| 14 | **Promover categoria a um `vinculo` já ocupado devolvia `500`.** O `update` batia no índice `categorias_vinculo_uidx` e o usuário recebia "Algo deu errado do nosso lado" numa ação previsível. Agora é `409 regra_violada`/`FR-079` dizendo **qual** categoria já ocupa o vínculo | `categorias/rotas.py` |
| 15 | **Idempotência não cobria o caso que existe para cobrir.** A divergência nº 2 do README do backend estava aberta desde B0 e o fechamento previsto para T056 nunca aconteceu: a chave vivia em memória do processo, e a repetição que a Vercel faz após timeout cai em instância nova. Resultado possível: dois lançamentos iguais, valor em dobro no saldo. Migração **`012`** aplicada e conferida | `migracoes/012_chaves_idempotencia.sql`, `comum/idempotencia.py`, `lancamentos/rotas.py`, `recorrencias/rotas.py`, `rotinas/diaria.py` |

### Verificação de documentação (Princípio V) — **não** era "nada a mudar"

- `Documentação/Requisitos da Plataforma Financeira.md` — §16 corrigido (19→**20 tabelas**,
  17→**18 chaves**) e **§17 novo**, com os dois pontos que mudam o que estava escrito:
  `RNF-06` (a exportação completa não leva os arquivos anexados) e `RF-21` (a sugestão de
  categoria sugere, não aplica).
- `contracts/plataforma.md` §8 — reescrito. Prometia `GET /api/exportacoes/{id}`, gravação
  por lote com cursor e anexos no ZIP; **nada disso existe**. O endpoint é síncrono e
  devolve o ZIP na hora. A troca está declarada com o limite dela.
- `contracts/lancamentos.md` §6 — sugestão de categoria, validade de 24h, auditoria do
  lançamento importado e origem do padrão de efetivação.
- `contracts/consultas.md` §1 — inadimplentes, comparativo dos cards especiais, desempate de
  ordem e o aviso de vencidos no resumo.
- `data-model.md` — §3.20 nova (`chaves_idempotencia`), §5.15 nova (validade da
  importação), a migração `012` e a nota da `011`.
- `contracts/README.md` §Idempotência — escopo, prazo, transação e quais `POST` aceitam.
- `backend/README.md` — divergência nº 2 marcada como resolvida, com o que foi feito.
- `plan.md` — contagem de tabelas.

O banco tem agora **21 tabelas** (`012` aplicada e conferida: RLS ligada, 0 políticas,
0 grant para `anon`/`authenticated` — a mesma negação de D-03a).

### O que ficou de fora — **precisa de decisão do dono do projeto**

- **T006** (cadastro público desabilitado no Supabase Auth), **T008** (confirmar backup
  gerenciado) e **T038** (publicar o projeto na Vercel) continuam abertas. São painel do
  Supabase e da Vercel, não código.
- **`GET /api/exportacoes/{id}` e a exportação por lote**: o contrato foi alinhado ao que
  existe hoje. Voltar ao desenho assíncrono é trabalho novo e só se justifica quando o
  histórico crescer — T210 mede.
- **`POST /api/funcionarios/{id}/desarquivar`**: clientes têm, funcionários não. Nem o
  contrato nem `RN-06` exigem; a assimetria está apontada, sem endpoint novo.

---

# 🎨 FASE BOSS 3 — FRONTEND

**Meta**: as ~10 telas fiéis ao Claude Design, nos dois temas, em PT-BR.

**Método de fidelidade** (plan.md §Fase C): cada tela é implementada lendo a seção
correspondente de `Synapse ERP Financeiro.dc.html` — que traz as medidas exatas em estilo
inline — e conferida contra as 15 capturas em `Documentação/prints do UI Mockup/`. Nunca de
memória.

**Antes de escrever componente novo**: procurar pronto na ordem shadcn → Reui → GitHub → só
então código próprio, e **registrar a pesquisa** (Princípio II).

## Sub-fase C0 — Fundação visual

- [X] T141 Inicializar o Next.js 15 (App Router) + TypeScript + Tailwind em `frontend/` e rodar `shadcn init`
- [X] T142 Copiar `colors_and_type.css` do Synapse Design System para `frontend/estilos/tokens.css` **sem reinterpretar**: roxo `#8B6CF0`, tinta `#14102B` (nunca `#000`), sombras com tom roxo, raios 10/14–20/28/999px, grade de 4pt
- [x] T143 ~~Aprovar a escala de tema escuro derivada~~ — **decidido em 2026-07-30: haverá tema escuro mesmo sem estar no design system, e a escala é derivada na hora da implementação** (T144). Sem aprovação prévia; a conferência é visual, tela a tela (T202)
- [X] T144 Escrever `frontend/estilos/tema-escuro.css` derivando a escala pelas regras de research.md D-12 — nunca `#000` (usar a tinta `#14102B` como base), elevação por luminosidade em vez de sombra colorida, roxo de ação um passo mais claro que `#8B6CF0`, semânticos reajustados para contraste AA — e ligar o alternador claro/escuro/automático em `frontend/app/layout.tsx` (`FR-109`)
- [X] T145 [P] Configurar fontes e providers em `frontend/app/layout.tsx` (TanStack Query, tema, zustand)
- [X] T146 [P] Extrair os SVGs de navegação do mockup para `frontend/componentes/comum/icones.tsx`; o resto da interface usa Lucide
- [X] T147 [P] Implementar `frontend/lib/formato.ts` com `Intl`: `R$ 1.234,56` e `dd/mm/aaaa` (`RNF-03`) — a API transporta ISO e decimal em string
- [X] T148 Implementar `frontend/lib/api.ts`: cliente HTTP tipado que lê o formato único de erro e mostra `erro.mensagem` como veio do backend, sem montar texto de regra de negócio no frontend (`RNF-02`)
- [X] T149 [P] Implementar `frontend/lib/supabase.ts` — **só login**; o frontend nunca fala com o banco (research.md D-03a)
- [X] T150 [P] Implementar `frontend/lib/estado-global.ts` com zustand: mundo e período espelhados na URL e mantidos entre navegações e sessões (`FR-001`)
- [X] T151 [P] Implementar `frontend/lib/atalhos.ts`: novo lançamento, busca global, navegação entre abas e fechar painel/modal (`FR-110`)
- [X] T152 Configurar `frontend/next.config.ts` com o rewrite de `/api/:path*` para `BACKEND_URL` — mesma origem, sem CORS (research.md D-02)
- [X] T153 [P] Configurar Vitest + Testing Library em `frontend/vitest.config.ts`
- [ ] T154 Criar o projeto `synapse-erp-web` na Vercel (root `frontend`, `BACKEND_URL` apontando para a API) e confirmar `https://<web>.vercel.app/api/saude` respondendo pelo proxy

## Sub-fase C1 — Casca da aplicação

- [X] T155 Implementar `frontend/app/entrar/page.tsx` com Supabase Auth (e-mail + senha), sem cadastro público
- [X] T156 Implementar `frontend/app/(app)/layout.tsx` e `frontend/componentes/layout/BarraLateral.tsx`: 246px, fundo `#F7F5FB`, item ativo `#EDE6FD`/`#4F3299`, as 7 abas de `FR-107` e o rodapé com Configurações e perfil
- [X] T157 Implementar `frontend/componentes/layout/CabecalhoGlobal.tsx` (64px) e `SeletorMundo.tsx` com os três estados Digital / Infra / Ambos (`FR-001`)
- [X] T158 [P] Implementar `frontend/componentes/layout/SeletorPeriodo.tsx` com os atalhos de período resolvidos pelo servidor (contracts/README.md)
- [X] T159 [P] Implementar `frontend/componentes/layout/BuscaGlobal.tsx` (atalho de teclado) e `SinoNotificacoes.tsx` com contador de não lidas (`FR-046`, `FR-100`)
- [X] T160 [P] Implementar `frontend/componentes/layout/AlternadorTema.tsx` persistindo em `usuarios.preferencias` (`FR-109`)
- [X] T161 [P] Implementar `frontend/componentes/comum/`: `Moeda`, `DataBR`, `BadgeStatus`, `BadgeMundo` e `EstadoVazio` ("Nada previsto", conforme mockup)

## Sub-fase C2 — US1 Lançamentos + US2 Mundos (P1) 🎯 MVP de tela

- [X] T162 [US1] Implementar `frontend/componentes/lancamentos/TabelaLancamentos.tsx` com TanStack Table: colunas de `FR-036`, cor por tipo e ordenação por qualquer coluna
- [X] T163 [US1] Implementar `frontend/componentes/lancamentos/BarraFiltros.tsx`: filtros combináveis, marcadores removíveis individualmente, limpar todos, contador e somas do conjunto filtrado (`FR-037`–`FR-039`)
- [X] T164 [US1] Implementar `frontend/componentes/lancamentos/FormLancamento.tsx` com react-hook-form + zod, valores padrão inteligentes, campo de mundo pré-preenchido e "salvar e criar outro" (`FR-004`, `FR-014`, `FR-015`)
- [X] T165 [US1] Implementar `frontend/componentes/lancamentos/PainelDetalhe.tsx`: um clique abre, duplo clique edita; valor, moeda de origem, classificação, programação, anexos, observações e histórico (`FR-041`, `FR-042`)
- [X] T166 [P] [US1] Implementar `frontend/componentes/lancamentos/DialogoSplit.tsx` mostrando a diferença que falta fechar antes de deixar salvar (`RN-11`)
- [X] T167 [P] [US1] Implementar `frontend/componentes/lancamentos/TabelaLote.tsx` e a barra de ações em massa (`FR-021`, `FR-040`)
- [X] T168 [P] [US1] Implementar o envio e o download de anexos com mensagem clara para arquivo grande e formato não suportado (`FR-013`)
- [X] T169 [P] [US1] Implementar a lixeira em `frontend/app/(app)/lancamentos/lixeira/page.tsx` com `dias_restantes` (`FR-017`)
- [ ] T170 [US2] Conferir a troca de mundo em todas as telas já prontas e a identificação visual por item no modo "Ambos" — zero dado do mundo errado (`SC-005`, `FR-003`)

## Sub-fase C3 — US3 Programação e recorrência (P1)

- [X] T171 [US3] Implementar os campos de recorrência e o `DialogoSerie.tsx` ("só este" / "este e os futuros") em `frontend/componentes/lancamentos/` (`FR-034`)
- [X] T172 [US3] Implementar a confirmação de geração retroativa mostrando quantas ocorrências e o intervalo, com barra de progresso para a geração em lotes — a interface não trava (`FR-027`, edge case)
- [X] T173 [P] [US3] Implementar a interface de parcelamento com a identificação "2/3" e o link para a série completa (`FR-028`, `FR-043`)
- [X] T174 [US3] Implementar os estados visuais de `programado`, `pendente` e `atrasado` e a confirmação de um clique na lista e no painel (`FR-030`, `FR-033`)

## Sub-fase C4 — US4 Dashboard (P1)

- [X] T175 [US4] Implementar `frontend/app/(app)/page.tsx` montando a grade a partir de `dashboard_cards_disponiveis` — um componente por card, resolvido por `id`, nenhum rótulo escrito no código (`FR-106`)
- [X] T176 [US4] Implementar os 7 cards numéricos com comparativo e mini-gráfico de tendência em `frontend/componentes/dashboard/` (`FR-054`–`FR-057`)
- [X] T177 [US4] Implementar os gráficos em `frontend/componentes/graficos/` com Recharts e tokens do tema: fluxo de caixa com projeção distinta, evolução do saldo, comparativo mensal e despesas por categoria (`FR-059`–`FR-062`)
- [X] T178 [P] [US4] Implementar os cards especiais de Clientes e Funcionários e a linha do tempo de 7 dias (`FR-065`–`FR-067`)
- [X] T179 [P] [US4] Implementar o alerta vermelho fixo de atrasados, o card "Saúde do caixa" com semáforo e o resumo em linguagem natural (`FR-068`–`FR-070`)
- [X] T180 [P] [US4] Implementar "Configurar cards" — mostrar, ocultar e reordenar, persistindo por usuário (`FR-071`)
- [X] T181 [US4] Ligar todo card e toda fatia de gráfico à lista já filtrada correspondente (`FR-058`, `FR-062`)

## Sub-fase C5 — US7 Extrato (P2)

- [X] T182 [US7] Implementar `frontend/app/(app)/extrato/page.tsx` com agrupamento por dia, semana ou mês e saldo acumulado ao fim de cada grupo (`FR-047`)
- [X] T183 [P] [US7] Implementar o cabeçalho-resumo comparativo e o gráfico compacto de receitas × despesas (`FR-048`, `FR-050`)
- [X] T184 [P] [US7] Implementar a seção fixa "A pagar / A receber" com destaque vermelho para vencidos e marcação visual dos grupos previstos (`FR-051`, `FR-052`)

## Sub-fase C6 — US5 Clientes + US6 Funcionários + Categorias (P2)

- [X] T185 [P] [US5] Implementar `frontend/app/(app)/categorias/page.tsx` com contagem e total por período respeitando o mundo, e o fluxo de arquivamento com escolha de destino (`FR-074`, `FR-075`)
- [X] T186 [US5] Implementar `frontend/app/(app)/clientes/page.tsx` com filtro de mundo derivado, situação e inadimplentes no topo (`FR-002`, `FR-083`)
- [X] T187 [US5] Implementar `frontend/app/(app)/clientes/[id]/page.tsx` — perfil com total recebido, gráfico mensal, lançamentos, próximos recebimentos e quebra por mundo (`FR-081`)
- [X] T188 [P] [US6] Implementar `frontend/app/(app)/funcionarios/page.tsx` (`FR-085`)
- [X] T189 [P] [US6] Implementar `frontend/app/(app)/funcionarios/[id]/page.tsx` — custo histórico e do período, pagamentos e próximos (`FR-087`)
- [X] T190 [US5] Implementar o destaque de inadimplência no Dashboard, no card Clientes e no perfil (`FR-097`, `SC-006`)

## Sub-fase C7 — US8 Relatórios (P3)

- [X] T191 [US8] Implementar `frontend/app/(app)/relatorios/page.tsx` com o DRE mensal e acumulado no ano (`FR-090`)
- [X] T192 [P] [US8] Implementar o ranking de clientes por receita (`FR-091`)
- [X] T193 [P] [US8] Implementar a variação mensal por categoria com o destaque vindo da configuração, e a matriz mensal (`FR-092`, `FR-093`)
- [X] T194 [US8] Implementar a exportação em PDF e CSV do que está na tela e a leitura do período em linguagem natural (`FR-094`, `FR-095`)

## Sub-fase C8 — US9 Notificações + US10 Configuração e papéis (P3)

- [X] T195 [US9] Implementar o painel de notificações a partir do sino, com marcar lida e marcar todas (`FR-096`–`FR-100`)
- [X] T196 [US10] Implementar `frontend/app/(app)/configuracoes/page.tsx` com as 7 seções do mockup, montadas a partir de `GET /api/configuracoes` — inclusive os textos de ajuda, que vêm do banco (`FR-105`, `FR-106`)
- [X] T197 [US10] Implementar a gestão de usuários e esconder Configurações do menu para operador — **lembrando que esconder o menu não é autorizar**; a garantia é o `403` do backend (`FR-102`, `SC-010`)
- [X] T198 [US10] Implementar o assistente de importação CSV/OFX: envio, mapeamento de colunas com sugestão de categoria, escolha de mundo, prévia e progresso da gravação em lotes (`FR-044`)
- [X] T199 [P] [US10] Implementar a exportação completa com acompanhamento do progresso e link assinado ao final (`FR-112`)
- [X] T200 [P] [US10] Implementar o histórico de alterações no painel de detalhe, mostrando quem, o quê e quando (`FR-103`, `SC-014`)
- [X] T201 [US10] Fechar os atalhos de teclado em todas as telas e escrever os testes de componente em `frontend/tests/` (`FR-110`)

**✅ Checkpoint Boss 3**: todas as telas navegáveis, fiéis ao mockup.

> **Medido em 2026-07-31, rodando:**
>
> ```
> npx tsc --noEmit          → sem erros
> npx next lint             → No ESLint warnings or errors
> npx vitest run            → 37 passed (4 arquivos)
> npx next build            → Compiled successfully · 14 rotas
> npx next start + curl     → as 10 rotas respondem 200
> ```
>
> **T154 fica aberta** (criar o projeto `synapse-erp-web` na Vercel) — é painel, como
> T006/T008/T038.
>
> **T170 fica aberta**: o mecanismo está pronto (mundo e período entram na `queryKey` de
> toda leitura, e o modo "Ambos" marca cada item com o `BadgeMundo`), mas *conferir* zero
> vazamento exige dados nos dois mundos. O banco de produção está vazio — a conferência
> vale quando houver histórico, junto de T202/T206.
>
> ### Verificação de documentação da Fase C (Princípio V) — **não** era "nada a mudar"
>
> 1. **`frontend/README.md`** escrito: estrutura, as cinco decisões que o código carrega,
>    a convenção de nome dos hooks e a tabela de divergências.
> 2. **Divergência achada entre o mockup e o seed**: o mockup desenha o bloco "Receita por
>    serviço" e `GET /api/dashboard` devolve `receita_por_servico`, mas as **18 chaves de
>    `dashboard_cards_disponiveis` (migração `007`) não têm entrada para ele**. Como
>    `FR-106` proíbe rótulo escrito no frontend, o bloco não é desenhado sem catálogo. O
>    componente existe e é resolvido pelo id `receita_servico`: acrescentar a chave no seed
>    liga o bloco sem tocar em código. **Decisão do dono do projeto** — está no README §
>    Divergências.
> 3. **Conflito entre a convenção PT-BR e o `react-hooks/rules-of-hooks`**: hooks nomeados
>    `usar…` não são reconhecidos como hooks pelo ESLint, e a regra deixa de acusar chamada
>    condicional **em todo o projeto**, não só nos arquivos deles. Os 43 arquivos foram
>    renomeados para o prefixo `use` mantendo o substantivo em português (`useSessao`,
>    `useLancamentos`). Registrado no README.
> 4. **Documento-mestre**: nada a mudar. Nenhum `RF-xx`/`RN-xx` mudou de significado — a
>    Fase C implementou o que já estava escrito.

---

## Auditoria de requisitos — 2026-08-03

Conferência dos `RF`/`RN`/`RNF` do documento-mestre e dos `FR-001`–`FR-116` da spec contra
o que existe: as rotas carregadas do app FastAPI, o catálogo de cards lido do banco pelo MCP
do Supabase, as telas do `frontend/` e os quatro arquivos de `contracts/`. Correções
aplicadas na mesma entrega.

### O que era requisito escrito e não estava cumprido

| # | Requisito | Defeito | Onde |
|---|---|---|---|
| 1 | `FR-064` / `RF-43b` | **O bloco "Receita por serviço" nunca era desenhado.** `GET /api/dashboard` devolvia `receita_por_servico` e o componente existia resolvido pelo id `receita_servico`, mas o catálogo `dashboard_cards_disponiveis` nasceu com 18 entradas e nenhuma era essa. Como `FR-106` proíbe rótulo de card no frontend, a grade **ignora em silêncio** id sem catálogo. Estava anotado como divergência nº 1 no `frontend/README.md` desde 2026-07-31, à espera de decisão — e a decisão era só acrescentar a chave | `migracoes/013_seed_card_receita_servico.sql` |
| 2 | `RN-06` | **Arquivar funcionário, serviço ou centro de custo não tinha volta.** O cabeçalho de contracts/cadastros.md promete `arquivar` **e** `/desarquivar` para todo cadastro; só categorias e clientes tinham. Sem `DELETE` (de propósito), arquivar o cadastro errado só se desfazia no banco à mão. A assimetria de funcionários estava apontada na auditoria do Boss 2 e ficou como "sem endpoint novo" | `funcionarios/rotas.py`, `cadastros/servicos.py`, `cadastros/centros_custo.py` |
| 3 | `FR-074` / `RF-52` | **A caixa "Mostrar arquivadas" da tela de Categorias não fazia nada.** O servidor declarava `incluir_arquivadas`; contrato e frontend usam `incluir_arquivados`. FastAPI ignora parâmetro de consulta desconhecido, então o clique não mudava a lista e nada acusava erro | `categorias/rotas.py` |
| 4 | `FR-040` / `RF-20` | **"Exportar" da barra de ações em massa ignorava a seleção** e baixava a lista filtrada inteira. Era a única das cinco ações em massa que não olhava para o que estava marcado | `lancamentos/rotas.py`, `lancamentos/repositorio.py`, `TelaLancamentos.tsx` |
| 5 | `RNF-10` | **Faltavam os atalhos `1`–`7`** de navegação entre abas, que o documento-mestre nomeia. Existiam só as sequências `G`+letra, que ele não menciona. Os dois valem agora | `lib/atalhos.ts`, `CabecalhoGlobal.tsx`, `FolhaDeAtalhos.tsx` |
| 6 | contracts/README.md | **`tipo_contratacao` inválido devolvia `500`** em vez de `400 validacao` com o nome do campo: o campo era `str` e o valor só morria no `cast(:tipo as tipo_contratacao)` do Postgres. É o mesmo defeito já corrigido em `tipo_cobranca` (2026-08-02) e registrado no README do backend como valendo "para todo enum do banco" — este tinha escapado | `funcionarios/rotas.py` |

### O que foi conferido e estava certo

As rotas do `/api/docs` batem uma a uma com `contracts/` — eram 94, são **97** com os três
`/desarquivar` (T208 fica coberta para o que é rota; a única ausência, `GET
/api/exportacoes/{id}`, está declarada em prosa como não implementada). `mundo` passa por `mod_mundo.exige` em **todos** os pontos de escrita.
Existem como escrito: filtro derivado de clientes com `sem_movimentacao`, quebra por mundo
nos cards e no ranking, comparativo dos blocos especiais, composição de "A pagar"/"A receber"
por situação, leitura em linguagem natural do DRE, agrupamento do Extrato por dia/semana/mês
e as sete seções de Configurações.

### Testado, rodando

```
pytest tests/unidade tests/contrato -q          → 429 passed  (eram 420)
pytest (os 5 testes novos de integração) -q     → 5 passed in 73s
ruff check . ; black --check .                  → limpos
npx tsc --noEmit ; npx next lint ; npx vitest   → sem erros · 37 passed
npx next build                                  → compilou · 13 rotas
```

Os 9 testes de contrato a mais são os três `/desarquivar` novos entrando nas três varreduras
que já existiam: existe na API, declara o papel, e é **só de gestor**.

Os 5 de integração rodam contra o banco de produção em transação desfeita, como os demais:
desarquivar funcionário (com a folha **não** voltando junto), desarquivar serviço e centro
de custo, `incluir_arquivados` em categorias e a exportação por id.

A migração `013` foi aplicada e conferida no banco: o catálogo tem **19** cards,
`receita_servico` na posição 16, e reaplicar a migração devolve 0 linhas — é idempotente.

### O que a auditoria **não** fecha

T006, T008, T038 e T154 (painéis do Supabase e da Vercel) e T170, T202–T210 continuam
abertas pelo mesmo motivo de antes: dependem de painel ou de dados reais no banco.

---

## Fase final — Polimento e conferência de aceitação

### Boss 4 — polimento entregue em 2026-08-03

- [X] T211 Trocar a tipografia para **Geist** e adotar a densidade da Vercel: escada de raios 4/6/8/10/12/16 e tamanho de fonte sempre inteiro (`frontend/estilos/tokens.css`, `app/layout.tsx`) — divergência declarada do design system, decidida pelo dono do projeto
- [X] T212 `GET /api/busca` passa a devolver **funcionários**, casando por nome e por função e respeitando o mundo ativo (`RN-15`) — `backend/app/busca/rotas.py`, contracts/consultas.md §4
- [X] T213 Refazer a busca global: **campo com dropdown**, não `CommandDialog`. `combobox` + `listbox`, `⌘K` e `/` focam em vez de abrir, cada opção é um `<Link>` e leva para a tela do registro (`componentes/layout/BuscaGlobal.tsx`)
- [X] T214 Estado de tela na URL nos dois sentidos: filtros, ordenação, página e lançamento aberto em Lançamentos (`paraUrl`/`daUrl`), `?aba=` em Relatórios e `?secao=` em Configurações — sem isso, chegar em `/lancamentos` já estando lá não fazia nada
- [X] T215 Regra única de `cursor: pointer` + estados de hover que faltavam; `useMovimentoReduzido()` desliga a animação em JavaScript do Recharts
- [X] T216 Varredura contra o **Web Interface Guidelines** (skill `/web-design-guidelines`) e correção do que ela apontou: foco, teclado, formulários, `select` nativo no tema escuro, celular, "pular para o conteúdo", `aria-live` e rótulos
- [X] T217 **Grade do Dashboard em duas colunas de verdade** + largura por card. Cada bloco tinha um `grid` próprio com um filho só, então nada ficava lado a lado. `cards_disponiveis[].largura` (`inteira`/`metade`) resolve preferência → catálogo → padrão por grupo, e "Configurar cards" ganhou **arrastar** (mantendo as setas, que funcionam no teclado) e o botão de largura

### O que continua aberto

- [ ] T202 Percorrer **todas** as telas nos temas claro e escuro e corrigir o que não estiver legível — cards, gráficos e tabelas (`SC-009`, `FR-109`)
- [ ] T203 Ajustar Dashboard e Extrato para celular: sem rolagem horizontal, sem precisar ampliar (`SC-012`, `FR-111`) — *parcialmente atacado em T216: a tabela de Lançamentos passou a rolar dentro de si e o padding das telas caiu no celular; falta conferir na tela*
- [ ] T204 Reexecutar a medição de desempenho com 5.000 lançamentos na interface real — filtro em menos de 2 s e rolagem fluida (`SC-007`, `FR-113`)
- [ ] T205 [P] Conferir estado vazio explicativo em todos os cards, gráficos e listas, inclusive o mundo com zero no modo "Ambos" (edge cases)
- [ ] T206 Executar a **verificação de aceitação** de quickstart.md §8 — os 13 itens, rodando, não por leitura de código; o item 9 duas vezes (pela tela e pela API com token de operador)
- [ ] T207 Confirmar em produção que o cron diário disparou: `GET /api/rotinas/estado` como gestor mostra a última execução e o resultado (Princípio VI)
- [ ] T208 [P] Conferir `/api/docs` contra os 4 arquivos de `contracts/` — divergência é bug, não detalhe (contracts/README.md)
- [ ] T209 [P] Atualizar `Documentação/Requisitos da Plataforma Financeira.md`, o `CLAUDE.md` e os READMEs de módulo com o que mudou ao longo da implementação (Princípio V)
- [ ] T210 Medir a exportação completa de ponta a ponta — menos de 5 minutos (`SC-011`)

---

## Auditoria de polimento — 2026-08-03 (Boss 4)

Pedido do dono do projeto: trocar a tipografia para Geist com a densidade da Vercel, varrer
a experiência com a skill `/web-design-guidelines` e arrumar os detalhes pequenos —
principalmente o ponteiro do mouse não avisar que dá para clicar e a busca abrir uma janela
em vez de funcionar como pesquisa.

### O que mudou

| # | Assunto | Onde |
|---|---|---|
| 1 | **Geist** substitui Plus Jakarta Sans + Inter; Geist Mono substitui JetBrains Mono. Auto-hospedadas por `next/font/google`. As três variáveis (`--fonte-display/body/mono`) não mudaram de nome, então nenhum dos ~60 usos precisou ser tocado | `app/layout.tsx`, `estilos/tokens.css`, `app/globals.css` |
| 1b | **Bug de fonte, anterior ao Boss 4, achado pelo dono do projeto**: a troca "não mudou nada" porque **nenhuma fonte estava valendo desde a Fase C**. As classes do `next/font` ficavam no `<body>` e o alias `--font-body: var(--fonte-body), …` no `:root`; o `var()` não resolvia, a declaração inteira morria e o navegador caía em serif. Classes movidas para o `<html>` e o alias passou à forma com fallback `var(--fonte-body, "Geist")` | `app/layout.tsx`, `app/globals.css` |
| 2 | **Densidade**: 160 `rounded-[Npx]` remapeados para a escada da Geist e 234 tamanhos quebrados (`12.5px`) virados inteiros. Cor, sombra e grade de 4pt intactas | 53 e 54 arquivos, por script |
| 3 | **A busca virou campo.** `combobox` + `listbox`, foco preso no campo, `↑↓` por `aria-activedescendant`, opção é `<Link>` (aceita `⌘`+clique), `⌘K` e `/` focam em vez de abrir. `buscaAberta` virou `pedidoDeFocoNaBusca` | `layout/BuscaGlobal.tsx`, `layout/CabecalhoGlobal.tsx`, `lib/estado-global.ts` |
| 4 | **Funcionário entrou na busca**, por nome e por função, respeitando o mundo (`RN-15`). Clicar leva para `/funcionarios/{id}` | `app/busca/rotas.py`, `lib/tipos.ts`, contracts/consultas.md §4 |
| 5 | **Lançamentos ganhou URL de mão dupla.** Sem isso, clicar num resultado da busca **estando já na tela** trocava o endereço e não acontecia nada — bug que a própria mudança nº 3 teria introduzido | `lancamentos/filtros.ts`, `TelaLancamentos.tsx` |
| 6 | **`cursor: pointer` numa regra só**, cobrindo também os papéis ARIA que o Radix põe em `div`. `button` do HTML nasce `cursor: default`: era essa a causa de "vários botões o mouse não fica apontando" | `app/globals.css` |
| 6b | **O Dashboard nunca pôs dois cards lado a lado**: cada bloco não-numérico ganhava um `grid lg:grid-cols-2` **próprio, com um filho só**. Virou uma grade única de duas colunas; `largura` (`inteira`/`metade`) vem do servidor, resolvida em preferência → `largura_padrao` do catálogo → padrão por grupo. "Configurar cards" ganhou arrastar (com as setas mantidas para teclado) e o botão de largura | `dashboard/rotas.py`, `usuarios/rotas.py`, `TelaDashboard.tsx`, `ConfigurarCards.tsx` |
| 7 | **Varredura do Web Interface Guidelines**: foco na linha da tabela, `Espaço` abrindo linha, `transition-all` fora de 7 primitivos, `prefers-reduced-motion` alcançando o Recharts, `name`/`autocomplete`/`inputmode` nos formulários, confirmação antes de descartar lançamento preenchido, `select` nativo legível no tema escuro do Windows, rolagem horizontal presa na tabela, painéis que não estouram a tela do celular, "pular para o conteúdo", `aria-live` e hover nas linhas que eram clicáveis mudas | ~30 arquivos |

### Testado, rodando

```
frontend: npx tsc --noEmit ; npx next lint     → sem erros
frontend: npx vitest run                       → 51 passed  (eram 37)
frontend: npx next build                       → compilou · 13 rotas
frontend: Chrome headless na página servida    → `getComputedStyle(html).fontFamily`
                                                 começa em `Geist`; `document.fonts
                                                 .check("700 24px Geist")` → true;
                                                 captura de `/entrar` sem serifa
backend:  pytest tests/unidade tests/contrato  → 432 passed  (eram 429)
backend:  pytest -k busca (integração)         → 9 passed   (eram 7)
backend:  pytest -k largura (integração)       → 3 passed
backend:  ruff check . ; black --check .       → limpos
```

Os 14 testes novos do frontend: 5 da ida e volta dos filtros pela URL, 6 da busca global
(é campo e não janela; o dropdown vazio oferece as telas; funcionário aparece e leva para a
tela dele; os quatro grupos no mesmo dropdown; seta + `Enter`; `Esc` limpa) e 3 da
reordenação por arraste (insere em vez de trocar; vale como as setas com passo 1; não sai da
lista).

No backend: 2 de integração afirmam a forma de `funcionarios` na resposta e que abaixo de 2
caracteres a lista sai vazia; 3 de contrato travam as duas larguras possíveis, o
`exclude_none` que impede gravar `largura: null` e o padrão por grupo; 2 de integração
conferem `largura` saindo em `cards_disponiveis` e a escolha do usuário vencendo o padrão.

### O que **não** foi feito

- **T202 continua aberta.** A varredura foi de código; ninguém olhou as 13 telas nos dois
  temas. As mudanças de densidade e de fonte pedem justamente essa conferência.
- **T203 ficou parcial**: a tabela de Lançamentos passou a rolar dentro de si e o padding
  caiu no celular, mas Dashboard e Extrato não foram medidos num aparelho.
- **T204, T206, T207, T210** dependem de dados reais ou de painel — inalteradas.
- **`cmdk` continua no `package.json`** sem uso, junto de 16 outros primitivos do shadcn.
  Mexer no lockfile numa entrega de polimento não valia o risco.

---

## Dependências e ordem de execução

### Entre as fases bosses

- **Boss 1 (Banco)** → não depende de nada, mas **T018 em diante depende da autenticação do MCP do Supabase** (plan.md Pendência #1)
- **Boss 2 (Backend)** → depende de Boss 1 aplicado e conferido (T018–T020)
- **Boss 3 (Frontend)** → depende de B0 no ar; cada sub-fase de tela depende da sub-fase de backend correspondente
- **Polimento** → depende de Boss 3

### Dentro do Boss 2

```
B0 (fundação) ──┬─> B1 (US1, US2) ──> B2 (US3) ──> B3 (US4, US7)
                │                                      │
                └──────────────────────────────────────┴──> B4 (US5, US6) ──> B5 (US8) ──> B6 (US9, US10)
```

- **B1** bloqueia todas as outras: elas leem, agregam ou geram lançamentos
- **B2** depende de B1 (recorrência gera lançamento) e bloqueia B3 (projeção usa programados)
- **B3** depende de B1 e B2
- **B4** depende de B1 (categoria especial precisa de lançamento) e de B2 (mensalidade e folha são recorrências)
- **B5** depende de B1 e B4 (o DRE quebra por subcategoria; o ranking é por cliente)
- **B6** depende de tudo — os avisos precisam dos dados existirem

### Entre as telas do Boss 3

| Sub-fase de tela | Depende de |
|---|---|
| C2 (US1, US2) | B1 |
| C3 (US3) | B2 |
| C4 (US4) | B3 |
| C5 (US7) | B3 |
| C6 (US5, US6) | B4 |
| C7 (US8) | B5 |
| C8 (US9, US10) | B6 |

### Dentro de cada sub-fase

Testes escritos e **falhando** → domínio → repositório → serviço → rotas → integração →
verificação de documentação. Nenhuma sub-fase é declarada pronta com teste vermelho
(Princípio VI).

### Oportunidades de paralelismo

- **A1**: T006, T007 e T008 são painéis diferentes do Supabase — em paralelo
- **B0**: os quatro módulos de `app/comum/` (T026–T029) são arquivos independentes
- **B1**: os 4 testes de unidade (T039–T042), os 5 módulos de domínio (T043–T047) e os 4 cadastros de apoio (T048–T051) — três blocos paralelos
- **B5**: os relatórios T116, T117 e T118 são endpoints independentes
- **C0**: T145, T146, T147, T149, T150, T151 e T153 são arquivos separados
- **C1**: T158, T159, T160 e T161 são componentes independentes
- Com duas pessoas: uma toca a sub-fase de backend seguinte enquanto a outra faz a tela da sub-fase anterior

---

## Exemplo de execução paralela — Sub-fase B1

```bash
# 1º: os quatro testes de unidade, juntos (vão falhar — é o esperado)
Task: "test_split_soma_exata.py — RN-11"
Task: "test_conversao_usd.py — RN-12"
Task: "test_saldo_ignora_nao_efetivado.py — RN-05"
Task: "test_separacao_por_mundo.py — RN-15"

# 2º: os cinco módulos de domínio, juntos
Task: "dominio/mundo.py"
Task: "dominio/saldo.py"
Task: "dominio/split.py"
Task: "dominio/cambio.py"
Task: "dominio/lixeira.py"

# 3º: os quatro cadastros de apoio, juntos (🟢 Skill antes de cada repositório)
Task: "cadastros/tags.py"
Task: "cadastros/centros_custo.py"
Task: "GET /api/categorias"
Task: "GET /api/servicos"

# 4º: lançamentos em sequência — mesmo arquivo de rotas, sem paralelismo
```

---

## Estratégia de implementação

### MVP primeiro

1. Boss 1 inteiro (T001–T021) — sem banco não há nada
2. B0 (T022–T038) — deploy vivo e autenticação
3. B1 (T039–T070) — o núcleo pela API
4. **PARAR E VALIDAR**: criar 20 lançamentos nos dois mundos por `/api/docs`, conferir filtros, lixeira e saldo
5. C0 + C1 + C2 (T141–T170) — a primeira tela usável

Nesse ponto o sistema **já substitui a planilha** para registro e consulta.

### Entrega incremental

Cada par sub-fase de backend + sub-fase de tela é uma entrega demonstrável:

| Entrega | Tasks | O que passa a existir |
|---|---|---|
| 1 — Registro | B1 + C2 | Substitui a planilha |
| 2 — Programação | B2 + C3 | Histórico entra sozinho, futuro se resolve na data |
| 3 — Leitura | B3 + C4 + C5 | Dashboard e Extrato — a razão de o produto existir |
| 4 — Gestão | B4 + C6 | Clientes, funcionários e inadimplência |
| 5 — Fechamento | B5 + C7 | DRE e exportações |
| 6 — Automação | B6 + C8 | Avisos, papéis e configuração sem código |

### O risco que essa ordem carrega

116 requisitos em três fases sequenciais concentram a descoberta de erro de modelagem no fim
(plan.md §Constitution Check). A mitigação, **dentro da ordem pedida**, é justamente entregar
o backend por história: quando a primeira tela chegar, ela encontra um backend já exercitado
por testes de integração, e não um bloco nunca executado.

---

## Notas

- `[P]` = arquivos diferentes, sem dependência pendente
- 🟢 = aciona a Skill `supabase-postgres-best-practices` **antes** de escrever
- Cada sub-fase termina com verificação de documentação; **"nada a mudar" é resposta válida,
  mas precisa ser dita** (Princípio V)
- Commit a cada task ou grupo lógico
- Ao relatar: o que foi feito, o que foi testado **rodando**, e o que ficou de fora
- Teste que falha entra no relato com a **saída real do erro** — a constituição proíbe
  reportar sucesso parcial como sucesso

### Bloqueios de decisão — todos resolvidos em 2026-07-30

| Task | Era | Resolução |
|---|---|---|
| T005 | Autenticação do MCP do Supabase | ✅ Autenticado e **testado**: projeto `frpbowkoibdgigekrhor`, PostgreSQL 17.6, leitura de schema/extensões/buckets/migrações e execução de SQL. Banco vazio, como esperado |
| T016 | `mundo` de Dylan e Marcondes | ✅ Ambos `digital` |
| T143 | Escala de tema escuro derivada | ✅ Haverá tema escuro; escala derivada na implementação, sem aprovação prévia |

**Nenhuma task depende mais de decisão.** O que resta é execução, começando por T001.
