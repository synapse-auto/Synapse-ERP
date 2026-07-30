-- 005_notificacoes.sql
-- Notificações — data-model.md §3.16
--
-- Tarefa: T013

create table notificacoes (
  id                  uuid primary key default gen_random_uuid(),
  usuario_id          uuid not null references usuarios (id),          -- uma linha por destinatário
  tipo                tipo_notificacao not null,
  titulo              text not null,
  corpo               text not null,
  mundo               mundo null,                                      -- nulo = consolidada (RF-101)
  lancamento_id       uuid null references lancamentos (id),
  cliente_id          uuid null references clientes (id),
  chave_deduplicacao  text not null,
  lida_em             timestamptz null,
  criado_em           timestamptz not null default now(),

  -- A rotina diária pode rodar mais de uma vez no mesmo dia (D-08). Sem esta chave o
  -- mesmo "vence em 3 dias" viraria três notificações.
  constraint notificacoes_dedup_uk unique (usuario_id, chave_deduplicacao)
);

comment on table  notificacoes is
  'FR-096..FR-100. Uma linha por destinatário. Alertas respeitam o mundo ativo (RF-101).';
comment on column notificacoes.chave_deduplicacao is
  'Formatos: vencimento:{lancamento_id}:{dias} · inadimplencia:{cliente_id}:{aaaa-mm-dd} · resumo_semanal:{aaaa-Www} · caixa_baixo:{mundo}:{aaaa-Www}';

-- Contador de não lidas e painel do sino (FR-100) — índice parcial, porque a consulta
-- sempre filtra "não lidas" (Skill: query-partial-indexes)
create index notificacoes_nao_lidas_idx on notificacoes (usuario_id, criado_em desc)
  where lida_em is null;
-- Painel completo, lidas e não lidas
create index notificacoes_usuario_idx on notificacoes (usuario_id, criado_em desc);
-- FKs indexadas para clicar e ir ao item
create index notificacoes_lancamento_idx on notificacoes (lancamento_id) where lancamento_id is not null;
create index notificacoes_cliente_idx    on notificacoes (cliente_id)    where cliente_id is not null;
