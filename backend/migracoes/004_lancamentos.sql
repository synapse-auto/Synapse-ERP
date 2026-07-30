-- 004_lancamentos.sql
-- Núcleo financeiro — data-model.md §3.10 a §3.14
-- parcelamentos, recorrencias, lancamentos, lancamentos_tags, anexos,
-- view lancamentos_ativos, índices e o gatilho de imutabilidade de `mundo` (RN-15).
--
-- Tarefa: T012

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.14 parcelamentos — valor FECHADO dividido (RF-16), não regra que gera indefinidamente
-- ─────────────────────────────────────────────────────────────────────────────
create table parcelamentos (
  id              uuid primary key default gen_random_uuid(),
  mundo           mundo not null,                                     -- RN-15 — imutável
  descricao       text not null,
  valor_total     numeric(14,2) not null check (valor_total > 0),
  total_parcelas  smallint not null check (total_parcelas > 1),
  criado_por      uuid not null references usuarios (id),
  criado_em       timestamptz not null default now()
);

comment on table parcelamentos is
  'RF-16. sum(parcelas) = valor_total, com a diferença de arredondamento absorvida na última parcela (dominio/parcelamento.py).';

create index parcelamentos_criado_por_idx on parcelamentos (criado_por);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.13 recorrencias
-- ─────────────────────────────────────────────────────────────────────────────
create table recorrencias (
  id                        uuid primary key default gen_random_uuid(),
  mundo                     mundo not null,                           -- RN-15 — imutável
  tipo                      tipo_lancamento not null,
  descricao                 text not null,
  valor                     numeric(14,2) not null check (valor > 0),
  categoria_id              uuid not null references categorias (id),
  subcategoria_id           uuid null references subcategorias (id),
  servico_id                uuid null references servicos (id),
  centro_custo_id           uuid null references centros_custo (id),
  frequencia                frequencia_recorrencia not null,           -- RF-15
  intervalo_dias            smallint null check (intervalo_dias is null or intervalo_dias > 0),
  dia_vencimento            smallint null,
  mes_vencimento            smallint null check (mes_vencimento is null or mes_vencimento between 1 and 12),
  data_inicio               date not null,                             -- PODE ser retroativa (RF-17a, RN-05a)
  data_fim                  date null,
  total_parcelas            smallint null check (total_parcelas is null or total_parcelas > 0),
  efetivar_automaticamente  boolean not null default true,             -- herdado pelas ocorrências
  gerada_ate                date null,                                 -- até onde já materializou (D-08)
  cliente_id                uuid null references clientes (id),        -- origem: mensalidade (RF-62)
  funcionario_id            uuid null references funcionarios (id),    -- origem: folha (RF-67)
  ativa                     boolean not null default true,
  criado_por                uuid not null references usuarios (id),
  criado_em                 timestamptz not null default now(),
  atualizado_em             timestamptz not null default now(),
  excluido_em               timestamptz null,
  excluido_por              uuid null references usuarios (id),

  -- data_fim e total_parcelas são mutuamente exclusivos (data-model §3.13)
  constraint recorrencias_fim_exclusivo
    check (not (data_fim is not null and total_parcelas is not null)),
  constraint recorrencias_fim_depois_do_inicio
    check (data_fim is null or data_fim >= data_inicio),
  -- intervalo_dias só quando frequencia='dias', e obrigatório nesse caso
  constraint recorrencias_intervalo_so_em_dias
    check ((frequencia = 'dias') = (intervalo_dias is not null)),
  -- mes_vencimento só quando frequencia='anual'
  constraint recorrencias_mes_so_em_anual
    check (frequencia = 'anual' or mes_vencimento is null),
  -- dia_vencimento: 1..31 no mensal/anual, 1..7 no semanal, ausente em 'dias'
  constraint recorrencias_dia_vencimento_coerente
    check (
      case frequencia
        when 'semanal' then dia_vencimento between 1 and 7
        when 'mensal'  then dia_vencimento between 1 and 31
        when 'anual'   then dia_vencimento between 1 and 31
        when 'dias'    then dia_vencimento is null
      end
    ),
  -- uma recorrência nasce de um cliente OU de um funcionário, nunca dos dois
  constraint recorrencias_uma_origem_no_maximo
    check (not (cliente_id is not null and funcionario_id is not null))
);

