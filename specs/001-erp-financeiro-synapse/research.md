# Phase 0 — Pesquisa e Decisões Técnicas

**Feature**: Plataforma Financeira Synapse (ERP interno v1)
**Data**: 2026-07-29
**Spec**: [spec.md](./spec.md) · **Plano**: [plan.md](./plan.md)

Todas as decisões abaixo foram tomadas contra os Princípios I–VII de
[`.specify/memory/constitution.md`](../../.specify/memory/constitution.md). O Princípio II
("Não reinventar a roda") exige registrar **o que foi pesquisado, o que foi escolhido e por
quê** — é o que esta página faz.

---

## 0. Resumo das mudanças de rumo desta fase

| Item | Pedido inicial | Onde ficou | Motivo |
|---|---|---|---|
| Banco | SQLite | **Supabase (PostgreSQL)** | SQLite não sobrevive na Vercel; decisão do dono do projeto em 2026-07-29 |
| Hospedagem | Front e back na Vercel | **Mantida** — 2 projetos Vercel no mesmo repositório | Ver D-02 |
| `FR-114` saldo inicial | em aberto | **Só histórico retroativo** | Decisão do dono do projeto |
| `FR-115` efetivação de receita de cliente | em aberto | **Sem regra especial** — vale o checkbox de `RF-17`/`RN-04` | Decisão do dono do projeto |
| `FR-116` cliente nos dois mundos | em aberto | **Cadastro único, sem mundo** | Decisão do dono do projeto |

---

## 1. Banco de dados

### D-01 — Supabase (PostgreSQL) em vez de SQLite

**Decisão**: PostgreSQL gerenciado pelo Supabase.

**Por que o SQLite foi descartado**: a Vercel roda o backend em funções sem disco
permanente — o sistema de arquivos é recriado a cada requisição e descartado no fim. Um
arquivo `.db` gravado ali desaparece. Não é limitação de configuração; é como a plataforma
funciona. Todo lançamento salvo se perderia.

**Alternativas consideradas**:

| Opção | Veredito |
|---|---|
| SQLite em arquivo na Vercel | **Impossível** — disco efêmero |
| Turso / libSQL (SQLite hospedado) | Viável tecnicamente; recusado pelo dono do projeto por complexidade |
| Backend fora da Vercel com disco (Fly.io, Railway) | Viável; recusado — sai da Vercel |
| Neon (Postgres puro) | Viável; resolve só o banco |
| **Supabase (Postgres + Auth + Storage)** | **Escolhido** |

**Rationale**: além do banco, o Supabase resolve de graça dois outros problemas que a
Vercel também não resolve sozinha — **login** (Auth) e **anexos** (Storage). Um serviço em
vez de três. E PostgreSQL é exatamente o que a seção "Padrões Técnicos Obrigatórios" da
constituição já exige, então a mudança **remove** uma divergência em vez de criar uma.

**Pendência de execução**: a configuração do MCP do Supabase será enviada depois. Até
chegar, as migrações são escritas como SQL versionado em `backend/migracoes/` mas **não
podem ser aplicadas**. É o único bloqueio real da Fase A.

### D-01a — Migrações em SQL puro, versionado

**Decisão**: arquivos `.sql` numerados (`001_esquema.sql`, `002_seed.sql`, …), aplicados
via CLI do Supabase.

**Alternativas**: Alembic (autogenerate a partir de modelos SQLAlchemy) — poderoso, mas
para um esquema que nasce inteiro de uma vez e muda pouco, adiciona uma camada que não se
paga (Princípio I). SQL puro também mantém o esquema legível para quem abrir o painel do
Supabase.

### D-01b — SQLAlchemy Core, não ORM completo

**Decisão**: SQLAlchemy 2.x em modo Core/`select()` com tabelas declaradas, sem
relacionamentos lazy-loaded.

**Rationale**: as telas mais caras (Dashboard, Extrato, DRE, variação mensal) são
agregações — `GROUP BY`, janelas, saldo acumulado. ORM atrapalha nesses casos e esconde
N+1. Core dá SQL previsível com tipagem e proteção contra injeção. `asyncpg` como driver.

---

