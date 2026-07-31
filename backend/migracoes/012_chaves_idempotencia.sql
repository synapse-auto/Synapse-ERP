-- ─────────────────────────────────────────────────────────────────────────────
-- 012 — `chaves_idempotencia`: o cabeçalho `Idempotency-Key` deixa de viver na
--       memória do processo (contracts/README.md §Idempotência)
--
-- ## O que estava errado
--
-- `app/comum/idempotencia.py` guardava a chave num dicionário em memória e dizia isso
-- em voz alta: "protege contra clique duplo na mesma instância quente, e só". O
-- fechamento estava planejado para T056 e não aconteceu — o README do backend listava
-- isso como divergência aberta.
--
-- O caso que o mecanismo existe para cobrir é justamente o que a memória não cobre: a
-- Vercel repete a invocação depois de um timeout de rede, e a repetição normalmente cai
-- numa instância **nova**, com a memória vazia. Resultado: dois lançamentos iguais. Num
-- sistema financeiro isso é um valor contado em dobro no saldo, não um incômodo de
-- interface.
--
-- ## Desenho
--
-- Chave primária composta `(usuario_id, rota, chave)` — a mesma chave vinda de pessoas
-- diferentes, ou em endpoints diferentes, são operações diferentes. É a mesma tripla que
-- o módulo já usava em memória.
--
-- A PK também é a trava do caso concorrente: se duas invocações realmente correrem
-- juntas, a segunda falha no `insert` em vez de criar o lançamento duplicado. Falhar é
-- o comportamento certo aqui — o cliente repete e a essa altura a primeira já commitou.
--
-- `resposta` guarda o corpo devolvido na primeira vez, para a repetição receber
-- exatamente a mesma resposta em vez de um erro confuso.
--
-- ## Por que expira, e por que a faxina é da rotina diária
--
-- A janela que interessa é a de uma repetição de rede, medida em segundos — o módulo usa
-- 10 minutos. Guardar por mais tempo só acumula lixo. Como `importacoes`, esta é tabela
-- de estado descartável, não histórico financeiro: apagar linha aqui é o certo, e
-- `RN-08` não se aplica.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists chaves_idempotencia (
  usuario_id  uuid        not null references usuarios (id),
  rota        text        not null,
  chave       text        not null,
  resposta    jsonb       not null,
  criado_em   timestamptz not null default now(),
  expira_em   timestamptz not null default now() + interval '10 minutes',
  primary key (usuario_id, rota, chave)
);

comment on table chaves_idempotencia is
  'contracts/README.md §Idempotência. Estado TEMPORÁRIO: expira em minutos e é limpo pela '
  'rotina diária. Não é histórico financeiro — RN-08 não se aplica.';

comment on column chaves_idempotencia.resposta is
  'Corpo devolvido na primeira chamada. A repetição recebe isto, não um erro.';

-- Serve só à faxina da rotina diária.
create index if not exists chaves_idempotencia_expiradas_idx
  on chaves_idempotencia (expira_em);

-- ─────────────────────────────────────────────────────────────────────────────
-- Segurança: mesma negação das outras tabelas (D-03a, migração `006`).
-- RLS ligada **sem política** = ninguém passa pelas chaves públicas. O gatilho de evento
-- `ensure_rls` do projeto já liga RLS em tabela nova; o `alter` abaixo é explícito para
-- o arquivo não depender disso.
-- ─────────────────────────────────────────────────────────────────────────────
alter table chaves_idempotencia enable row level security;

revoke all on table chaves_idempotencia from anon, authenticated;