comment on table  recorrencias is
  'RF-15/RF-17a. Ocorrências entre data_inicio retroativa e hoje nascem efetivado (RN-05a), independente de efetivar_automaticamente — o passado já aconteceu.';
comment on column recorrencias.gerada_ate is
  'D-08: é o que torna a materialização idempotente. Gerar = avançar de gerada_ate até o horizonte, nunca recriar tudo.';

-- FKs indexadas (Skill: schema-foreign-key-indexes)
create index recorrencias_categoria_idx     on recorrencias (categoria_id);
create index recorrencias_subcategoria_idx  on recorrencias (subcategoria_id)  where subcategoria_id is not null;
create index recorrencias_servico_idx       on recorrencias (servico_id)       where servico_id is not null;
create index recorrencias_centro_custo_idx  on recorrencias (centro_custo_id)  where centro_custo_id is not null;
create index recorrencias_cliente_idx       on recorrencias (cliente_id)       where cliente_id is not null;
create index recorrencias_funcionario_idx   on recorrencias (funcionario_id)   where funcionario_id is not null;
create index recorrencias_criado_por_idx    on recorrencias (criado_por);
-- A rotina diária varre só as ativas que ainda têm o que gerar (D-08)
create index recorrencias_a_gerar_idx on recorrencias (gerada_ate)
  where ativa and excluido_em is null;

create trigger recorrencias_atualizado_em before update on recorrencias
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.10 lancamentos — entidade central
-- ─────────────────────────────────────────────────────────────────────────────
create table lancamentos (
  id                        uuid primary key default gen_random_uuid(),
  mundo                     mundo not null,                            -- RN-15 — IMUTÁVEL (gatilho abaixo)
  tipo                      tipo_lancamento not null,
  descricao                 text not null,
  valor                     numeric(14,2) not null check (valor > 0),   -- RN-02: sempre positivo, o sinal vem do tipo
  data                      date not null,                             -- RN-09: data única, quando o dinheiro se move
  status                    status_lancamento not null,                 -- RN-03
  categoria_id              uuid not null references categorias (id),   -- RN-01
  subcategoria_id           uuid null references subcategorias (id),    -- obrigatória se a categoria é especial (RN-01)
  servico_id                uuid null references servicos (id),
  centro_custo_id           uuid null references centros_custo (id),    -- RN-13: ausência = "geral"
  observacoes               text null,
  efetivar_automaticamente  boolean not null default true,              -- RF-17, RN-04
  efetivado_em              timestamptz null,
  efetivado_por             uuid null references usuarios (id),          -- nulo se foi a rotina automática
  moeda_origem              moeda not null default 'BRL',               -- RN-12
  valor_origem              numeric(14,2) null check (valor_origem is null or valor_origem > 0),
  cotacao                   numeric(14,6) null check (cotacao is null or cotacao > 0),
  cotacao_data              date null,
  cotacao_manual            boolean not null default false,
  recorrencia_id            uuid null references recorrencias (id),
  parcelamento_id           uuid null references parcelamentos (id),
  parcela_numero            smallint null check (parcela_numero is null or parcela_numero > 0),
  parcela_total             smallint null check (parcela_total is null or parcela_total > 0),
  lancamento_pai_id         uuid null references lancamentos (id),       -- split (RF-13a)
  versao                    integer not null default 1,                 -- data-model §5.6 (edição concorrente)
  criado_por                uuid not null references usuarios (id),      -- RF-03
  criado_em                 timestamptz not null default now(),
  atualizado_por            uuid null references usuarios (id),
  atualizado_em             timestamptz not null default now(),
  excluido_em               timestamptz null,                            -- soft delete (RN-08)
  excluido_por              uuid null references usuarios (id),

  -- RN-12: USD exige os três campos de conversão; BRL exige os três nulos
  constraint lancamentos_cambio_coerente
    check (
      case moeda_origem
        when 'USD' then valor_origem is not null and cotacao is not null and cotacao_data is not null
        when 'BRL' then valor_origem is null     and cotacao is null     and cotacao_data is null
      end
    ),
  -- parcela_numero e parcela_total juntos, ou ambos nulos; numero <= total
  constraint lancamentos_parcela_par_completo
    check ((parcela_numero is null) = (parcela_total is null)),
  constraint lancamentos_parcela_numero_no_limite
    check (parcela_numero is null or parcela_numero <= parcela_total),
  -- split não aponta para si mesmo
  constraint lancamentos_pai_nao_e_ele_mesmo
    check (lancamento_pai_id is distinct from id),
  -- soft delete: quem e quando andam juntos
  constraint lancamentos_exclusao_completa
    check ((excluido_em is null) = (excluido_por is null))
);