## 2. Hospedagem e topologia

### D-02 — Monorepo, dois projetos Vercel, front faz proxy do back

**Decisão**:

- Um repositório com `frontend/` (Next.js) e `backend/` (FastAPI).
- Dois projetos na Vercel apontando para o mesmo repositório, cada um com seu *root
  directory*.
- O Next.js declara `rewrites` mandando `/api/:path*` para a URL do backend.

**Consequência boa**: para o navegador, tudo vem do mesmo domínio. Sem CORS, sem problema
de cookie cross-site, sem chave de API exposta no cliente.

**Alternativas consideradas**:

| Opção | Veredito |
|---|---|
| Um único projeto Vercel com `api/index.py` ao lado do Next.js | Funciona, mas o roteamento entre o `app/api` do Next e a função Python na raiz é uma fonte conhecida de conflito. Não vale a economia de um projeto. |
| Dois domínios (`app.` e `api.`) com CORS | Mais peças móveis: CORS, cookie de domínio pai, preflight. Rejeitado. |
| Backend em outro provedor | Contraria o pedido explícito de manter tudo na Vercel. |

### D-02a — FastAPI na Vercel: limites aceitos de olhos abertos

O runtime Python da Vercel roda ASGI direto, então FastAPI funciona sem adaptador. Mas:

- **Cold start**: primeira requisição depois de um tempo parado leva alguns segundos. Para
  3 usuários internos, aceitável. O frontend mostra estado de carregamento em vez de
  parecer travado.
- **Duração máxima da função**: limitada, e menor no plano gratuito. Impacto real em duas
  operações: geração de recorrência retroativa longa (o *edge case* de 3 anos da spec) e
  importação de CSV grande.
  **Mitigação**: as duas operam em **lotes com retomada** — o endpoint processa um pedaço,
  devolve um cursor, o frontend chama de novo mostrando progresso. Sem worker, sem fila.
- **Tamanho do pacote**: por isso `pandas` está fora (ver D-08).
- **Sem processo de fundo**: por isso a rotina diária é um cron chamando um endpoint
  (ver D-06).

### D-02b — Sem `git init` ainda

O diretório não é um repositório git. `git init` + primeiro commit é a tarefa zero da
Fase A — os dois projetos Vercel dependem de um repositório remoto para existir.

---

## 3. Login e permissões

### D-03 — Supabase Auth para identidade, RBAC no FastAPI

**Decisão**:

- **Quem é você**: Supabase Auth (e-mail + senha). O frontend recebe um JWT.
- **O que você pode**: tabela `usuarios` com coluna `papel` (`gestor` | `operador`). Toda
  rota do FastAPI declara o papel exigido por uma dependência (`exige_papel("gestor")`).
- O FastAPI valida o JWT em cada requisição e carrega o usuário e o papel.

**Rationale**: Princípio II — escrever autenticação à mão (hash de senha, recuperação,
expiração, rotação de token) é reinventar a roda mais arriscada que existe. O Supabase Auth
já resolve. O que **não** se delega é a autorização: `RF-02` e a constituição exigem RBAC
declarado no endpoint, verificável e testável — isso mora no backend.

**A verificar na implementação**: o Supabase migrou para JWT assimétrico (JWKS) mantendo o
segredo compartilhado legado. A validação deve usar o modo que o projeto estiver
configurado — conferir no painel antes de escrever o validador, não assumir.

### D-03a — RLS ligada como rede de segurança, não como mecanismo principal

**Decisão**: o backend acessa o banco com credencial de serviço; a autorização real está
no FastAPI. Mas o RLS fica **ligado com política de negação** para as chaves públicas
(`anon`, `authenticated`).

**Rationale**: sem isso, a chave pública do Supabase — que por natureza vive no navegador —
daria leitura direta às tabelas financeiras, contornando todo o RBAC. Duas linhas de SQL
por tabela fecham a porta. Não é sobre-engenharia; é fechar um buraco que a arquitetura
escolhida abre.

