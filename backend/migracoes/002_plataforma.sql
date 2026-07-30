-- 002_plataforma.sql
-- Tabelas de plataforma — data-model.md §3.1, §3.15, §3.17, §3.18, §3.19
-- Nenhuma delas carrega `mundo` (data-model §1 — exceções documentadas).
--
-- Tarefa: T010

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.1 usuarios
-- ─────────────────────────────────────────────────────────────────────────────
create table usuarios (
  id            uuid primary key,                                    -- IGUAL ao id do Supabase Auth
  nome          text not null,
  email         text not null unique,
  papel         papel_usuario not null default 'operador',            -- RF-02: padrão é o menor privilégio
  ativo         boolean not null default true,                        -- desativar, nunca excluir
  preferencias  jsonb not null default '{}'::jsonb,                   -- D-09: {tema, dashboard_cards:[{id,visivel,ordem}]}
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

comment on table  usuarios is 'RF-02. id vem do Supabase Auth — o backend não gera. Nunca excluído: ativo=false.';
comment on column usuarios.preferencias is 'FR-071/FR-109: tema e ordem/visibilidade dos cards do Dashboard.';

create trigger usuarios_atualizado_em before update on usuarios
  for each row execute function public.toca_atualizado_em();

-- O sistema garante ao menos um gestor ativo (data-model §3.1). A trava mora no
-- serviço (backend/app/usuarios) porque a mensagem de erro é de negócio e precisa
-- ser em PT-BR com `codigo`/`requisito` — contracts/README.md. O índice abaixo faz
-- a contagem de gestores ativos ser imediata.
create index usuarios_gestores_ativos_idx on usuarios (papel) where ativo and papel = 'gestor';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.15 configuracoes — materializa RNF-02 / FR-106 / Princípio VII
-- ─────────────────────────────────────────────────────────────────────────────
create table configuracoes (
  chave           text primary key,
  valor           jsonb not null,
  descricao       text not null,
  atualizado_por  uuid null references usuarios (id),
  atualizado_em   timestamptz not null default now()
);

comment on table configuracoes is
  'Princípio VII: rótulos, limites, prazos e multiplicadores vivem aqui, nunca no código. Seed em 007.';

create index configuracoes_atualizado_por_idx on configuracoes (atualizado_por);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.17 auditoria — nunca apagada, sem soft delete
-- ─────────────────────────────────────────────────────────────────────────────
create table auditoria (
  id           bigserial primary key,
  entidade     text not null,                                        -- nome da tabela
  entidade_id  uuid not null,
  acao         acao_auditoria not null,
  alteracoes   jsonb not null,                                       -- {campo: {de, para}} — só o que mudou
  usuario_id   uuid not null references usuarios (id),
  criado_em    timestamptz not null default now()
);

comment on table auditoria is
  'RN-08 / RF-03. Histórico financeiro é permanente: nunca apagada, não tem soft delete.';

-- A linha do tempo do painel de detalhe (FR-041, FR-103)
create index auditoria_entidade_idx on auditoria (entidade, entidade_id, criado_em desc);
-- Modo geral com filtro por autor (FR-103)
create index auditoria_usuario_idx on auditoria (usuario_id, criado_em desc);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.19 execucoes_rotina — idempotência e recuperação (D-08)
-- ─────────────────────────────────────────────────────────────────────────────
create table execucoes_rotina (
  nome                    text primary key,                          -- 'diaria' | 'semanal'
  ultima_execucao_em      timestamptz not null,
  ultima_data_processada  date not null,
  ultimo_resultado        jsonb not null
);

comment on table  execucoes_rotina is
  'D-08. Suporta idempotência e recuperação de dia perdido.';
comment on column execucoes_rotina.ultimo_resultado is
  'Princípio VI: o que a rotina de fato fez (quantos efetivados, quantos atrasados) — verificável, não afirmado.';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.18 cotacoes_cambio — cache de cotação (RN-12)
-- ─────────────────────────────────────────────────────────────────────────────
create table cotacoes_cambio (
  data       date not null,
  par        text not null,                                          -- 'USDBRL'
  taxa       numeric(14,6) not null check (taxa > 0),
  fonte      text not null,
  obtida_em  timestamptz not null default now(),
  primary key (data, par)
);

comment on table cotacoes_cambio is
  'RN-12: cache. A conversão usa a cotação da DATA DO LANÇAMENTO, não a de hoje.';