comment on table  lancamentos is
  'Entidade central. RN-02 valor sempre positivo. RN-09 data única. Só `efetivado` conta no realizado (RN-05).';
comment on column lancamentos.mundo is
  'RN-15: obrigatório e IMUTÁVEL. Garantido por gatilho de banco, não pelo serviço — ver lancamentos_mundo_imutavel.';
comment on column lancamentos.lancamento_pai_id is
  'RF-13a split. "Uma parte não pode ter partes" (um nível só) é regra entre linhas — CHECK não alcança. Mora em app/dominio/split.py.';
comment on column lancamentos.versao is
  'data-model §5.6: o PUT envia a versao que leu; divergência responde 409 conflito_versao em vez de sobrescrever em silêncio.';

-- ── Os 8 índices de data-model §3.10 ────────────────────────────────────────
-- Parciais: casam exatamente com o filtro de soft delete que toda consulta usa
-- (Skill: query-partial-indexes).
create index lancamentos_mundo_data_idx     on lancamentos (mundo, data desc) where excluido_em is null;  -- lista, extrato, dashboard
create index lancamentos_status_data_idx    on lancamentos (status, data)     where excluido_em is null;  -- rotina diária, A pagar/A receber, atrasados
create index lancamentos_categoria_idx      on lancamentos (categoria_id, data);                          -- DRE, variação mensal
create index lancamentos_subcategoria_idx   on lancamentos (subcategoria_id, data);                       -- perfis de cliente/funcionário
create index lancamentos_servico_idx        on lancamentos (servico_id, data);                            -- RF-43b receita por serviço
create index lancamentos_recorrencia_idx    on lancamentos (recorrencia_id);                              -- navegar para a série
create index lancamentos_parcelamento_idx   on lancamentos (parcelamento_id);
create index lancamentos_pai_idx            on lancamentos (lancamento_pai_id);
create index lancamentos_lixeira_idx        on lancamentos (excluido_em)      where excluido_em is not null;  -- lixeira
-- Busca por texto livre (FR-037) e busca global (FR-046). Opclass qualificada porque
-- pg_trgm vive no schema `extensions` no Supabase.
create index lancamentos_descricao_trgm_idx on lancamentos using gin (descricao extensions.gin_trgm_ops);

-- FK que também é filtro combinável de FR-037
create index lancamentos_centro_custo_idx on lancamentos (centro_custo_id) where centro_custo_id is not null;

-- Nota de desvio consciente da Skill (schema-foreign-key-indexes): `criado_por`,
-- `atualizado_por`, `efetivado_por` e `excluido_por` ficam SEM índice. O motivo da regra é
-- acelerar JOIN e ON DELETE CASCADE; aqui não há cascade (usuários nunca são excluídos, só
-- ativo=false) e nenhuma consulta de contracts/ filtra por esses campos. Índice a mais
-- encarece toda escrita. Se T097 (medição com 5.000 lançamentos) mostrar necessidade, entram.

