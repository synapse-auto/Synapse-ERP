# Implementation Plan: Plataforma Financeira Synapse (ERP interno v1)

**Branch**: `001-erp-financeiro-synapse` (diretório de spec; repositório git ainda não iniciado)
**Date**: 2026-07-29
**Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-erp-financeiro-synapse/spec.md`

**Artefatos desta fase**: [research.md](./research.md) · [data-model.md](./data-model.md) ·
[contracts/](./contracts/) · [quickstart.md](./quickstart.md)

---

## Summary

ERP financeiro interno da Synapse para 3 usuários, com dois mundos financeiros separados
(Digital e Infra), lançamentos com recorrência retroativa, dashboard de saúde do caixa e
relatórios de fechamento. 116 requisitos funcionais, 10 histórias de usuário priorizadas
P1–P3.

**Abordagem técnica**: monorepo com backend FastAPI (Python 3.12) e frontend Next.js 15,
os dois hospedados na Vercel como projetos separados do mesmo repositório, com o Next.js
fazendo proxy de `/api/*` para o backend (mesma origem, sem CORS). Dados em PostgreSQL
gerenciado pelo Supabase, que também fornece login (Auth) e armazenamento de anexos
(Storage). Regras de negócio (`RN-01`…`RN-16`) concentradas em módulos de domínio no
backend, nunca em componente de tela. Interface construída sobre shadcn/ui com os tokens do
Synapse Design System aplicados sem reinterpretação.

**Duas correções de rumo em relação ao pedido original**, ambas decididas pelo dono do
projeto em 2026-07-29:

1. **SQLite → Supabase (PostgreSQL)**. SQLite não sobrevive na Vercel — o disco das funções
   é descartado a cada requisição, então o banco nasceria vazio a cada uso. Não é
   configuração; é como a plataforma funciona. Detalhe e alternativas em research.md D-01.
   Efeito colateral positivo: PostgreSQL é o que a constituição já exige, então a mudança
   **remove** uma divergência.
2. **Os três `NEEDS CLARIFICATION` da spec foram respondidos** e estão registrados em
   research.md D-04, D-05 e D-06. A spec e o checklist foram atualizados nesta mesma
   entrega (Princípio V).

---

## Technical Context

**Language/Version**: Python 3.12 (backend) · TypeScript 5.x / Node 22 (frontend)

**Primary Dependencies**:
- Backend — FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 Core, asyncpg, PyJWT,
  python-dateutil, ofxparse, reportlab, pytest/httpx
- Frontend — Next.js 15 (App Router), React 19, shadcn/ui, Tailwind, Recharts (via `chart`
  do shadcn), TanStack Table, TanStack Query, react-hook-form, zod, zustand, date-fns,
  Lucide, Vitest/Testing Library
- Plataforma — Supabase (Postgres + Auth + Storage), Vercel (hosting + Cron)

Cada escolha, com alternativas descartadas e o motivo, em [research.md](./research.md) §5
(exigência do Princípio II).

**Storage**: PostgreSQL gerenciado pelo Supabase. **20** tabelas, **12** tipos enumerados, uma
view (`lancamentos_ativos`), o gatilho de imutabilidade de `mundo`. Anexos em bucket privado do
Supabase Storage. Esquema completo em [data-model.md](./data-model.md).

> São **20**, não 19: `importacoes` nasceu em B6 (migração `011`), quando o fluxo de três
> requisições da importação (`FR-044`) mostrou que o conteúdo lido precisa sobreviver entre
> elas. Aplicada e conferida em 2026-07-31.

> Corrigido em 2026-07-30 (Fase A aplicada): são **12** `CREATE TYPE`, não 13. data-model §2
> lista 13 nomes, mas `escopo_edicao_serie` é parâmetro de endpoint e não coluna — está lá por
> completude do vocabulário. E o gatilho de `mundo` é **um por tabela que tem a coluna**: seis
> gatilhos compartilhando uma função (`recusa_alteracao_de_mundo`), não um só.

**Testing**: pytest + pytest-asyncio + httpx no backend (unidade para domínio, integração
contra Postgres real, contrato contra os arquivos de `contracts/`). Vitest + Testing Library
no frontend. Alvos obrigatórios de teste automatizado, fixados pela constituição
(Princípio VI): `RN-03` ciclo de status, `RN-05` só efetivado conta no realizado, `RN-05a`
recorrência retroativa, `RN-11` integridade do split, `RN-12` conversão USD→BRL, `RN-15`
separação por mundo.

**Target Platform**: navegador desktop moderno como alvo principal; Dashboard e Extrato
utilizáveis em celular (`RNF-05`, `FR-111`, `SC-012`). Backend em função serverless Python na
Vercel.

**Project Type**: aplicação web — backend de API + frontend separados.

**Performance Goals**:
- `SC-007`: com 5.000 lançamentos, aplicar filtro responde em menos de 2 s e a rolagem
  permanece fluida.
- `SC-002`: Dashboard legível em 10 s sem clicar — daí a decisão de servir o Dashboard
  inteiro em **uma** requisição (contracts/consultas.md §1).
- `SC-011`: exportação completa em menos de 5 min.

**Constraints**:
- **Sem processo de fundo e sem worker**: a plataforma só oferece função por requisição. Toda
  automação é cron chamando endpoint idempotente (research.md D-08).
- **Duração máxima da função é limitada** e menor no plano gratuito: recorrência retroativa
  longa, importação e exportação completa operam **em lotes com cursor** e progresso na tela.
- **Cron do plano gratuito roda uma vez por dia**: o desenho cabe nesse limite; nenhuma regra
  da spec exige granularidade menor que um dia.
- **Tamanho do pacote da função é limitado**: por isso `pandas` está fora e o PDF usa
  reportlab.
- **Cold start** de alguns segundos após inatividade: aceitável para 3 usuários internos; o
  frontend mostra carregamento em vez de parecer travado.
- **PT-BR e BRL** obrigatórios na interface: `1.234,56`, `dd/mm/aaaa` (`RNF-03`). Na API,
  transporte é ISO e decimal em string.
- **Tema claro e escuro** em 100% das telas (`RNF-09`, `SC-009`) — e o design system **não
  define tokens escuros** (ver lacuna abaixo).

**Scale/Scope**: 3 usuários simultâneos, dezenas a centenas de lançamentos/mês, dimensionado
para milhares acumulados. 116 requisitos funcionais, ~10 telas mais painéis e formulários,
19 tabelas, ~75 endpoints.

---

## Regra obrigatória: Supabase passa pela Skill

**Toda vez que o trabalho tocar o Supabase — estrutura ou consulta — a Skill
`supabase-postgres-best-practices` é acionada ANTES de escrever qualquer SQL ou código de
acesso.** Não é sugestão nem "quando lembrar": é passo obrigatório da task, no mesmo nível de
"testar de verdade".

Vale para:

| Situação | Exemplos nesta feature |
|---|---|
| Criar ou alterar estrutura | Migrações `001`…`008`, tabelas, enums, view `lancamentos_ativos`, trigger de imutabilidade de `mundo`, índices, constraints |
| Escrever ou revisar consulta | Todo `repositorio.py`, a consulta única do Dashboard, Extrato paginado, relatórios, busca global, agregações por mundo/período |
| Políticas e acesso | RLS de negação para a chave `anon` (research.md D-03a), papéis, grants |
| Configuração do banco | Extensões, tipos, defaults, pool de conexão, timeouts |
| Storage e Auth do Supabase | Bucket privado de anexos, URL assinada, validação do JWT |

Ordem dentro da task: **Skill → escrever → testar → verificar documentação**. A Skill entra no
passo 1 do fluxo da constituição (pesquisar referência pronta, Princípio II) e a pesquisa fica
registrada como qualquer outra.

Se a orientação da Skill conflitar com o que está em data-model.md ou research.md, o conflito
é **declarado no relato da task** — não se resolve em silêncio nem se ignora a Skill.

---

## Constitution Check

*GATE: verificado antes da pesquisa e reavaliado após o desenho.*

Contra [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) v1.0.0.

### Princípios I–VII

| # | Princípio | Situação | Como o plano cumpre |
|---|---|---|---|
| I | Simplicidade (KISS+YAGNI) | ✅ | Sem ORM completo, sem fila, sem worker, sem cache externo, sem virtualização antes de medir. Preferências em `jsonb` em vez de três tabelas (D-09). Nenhuma abstração criada com um só uso. |
| II | Não reinventar a roda | ✅ | Pesquisa registrada em research.md §5 e §6 com alternativas descartadas. Supabase Auth em vez de autenticação própria. shadcn/ui, Recharts, TanStack, dateutil, ofxparse, reportlab. Referências de arquitetura: Firefly III, Akaunting, ERPNext, Google Agenda (research.md D-13). |
| III | Código limpo e DRY | ✅ | Toda `RN-xx` tem **um** módulo dono em `backend/app/dominio/` (mapa em data-model.md §5). View `lancamentos_ativos` evita repetir o filtro de soft delete. D-07 escolhido explicitamente para não duplicar lógica de agrupamento em muitos lugares. |
| IV | Organização explícita | ✅ | Pastas por domínio (`lancamentos/`, `clientes/`, …), camadas `rotas → servico → repositorio`. REST no plural em PT-BR. Contratos escritos em `contracts/` **antes** do código, mais OpenAPI publicado em `/api/docs`. Frontend nunca fala com o banco (D-03a). |
| V | Documentação viva | ✅ | spec.md e o checklist atualizados nesta entrega com as respostas de `FR-114`/`115`/`116`. Pendências para o documento-mestre listadas abaixo. Toda task da implementação termina com o check de documentação. |
| VI | Nada funciona até ser testado | ✅ | Os 6 alvos obrigatórios de teste estão nomeados. `execucoes_rotina.ultimo_resultado` grava o que a rotina de fato fez, para que "funcionou" seja verificável e não afirmado. |
| VII | Nada hardcoded | ✅ | Tabela `configuracoes` com 16 chaves seed (data-model.md §3.15), incluindo rótulos e ordem padrão dos cards. Limiar de destaque de variação, tolerância de inadimplência, multiplicadores do semáforo e antecedências de alerta vêm do banco e são devolvidos pela API junto do dado. Segredos em variável de ambiente. |

### Padrões Técnicos Obrigatórios

| Exigência | Situação | Observação |
|---|---|---|
| Interface 100% PT-BR, R$ 1.234,56, dd/mm/aaaa | ✅ | `Intl` nativo; API transporta ISO/decimal |
| shadcn/ui como base | ✅ | |
| Dark mode **e** light mode em todos os cards, gráficos e tabelas | ✅ **resolvido** | Escala escura aprovada em 2026-07-30 — ver abaixo |
| **PostgreSQL** | ✅ | Supabase. A mudança de SQLite **alinha** com a constituição |
| `mundo` obrigatório e imutável em toda entidade financeira exceto categorias | ⚠️ **exceção nova** | Ver abaixo |
| Soft delete com auditoria de quem/quando/o quê | ✅ | `excluido_em`/`excluido_por` + tabela `auditoria` |
| Cliente e funcionário arquivados, nunca excluídos | ✅ | Sem `DELETE` nesses recursos |
| RBAC desde o primeiro endpoint, papel declarado por endpoint | ✅ | Declarado em todos os arquivos de `contracts/` |
| Listas com paginação ou virtualização | ✅ | Paginação no servidor, padrão 50 |

### Duas pendências declaradas em voz alta

A constituição exige que exceção a princípio seja **declarada com justificativa e aceita
pelo dono do projeto** — silêncio não é aprovação. São duas:

**1. `RN-15` ganha uma segunda exceção: `clientes` não tem `mundo`.**
Decidido pelo dono do projeto (research.md D-04). Consequência que precisa ser aceita: o
filtro "clientes do mundo ativo" de `RF-101` passa a ser derivado da movimentação do
cliente, e cliente ainda sem lançamento aparece nos três estados do seletor. Em troca, o
ranking de clientes e o perfil ganham a quebra por mundo, que seria impossível com cadastros
separados. **Precisa ser refletido no documento-mestre** (`RN-15` e `RF-101`).

**2. ~~O design system não tem tema escuro, e a spec exige tema escuro.~~ Resolvido em
2026-07-30.**
`RNF-09`/`FR-109`/`SC-009` pedem 100% das telas legíveis nos dois temas. O Synapse Design
System define **só** a escala clara, e o mockup existe **só** em claro. **Decisão do dono do
projeto**: haverá tema escuro mesmo sem estar no design system, e a escala é **derivada na
hora da implementação**, seguindo as regras que o próprio design system enuncia (nunca `#000`;
elevação por luminosidade em vez de sombra colorida; roxo de ação um passo mais claro;
semânticos reajustados para contraste AA) — detalhe em research.md D-12. Não volta ao projeto
do Claude Design para aprovação prévia: a Fase C está liberada. Consequência aceita: o tema
escuro nasce como extensão da implementação, não como parte versionada do design system, e a
conferência é visual, tela a tela (task T202).

### Reavaliação pós-desenho

Nenhuma violação surgiu no desenho. A tabela de Complexity Tracking permanece vazia — não há
abstração adicionada sem dois usos, nem camada além de `rotas → serviço → repositório`.

**Um risco de processo, não de princípio**: 116 requisitos entregues em três fases sequenciais
concentram a descoberta de erro de modelagem no fim. A mitigação, dentro da ordem pedida,
está em "Fases de execução" — backend entregue por história na ordem P1→P3, não em bloco
único.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-erp-financeiro-synapse/
├── plan.md              # Este arquivo
├── spec.md              # Especificação (atualizada: FR-114/115/116 resolvidos)
├── research.md          # Fase 0 — decisões D-01…D-13 com alternativas
├── data-model.md        # Fase 1 — 19 tabelas, enums, regras, migrações
├── quickstart.md        # Fase 1 — como rodar e verificar
├── contracts/           # Fase 1 — contratos de API acordados
│   ├── README.md        #   convenções, erros, paginação, papéis
│   ├── lancamentos.md   #   lançamentos, recorrências, split, lote, anexos, importação
│   ├── consultas.md     #   dashboard, extrato, relatórios, busca, saldo
│   ├── cadastros.md     #   categorias, clientes, funcionários, serviços, centros, tags
│   └── plataforma.md    #   sessão, usuários, configurações, notificações, rotinas
├── checklists/
│   └── requirements.md  # Atualizado: 0 marcadores em aberto
└── tasks.md             # Fase 2 — gerado por /speckit-tasks, NÃO por este comando
```

### Source Code (repository root)

```text
backend/
├── api/index.py                    # entrypoint da função Vercel (expõe o app ASGI)
├── app/
│   ├── main.py                     # FastAPI, routers, handlers de erro
│   ├── config.py                   # pydantic-settings; nada de os.environ solto
│   ├── db.py                       # engine asyncpg, sessão por requisição
│   ├── seguranca/
│   │   ├── auth.py                 # valida JWT do Supabase, carrega o usuário
│   │   └── rbac.py                 # exige_papel("gestor") como dependência
│   ├── comum/
│   │   ├── erros.py                # formato único de erro (contracts/README.md)
│   │   ├── paginacao.py
│   │   ├── periodo.py              # "este_mes" → (inicio, fim, anterior)
│   │   ├── idempotencia.py         # Idempotency-Key
│   │   └── auditoria.py            # registra_auditoria(entidade, id, acao, diff)
│   ├── dominio/                    # ⬅ TODAS as RN-xx moram aqui (Princípio III)
│   │   ├── mundo.py                # RN-15
│   │   ├── status.py               # RN-03, RN-04, edição histórica
│   │   ├── saldo.py                # RN-05, RN-16
│   │   ├── recorrencia.py          # RF-15/17a, RN-05a, RN-07, clamp de dia do mês
│   │   ├── parcelamento.py         # RF-16, arredondamento na última parcela
│   │   ├── split.py                # RN-11
│   │   ├── cambio.py               # RN-12 + cache de cotação
│   │   ├── inadimplencia.py        # RN-10
│   │   ├── saude_caixa.py          # RF-46b
│   │   ├── arquivamento.py         # RN-06
│   │   └── lixeira.py              # RN-08
│   ├── lancamentos/                # rotas.py · servico.py · repositorio.py · esquemas.py
│   ├── recorrencias/
│   ├── categorias/
│   ├── clientes/
│   ├── funcionarios/
│   ├── cadastros/                  # servicos, centros_custo, tags
│   ├── extrato/                    # rotas.py · servico.py (só leitura)
│   ├── dashboard/
│   ├── relatorios/                 # + exportacao_csv.py, exportacao_pdf.py
│   ├── anexos/                     # Supabase Storage, URL assinada
│   ├── importacao/                 # csv.py, ofx.py, mapeamento.py
│   ├── notificacoes/
│   ├── configuracoes/
│   ├── usuarios/
│   ├── busca/
│   └── rotinas/                    # diaria.py, semanal.py, recuperacao.py
├── migracoes/                      # 001…008, SQL versionado (data-model.md §7)
├── tests/
│   ├── unidade/                    # dominio/ — os 6 alvos obrigatórios
│   ├── integracao/                 # endpoints contra Postgres real
│   └── contrato/                   # resposta × contracts/*.md
├── requirements.txt
└── vercel.json                     # runtime Python + crons

frontend/
├── app/
│   ├── layout.tsx                  # providers, tema, fontes
│   ├── entrar/page.tsx             # Supabase Auth
│   └── (app)/
│       ├── layout.tsx              # BarraLateral + CabecalhoGlobal
│       ├── page.tsx                # Dashboard
│       ├── lancamentos/page.tsx
│       ├── extrato/page.tsx
│       ├── categorias/page.tsx
│       ├── clientes/page.tsx · clientes/[id]/page.tsx
│       ├── funcionarios/page.tsx · funcionarios/[id]/page.tsx
│       ├── relatorios/page.tsx
│       └── configuracoes/page.tsx  # 7 seções
├── componentes/
│   ├── ui/                         # shadcn/ui, não editado à mão
│   ├── layout/                     # BarraLateral, SeletorMundo, SeletorPeriodo,
│   │                               # BuscaGlobal, SinoNotificacoes, AlternadorTema
│   ├── lancamentos/                # TabelaLancamentos, PainelDetalhe, FormLancamento,
│   │                               # BarraFiltros, DialogoSplit, TabelaLote, DialogoSerie
│   ├── dashboard/                  # um componente por card, resolvido por id
│   ├── graficos/                   # wrappers Recharts com tokens do tema
│   └── comum/                      # Moeda, DataBR, BadgeStatus, BadgeMundo,
│                                   # EstadoVazio, icones.tsx (SVGs do mockup)
├── lib/
│   ├── api.ts                      # cliente HTTP tipado + tratamento do erro padrão
│   ├── supabase.ts                 # cliente de autenticação (só login)
│   ├── formato.ts                  # BRL 1.234,56 · dd/mm/aaaa (RNF-03)
│   ├── estado-global.ts            # zustand: mundo + período, espelhados na URL
│   └── atalhos.ts                  # RNF-10
├── estilos/
│   ├── tokens.css                  # copiado do design system, sem reinterpretação
│   └── tema-escuro.css             # escala derivada (research.md D-12)
├── tests/
├── next.config.ts                  # rewrites /api/:path* → backend
└── package.json
```

**Structure Decision**: opção "aplicação web" do template — `backend/` e `frontend/`
separados no mesmo repositório. Dentro do backend, a subdivisão é **por domínio** e não por
tipo técnico, como o Princípio IV exige, com uma exceção deliberada: `app/dominio/` agrupa as
regras de negócio (`RN-xx`) por regra, não por tela, porque a mesma regra atende vários
domínios (o ciclo de status vale para lançamento, recorrência, cliente e rotina). Concentrar
ali é justamente o que impede a regra de se espalhar entre componentes, que é o que o
Princípio III proíbe.

Dois projetos Vercel apontam para este repositório com *root directory* diferente; o Next.js
faz proxy de `/api/*` para o backend (research.md D-02).

---

## Fases de execução

Ordem pedida pelo dono do projeto — banco, depois backend, depois frontend — mantida. O que
muda é o tamanho do passo dentro de cada fase.

### Fase A — Banco e fundação

**Liberada em 2026-07-30** — MCP do Supabase autenticado e testado (ver Pendências #1).

**Fase inteira sob a regra da Skill**: nenhuma migração, política ou índice desta fase é
escrito sem acionar `supabase-postgres-best-practices` antes.

1. `git init`, primeiro commit, repositório remoto (pré-requisito dos projetos Vercel).
2. Projeto Supabase: banco, Auth (e-mail+senha), bucket privado de anexos, backup gerenciado
   confirmado (`RNF-06`).
3. Migrações `001`…`008` conforme data-model.md §7 — **Skill acionada antes de cada uma**.
4. ~~**Antes do seed `008`**: confirmar o `mundo` de Dylan e Marcondes~~ — confirmado em
   2026-07-30: os dois são `digital` (data-model.md §3.6).
5. RLS de negação para as chaves públicas (research.md D-03a) — não é opcional; sem isso a
   chave que vive no navegador lê as tabelas financeiras direto. **Escrever a política com a
   Skill aberta**: RLS é onde erro silencioso custa caro.
6. Verificação: aplicar, consultar seeds, conferir que a chave `anon` recebe negação.

### Fase B — Backend, por história na ordem de prioridade

Cada bloco termina com testes rodando de verdade e documentação verificada (Princípios V e
VI), antes do bloco seguinte. **Todo `repositorio.py` — toda consulta que toca o Postgres do
Supabase — passa pela Skill `supabase-postgres-best-practices` antes de ser escrito**; vale
especialmente para B3, onde o Dashboard inteiro sai em uma requisição e o índice errado é a
diferença entre `SC-002` e um carregamento visível.

| Bloco | Histórias | Entrega |
|---|---|---|
| B0 | — | Esqueleto: app, config, db, erros, auth+RBAC, `/api/saude`, `/api/sessao`, deploy na Vercel funcionando ponta a ponta |
| B1 | 1, 2 | Lançamentos CRUD, mundo, tags, anexos, split, lote, lixeira, câmbio, saldo. Testes: `RN-02`, `RN-11`, `RN-12`, `RN-15` |
| B2 | 3 | Recorrência (inclusive retroativa e *clamp* de dia do mês), parcelamento, ciclo de status, rotina diária. Testes: `RN-03`, `RN-05`, `RN-05a`, `RN-07` |
| B3 | 4, 7 | Dashboard (uma requisição), Extrato, saúde do caixa, projeção |
| B4 | 5, 6 | Categorias especiais, clientes, funcionários, inadimplência, subcategorias espelho |
| B5 | 8 | Relatórios, exportação CSV/PDF |
| B6 | 9, 10 | Notificações, rotina semanal, usuários, configurações, auditoria, busca global, importação CSV/OFX, exportação completa |

**Por que não tudo de uma vez**: um erro de modelagem descoberto na tela do Dashboard, na
Fase C, custaria retrabalho nas três fases. Entregando por história, a primeira tela encontra
um backend já exercitado.

### Fase C — Frontend, fiel ao Claude Design

1. **Fundação visual**: tokens do design system copiados sem reinterpretação, escala escura
   derivada (**depende da aprovação de D-12**), fontes, shadcn/ui inicializado, SVGs de
   navegação extraídos do mockup.
2. **Casca**: barra lateral 246px, cabeçalho 64px, seletor de mundo, seletor de período,
   busca global, sino de notificações, alternador de tema, atalhos de teclado.
3. **Telas na mesma ordem P1→P3 do backend**, cada uma conferida contra o mockup e nos dois
   temas antes de ser declarada pronta (`SC-009` não admite tela que só funciona em um tema).

**Método de fidelidade**: cada tela é implementada lendo a seção correspondente de
`Synapse ERP Financeiro.dc.html` (2.386 linhas, estilos inline com as medidas exatas), não de
memória nem de aproximação. As 15 capturas em `Documentação/prints do UI Mockup/` servem de
conferência visual.

---

## Complexity Tracking

> Preenchido apenas quando a Constitution Check tem violação a justificar.

Sem violações a justificar. As duas pendências da seção Constitution Check são **decisões que
precisam de aceite do dono do projeto**, não complexidade adicionada:

| Item | Natureza | Status |
|---|---|---|
| `clientes` sem `mundo` (2ª exceção a `RN-15`) | Decisão de modelagem já tomada pelo dono do projeto | Aguarda reflexo no documento-mestre (task T021) |
| Escala de tema escuro derivada | Lacuna do design system, não do plano | ✅ **Aprovada em 2026-07-30** — derivada na implementação (research.md D-12) |

---

## Pendências abertas ao fim desta fase

| # | Pendência | Bloqueia |
|---|---|---|
| 1 | ✅ **Resolvida em 2026-07-30** — MCP do Supabase autenticado e **testado**: projeto `frpbowkoibdgigekrhor`, PostgreSQL 17.6, leitura de schema/extensões/buckets/migrações e execução de SQL funcionando. Banco ainda vazio (0 tabelas, 0 migrações, 0 buckets), como esperado | ~~Toda a Fase A~~ — liberada |
| 2 | ✅ **Resolvida em 2026-07-30** — Dylan e Marcondes são do mundo `digital` (data-model §3.6) | ~~Seed `008`~~ — liberado |
| 3 | ✅ **Resolvida em 2026-07-30** — haverá tema escuro; a escala é derivada na implementação, sem aprovação prévia no design system | ~~Fase C item 1~~ — liberada |
| 4 | Refletir no documento-mestre: `RN-15` (2ª exceção), `RF-101` (filtro de cliente derivado), `RN-03`/`RF-17` (`atrasado` só com efetivação manual), ausência de saldo inicial, e a troca de PostgreSQL na constituição já estar satisfeita | Princípio V — faz parte da Fase A (task T021) |
| 5 | Dados iniciais reais: mensalidades dos clientes ativos (a spec já lista os 9 serviços, as 9 categorias e os 2 funcionários) | Sistema nascer com histórico correto |

**Único bloqueio restante**: nenhum de decisão. A pendência 4 é trabalho (task T021) e a 5 é
dado que o dono do projeto fornece quando o sistema estiver de pé.