**Consequência**: o frontend **nunca** consulta o banco pelo SDK do Supabase. Só o backend.
O SDK no cliente serve apenas ao login. Isso também é o que o Princípio IV manda ("componente
de tela MUST NOT falar direto com o banco").

---

## 4. Modelo de dados — decisões que a spec deixou abertas

### D-04 — Cliente não tem mundo (resolve `FR-116`, cria consequência em `RF-101`)

**Decisão do dono do projeto**: cadastro único de cliente, sem campo `mundo`. Quem carrega
o mundo é cada lançamento dele.

**Consequência que precisa ser dita**: `RF-101` manda a lista de Clientes filtrar pelo
mundo ativo. Sem `mundo` no cliente, esse filtro deixa de ser uma coluna e passa a ser
**derivado**: "clientes com movimentação (efetivada ou programada) no mundo ativo". Quem
não tem nenhum lançamento ainda aparece nos três estados do seletor — não tem como saber a
que mundo pertence.

**Efeito colateral positivo**: `RF-71` (ranking de clientes) e o perfil do cliente passam a
mostrar naturalmente a quebra por mundo, o que antes seria impossível com dois cadastros
separados.

**Onde `RN-15` fica**: ganha uma segunda exceção documentada, ao lado de categorias.
Precisa ser refletido no documento-mestre (Princípio V).

### D-05 — `atrasado` só existe quando a efetivação automática está desligada (resolve `FR-115`)

**Correção registrada**: a spec tratou isso como contradição entre `RF-17` e `RN-03` e abriu
um `NEEDS CLARIFICATION`. Não havia contradição — `RF-17`/`RN-04` já definem o mecanismo, e
ele é por lançamento, não por categoria.

**Decisão**: nenhuma regra especial para a categoria Clientes. O ciclo é:

```
efetivar_automaticamente = true   → programado --(chega a data)--> efetivado
efetivar_automaticamente = false  → programado --(chega a data)--> pendente
                                              --(passa do vencimento)--> atrasado
                                              --(1 clique)--> efetivado
qualquer um                       → cancelado (preserva histórico)
```

`atrasado` é alcançável **somente** por lançamentos com o checkbox desligado — os
automáticos se efetivam na data e nunca vencem. Logo o alerta de inadimplência (`RF-63`,
`RN-10`) depende de a mensalidade do cliente ter o checkbox **desligado**.

**Como isso não vira pegadinha**: o valor padrão do checkbox para receita de cliente vira
uma **chave de configuração** (`efetivacao_automatica_padrao_receita_cliente`), não um
literal no código. O dono do projeto liga ou desliga na tela de Configurações e escolhe
entre "caixa mais rápido de operar" e "alerta de inadimplência funcionando". Atende
`RNF-02` e o Princípio VII, e deixa a escolha onde ela pertence.

### D-06 — Saldo inicial: não existe (resolve `FR-114`)

**Decisão do dono do projeto**: sem campo de saldo inicial e sem lançamento de abertura. O
saldo de cada mundo é integralmente o resultado dos lançamentos `efetivado`.

**Consequência que precisa ser dita**: o saldo só bate com o extrato bancário real depois
que o histórico estiver completo no sistema — via recorrência retroativa (`RN-05a`) e
importação de CSV/OFX (`RF-21`). Até lá o card "Saldo atual" mostra um número menor que a
realidade, e o semáforo de saúde do caixa (`RF-46b`) fica pessimista.

**Mitigação sem inventar escopo**: nenhuma. Isso é uma escolha consciente, não um bug. Se
depois de carregar o histórico o número não fechar, a saída é um lançamento de ajuste
comum — o que o sistema já permite sem nenhum recurso novo.

### D-07 — Subcategoria das categorias especiais espelha cliente/funcionário

**Decisão**: `subcategorias` ganha `cliente_id` e `funcionario_id` (nulos, exclusivos).
Quando um cliente ou funcionário é criado, o serviço de domínio cria a subcategoria
correspondente na categoria especial. Arquivar um arquiva a outra.

**Alternativa considerada**: não criar subcategoria e pôr `cliente_id`/`funcionario_id`
direto em `lancamentos`. Rejeitada: obrigaria toda consulta de agrupamento (DRE por
subcategoria, variação mensal, filtros, exportação) a ter dois caminhos — "se a categoria é
especial, agrupe por cliente; senão, por subcategoria". Isso é lógica duplicada em muitos
lugares, o que o Princípio III proíbe. Espelhar custa uma função de sincronismo em um lugar
só e deixa **todo** o resto do sistema com um caminho único.

**Onde o sincronismo mora**: no serviço de domínio, não em trigger de banco — precisa ser
testável (Princípio VI).

### D-08 — Status materializado + rotina diária idempotente + recuperação na leitura

**Decisão**: `status` é coluna gravada, não calculada em toda leitura. Uma rotina diária
atualiza o que venceu.

**Alternativas consideradas**:

| Opção | Veredito |
|---|---|
| Status 100% calculado na leitura | Tentador (sempre correto, zero cron), mas impede registrar *quando* e *por quem* algo foi efetivado, quebra a auditoria (`RN-08`) e força recalcular em toda consulta de saldo |
| Status 100% gravado por cron | Simples, mas se o cron falhar um dia o sistema mente sem avisar |
| **Gravado + rotina diária + recuperação na leitura** | **Escolhido** |

**Como funciona**: a rotina diária (`POST /api/jobs/diario`) executa, em ordem:
materializa ocorrências de recorrência → efetiva os `programado` vencidos com checkbox
ligado → move para `pendente` os vencidos com checkbox desligado → move para `atrasado` os
`pendente` que passaram do vencimento → reavalia inadimplência de clientes → gera
notificações.

**Idempotência**: a rotina registra a data da última execução bem-sucedida e cada passo é
escrito como "traga o estado até a data de hoje", não como "avance um dia". Rodar duas
vezes no mesmo dia não duplica nada. Isso é obrigatório porque a Vercel pode repetir a
invocação.

**Recuperação na leitura**: se a rotina não rodou hoje, a primeira requisição de leitura a
dispara antes de responder. Um cron perdido não vira dado errado na tela.

**Reavaliação retroativa**: mudar a tolerância de inadimplência nas Configurações reavalia
os clientes já marcados na hora (*edge case* da spec), não só na próxima execução.

### D-09 — Preferências do usuário em `jsonb`, não em tabela

**Decisão**: tema e a ordem/visibilidade dos cards do Dashboard (`FR-071`) vivem em
`usuarios.preferencias jsonb`.

**Rationale**: Princípio I. São dados que só o próprio usuário lê, nunca entram em
`JOIN`, nunca são agregados e não têm integridade referencial a proteger. Uma tabela
`dashboard_cards` com ordem e visibilidade seria três tabelas e um CRUD para guardar o que
é, na prática, uma preferência. O catálogo de cards disponíveis, sim, é configuração
compartilhada (`configuracoes.dashboard_cards_disponiveis`) — porque aí o Princípio VII se
aplica.

---

## 5. Bibliotecas — o que foi pesquisado e escolhido

### Backend (Python 3.12)

| Necessidade | Escolha | Alternativas descartadas |
|---|---|---|
| API + OpenAPI automático | **FastAPI** | Pedido do dono do projeto; `/docs` já satisfaz o Princípio IV |
| Acesso a dados | **SQLAlchemy 2 Core + asyncpg** | ORM completo (esconde agregação), `psycopg` síncrono |
| Validação / serialização | **Pydantic v2** | vem com FastAPI |
| Configuração por ambiente | **pydantic-settings** | `os.environ` solto viola Princípio VII |
| Recorrência de datas | **python-dateutil (`rrule`)** | Escrever calendário à mão. Ver ressalva abaixo |
| OFX | **ofxparse** | Parser próprio para um formato XML/SGML legado — inviável |
| CSV | **`csv` da biblioteca padrão** | `pandas` — pesa dezenas de MB e conta contra o limite de tamanho da função Vercel (D-02a). Para mapear colunas de um CSV, não paga |
| PDF dos relatórios | **reportlab** | `weasyprint` (depende de bibliotecas de sistema que não existem no runtime da Vercel); gerar no navegador (perde o layout formatado que `RF-74` pede) |
| JWT | **PyJWT** com JWKS | validação manual de assinatura |
| Testes | **pytest + pytest-asyncio + httpx** | — |

**Ressalva sobre `dateutil.rrule`**: ele **não** resolve o *edge case* "mensal todo dia 31
em fevereiro" — a regra `bymonthday=31` simplesmente pula os meses sem dia 31, em vez de
cair no último dia. A spec exige cair no último dia do mês. Então: `rrule` gera a sequência
de meses e uma função própria de *clamp* (`min(dia_desejado, último_dia_do_mês)`) fixa o
dia. Essa função é um dos alvos de teste automatizado obrigatório.

### Frontend (Next.js 15, App Router, TypeScript)

| Necessidade | Escolha | Alternativas descartadas |
|---|---|---|
| Componentes | **shadcn/ui** | Exigido pela constituição |
| Gráficos | **Recharts** via `chart` do shadcn/ui | Chart.js, Nivo, Tremor — o shadcn já embala Recharts com os tokens do tema, o que resolve `RNF-09` (claro/escuro) de graça |
| Tabelas | **TanStack Table** via `data-table` do shadcn | AG Grid (pesado, licença), tabela própria |
| Dados do servidor | **TanStack Query** | `fetch` solto em `useEffect` — perde cache, revalidação e estado de carregamento |
| Formulários | **react-hook-form + zod** | padrão do shadcn |
| Estado global (mundo, período) | **zustand** com persistência | Context puro re-renderiza a árvore inteira a cada troca de mundo |
| Ícones | **Lucide** + os SVGs do mockup | ver D-11 |
| Datas | **date-fns** com locale `pt-BR` | Moment (aposentado), Day.js (menos completo em formatação pt-BR) |
| Moeda e data | `Intl.NumberFormat`/`DateTimeFormat` nativos | biblioteca de formatação — `RNF-03` (1.234,56 e dd/mm/aaaa) é nativo |
| Virtualização | **TanStack Virtual**, só se medir necessidade | Paginação no servidor resolve `RNF-07` no volume real (`SC-007`: 5.000 lançamentos). Virtualizar antes de medir é abstração sem dois usos (Princípio I) |
| Testes | **Vitest + Testing Library** | — |

### Cotação USD→BRL (`RN-12`)

**Escolha**: AwesomeAPI como fonte primária (tem cotação por data histórica, o que
`RN-12` exige para lançamento com data passada), PTAX do Banco Central como alternativa,
entrada manual como último recurso — exatamente o que a spec já definiu em *Assumptions*.

**Cache obrigatório**: tabela `cotacoes_cambio` com chave `(data, par)`. Sem ela, salvar 30
lançamentos históricos em dólar são 30 chamadas externas — e o *edge case* "fonte
indisponível" passa a acontecer no meio de uma importação.

---

## 6. Interface — o que veio do Claude Design

**Fonte**: projeto `Synapse ERP Financeiro`
(`f5d2a73f-43fc-4d92-b46a-b3ef8d637164`) — 2.386 linhas de HTML navegável + o
`Synapse Design System`.

### D-10 — Os tokens do design system entram como CSS, não como reinterpretação

**Decisão**: `colors_and_type.css` do design system é copiado para
`frontend/estilos/tokens.css` e o Tailwind é configurado para consumir **essas** variáveis.
Nenhuma cor, raio, sombra ou tamanho de fonte é redigitado.

**O que isso trava**: roxo primário `#8B6CF0`, tinta quase-preta com fundo roxo (`#14102B`,
nunca `#000`), sombras com tom roxo (não cinza-neutro), escada de raios
(10px campo / 14–20px card / 28px superfície / 999px pílula), grade de 4pt, easing
`cubic-bezier(0.22, 1, 0.36, 1)`, durações 140/220/360ms.

**Medidas extraídas do mockup**: sidebar 246px fixa · header 64px · fundo da aplicação
`#F7F5FB` · sidebar `#FBFAFE` · item de menu ativo `#EDE6FD` com texto `#4F3299` · raio
9px nos itens de menu · Plus Jakarta Sans 13,5px/700 no menu.

### D-11 — Ícones: SVGs do mockup na navegação, Lucide no resto

**Constatação**: o design system manda usar Lucide, mas o mockup **não** usa Lucide — usa
SVGs desenhados à mão (o ícone de Lançamentos são duas setas opostas; o de Extrato é um
recibo com borda serrilhada). São mais expressivos que os equivalentes Lucide.

**Decisão**: extrair os 7 SVGs de navegação do mockup para
`frontend/componentes/comum/icones.tsx` e usar Lucide em todo o resto. Fidelidade onde ela
é visível, biblioteca pronta onde não faz diferença.

### D-12 — Tokens de tema escuro precisam ser derivados (lacuna do design system)

**Constatação**: `RNF-09`/`FR-109`/`SC-009` exigem tema escuro em 100% das telas, gráficos
e tabelas. **O design system não define nenhum token escuro** e o mockup só existe em
claro. É uma lacuna real, não um detalhe.

**Decisão**: derivar a escala escura das regras que o design system já enuncia, em vez de
inventar:

- Fundo base = `--ink-900` (`#14102B`), nunca `#000` — o design system proíbe preto puro.
- Superfícies elevadas sobem a escala de tinta (`--ink-800`, `--ink-700`), sem sombra
  colorida: sombra roxa sobre fundo escuro não se vê. Elevação no escuro = diferença de
  luminosidade + hairline.
- Roxo de ação sobe um passo (`--purple-400` `#A78BFA`) para manter contraste de texto
  sobre fundo escuro; o hover **escurece** (regra do design system), então no escuro o
  hover vai para `--purple-500`.
- Semânticos (verde receita, vermelho despesa, âmbar, azul) são reajustados para contraste
  mínimo AA sobre `#14102B` — os valores claros não passam.
- Entregue como bloco `[data-theme="dark"]` sobrescrevendo as mesmas variáveis, para que
  nenhum componente precise saber que existe tema.

**Aprovado pelo dono do projeto em 2026-07-30**: haverá tema escuro mesmo sem ele existir no
design system, e a escala é derivada **na hora da implementação**, pelas cinco regras acima.
Não volta ao projeto do Claude Design para aprovação prévia — a Fase C está liberada.

Consequência aceita: o tema escuro nasce como extensão da implementação, não como parte
versionada do design system. A garantia de `SC-009` passa a ser conferência visual tela a
tela (task T202), não um token aprovado na origem.

### D-13 — Referências externas consultadas (Princípio II)

| Referência | O que foi aproveitado |
|---|---|
| **Firefly III** | Modelagem de recorrência (regra separada das ocorrências geradas) e a ideia de conta única com saldo derivado |
| **Akaunting** | Dashboard de *widgets* mostráveis/ocultáveis/reordenáveis — a origem declarada de `RF-48` |
| **ERPNext** | Padrão de "documento cancelado preserva histórico" (`RN-03`) e de auditoria em tabela separada |
| **Google Agenda** | "só este / este e os futuros" na edição de série (`RN-07`) — o comportamento que o usuário já conhece |
| **claude.ai** | Estrutura da barra lateral com Configurações e perfil no rodapé (`RNF-04`), padrão da casa |

---

## 7. Sequência de execução e o que ela exige

O plano executa em três fases, na ordem pedida: banco → backend → frontend. Duas observações
honestas sobre isso:

**A Fase A está bloqueada** até a configuração do MCP do Supabase chegar. O SQL das
migrações pode ser escrito antes; aplicar, não.

**Frontend inteiramente depois do backend inteiro é um risco**, e vale dizer: um erro de
modelagem descoberto na tela do Dashboard, no fim da Fase C, custa retrabalho nas três
fases. A mitigação dentro da ordem pedida é entregar o backend **por história de usuário na
ordem de prioridade** (P1 → P2 → P3), com os testes de `RN` críticos passando a cada bloco,
em vez de todos os 116 requisitos de uma vez. Assim a primeira tela encontra um backend já
exercitado. A ordem pedida é mantida — muda só o tamanho do passo.

---

## 8. Itens sem pendência de pesquisa

Nenhum `NEEDS CLARIFICATION` permanece. Os três da spec foram respondidos pelo dono do
projeto em 2026-07-29 e estão registrados em D-04, D-05 e D-06; a spec e o checklist foram
atualizados na mesma entrega.