create trigger lancamentos_atualizado_em before update on lancamentos
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- RN-15 — `mundo` imutável, garantido pelo banco
--
-- Única regra de negócio em gatilho (data-model §3.10): é uma garantia que não pode
-- depender de o serviço lembrar. SQLSTATE próprio 'RN015' para que app/dominio/mundo.py
-- traduza em 409 `regra_violada` / requisito `RN-15` (contracts/README.md) sem casar texto.
-- ─────────────────────────────────────────────────────────────────────────────
create or replace function public.recusa_alteracao_de_mundo()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.mundo is distinct from old.mundo then
    raise exception 'O mundo não pode ser alterado depois de criado (tabela %).', tg_table_name
      using errcode = 'RN015';
  end if;
  return new;
end;
$$;

comment on function public.recusa_alteracao_de_mundo() is
  'RN-15. Recusa UPDATE que muda `mundo`. Anexada às 6 tabelas que têm a coluna.';

create trigger lancamentos_mundo_imutavel   before update of mundo on lancamentos
  for each row execute function public.recusa_alteracao_de_mundo();
create trigger recorrencias_mundo_imutavel  before update of mundo on recorrencias
  for each row execute function public.recusa_alteracao_de_mundo();
create trigger parcelamentos_mundo_imutavel before update of mundo on parcelamentos
  for each row execute function public.recusa_alteracao_de_mundo();
create trigger funcionarios_mundo_imutavel  before update of mundo on funcionarios
  for each row execute function public.recusa_alteracao_de_mundo();
create trigger servicos_mundo_imutavel      before update of mundo on servicos
  for each row execute function public.recusa_alteracao_de_mundo();
create trigger centros_custo_mundo_imutavel before update of mundo on centros_custo
  for each row execute function public.recusa_alteracao_de_mundo();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.11 lancamentos_tags — RN-14, sem limite por lançamento
-- ─────────────────────────────────────────────────────────────────────────────
create table lancamentos_tags (
  lancamento_id uuid not null references lancamentos (id) on delete cascade,
  tag_id        uuid not null references tags (id),
  primary key (lancamento_id, tag_id)
);

-- A PK cobre o lado lancamento_id; tag_id precisa do próprio índice (filtro por tag)
create index lancamentos_tags_tag_idx on lancamentos_tags (tag_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.12 anexos — bucket PRIVADO, download por URL assinada (FR-013)
-- ─────────────────────────────────────────────────────────────────────────────
create table anexos (
  id                uuid primary key default gen_random_uuid(),
  lancamento_id     uuid not null references lancamentos (id),
  nome_arquivo      text not null,
  caminho_storage   text not null unique,
  mime_type         text not null,
  tamanho_bytes     bigint not null check (tamanho_bytes > 0),
  criado_por        uuid not null references usuarios (id),
  criado_em         timestamptz not null default now()
);

comment on table anexos is
  'FR-013. Bucket privado: o download passa por URL assinada de curta validade gerada pelo backend, nunca URL pública. Limite de tamanho e MIME vêm de configuracoes, não do código (Princípio VII) — por isso não há CHECK de mime aqui.';
comment on column anexos.lancamento_id is
  'RF-013a: anexo fica no lançamento-pai e as partes do split leem por herança.';

create index anexos_lancamento_idx on anexos (lancamento_id);
create index anexos_criado_por_idx on anexos (criado_por);

-- ─────────────────────────────────────────────────────────────────────────────
-- View lancamentos_ativos — toda consulta de negócio parte dela (Princípio III)
--
-- security_invoker = true: a view respeita as políticas de quem chama, em vez de rodar com
-- os direitos do dono. Sem isso a view seria uma porta lateral em volta do RLS de 006.
-- ─────────────────────────────────────────────────────────────────────────────
create view lancamentos_ativos with (security_invoker = true) as
  select * from lancamentos where excluido_em is null;

comment on view lancamentos_ativos is
  'Princípio III: evita repetir o filtro de soft delete em cada consulta e esquecê-lo em alguma.';
