-- 003_cadastros.sql
-- Cadastros — data-model.md §3.2 a §3.9
--
-- Dependência circular: `subcategorias.cliente_id` → `clientes` e
-- `subcategorias.funcionario_id` → `funcionarios`, mas as duas tabelas nascem depois de
-- `subcategorias`. Resolvido como data-model §7 manda: tabelas primeiro, FKs circulares
-- no fim do arquivo.
--
-- Onde `mundo` existe aqui: `funcionarios`, `servicos`, `centros_custo`.
-- Onde não existe (exceções documentadas): `categorias`, `subcategorias` (FR-006),
-- `tags` (RF-103 não as lista), `clientes` (D-04).
--
-- O gatilho de imutabilidade de `mundo` (RN-15) é anexado em 004, junto da função.
--
-- Tarefa: T011

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.2 categorias — sem mundo (FR-006)
-- ─────────────────────────────────────────────────────────────────────────────
create table categorias (
  id            uuid primary key default gen_random_uuid(),
  nome          text not null,
  cor           text not null check (cor ~ '^#[0-9A-Fa-f]{6}$'),
  icone         text not null,                                        -- nome do ícone Lucide (FR-072)
  tipo          tipo_categoria not null,
  especial      boolean not null default false,                       -- RF-55..57
  vinculo       vinculo_subcategoria null,
  ordem         integer not null default 0,
  arquivada_em  timestamptz null,                                     -- arquivamento, não exclusão
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),

  -- especial=true exige vinculo; especial=false exige vinculo nulo
  constraint categorias_especial_exige_vinculo
    check ((especial and vinculo is not null) or (not especial and vinculo is null))
);

comment on table  categorias is
  'FR-006: compartilhada pelos dois mundos, sem coluna mundo. Arquivada, não excluída.';
comment on column categorias.vinculo is
  'FR-079: promover a especial é DADO, não código. O card do Dashboard e o perfil saem daqui — nunca de if nome = ''Clientes''.';

-- Nome único entre as não arquivadas (data-model §3.2)
create unique index categorias_nome_ativas_uidx on categorias (lower(nome)) where arquivada_em is null;
-- Só uma categoria especial por vínculo — senão o Dashboard não sabe qual card montar
create unique index categorias_vinculo_uidx on categorias (vinculo) where vinculo is not null and arquivada_em is null;

create trigger categorias_atualizado_em before update on categorias
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.3 subcategorias — exatamente dois níveis, sem subcategoria pai (FR-073)
-- ─────────────────────────────────────────────────────────────────────────────
create table subcategorias (
  id              uuid primary key default gen_random_uuid(),
  categoria_id    uuid not null references categorias (id),
  nome            text not null,
  cor             text null check (cor is null or cor ~ '^#[0-9A-Fa-f]{6}$'),  -- herda a da categoria quando nula
  cliente_id      uuid null,                                          -- FK adicionada no fim do arquivo (D-07)
  funcionario_id  uuid null,                                          -- FK adicionada no fim do arquivo (D-07)
  ordem           integer not null default 0,
  arquivada_em    timestamptz null,
  criado_em       timestamptz not null default now(),
  atualizado_em   timestamptz not null default now(),

  -- No máximo um dos dois vínculos preenchido
  constraint subcategorias_um_vinculo_no_maximo
    check (not (cliente_id is not null and funcionario_id is not null))
);

comment on table subcategorias is
  'FR-073: dois níveis, sem hierarquia mais profunda. Nas categorias especiais as linhas são ESPELHADAS de clientes/funcionarios (D-07).';
comment on column subcategorias.cliente_id is
  'D-07. A checagem "só quando a categoria tem o vinculo correspondente" é cruzada entre tabelas — CHECK não alcança outra tabela. Mora em app/dominio/espelho_subcategoria.py, porque data-model §3.10 reserva o único gatilho de regra para a imutabilidade de mundo.';

-- Nome único dentro da categoria, entre as não arquivadas (data-model §3.3)
create unique index subcategorias_nome_ativas_uidx
  on subcategorias (categoria_id, lower(nome)) where arquivada_em is null;

-- FK indexada (Skill: schema-foreign-key-indexes)
create index subcategorias_categoria_idx     on subcategorias (categoria_id);
create index subcategorias_cliente_idx       on subcategorias (cliente_id)     where cliente_id is not null;
create index subcategorias_funcionario_idx   on subcategorias (funcionario_id) where funcionario_id is not null;

create trigger subcategorias_atualizado_em before update on subcategorias
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.4 clientes — SEM mundo (D-04, 2ª exceção a RN-15)
-- ─────────────────────────────────────────────────────────────────────────────
create table clientes (
  id                uuid primary key default gen_random_uuid(),
  nome              text not null,
  empresa           text null,
  contato_email     text null,
  contato_telefone  text null,
  tipo_cobranca     tipo_cobranca not null,                           -- RF-60
  valor_recorrente  numeric(14,2) null check (valor_recorrente is null or valor_recorrente > 0),
  dia_cobranca      smallint null check (dia_cobranca is null or dia_cobranca between 1 and 31),
  mundo_cobranca    mundo null,
  observacoes       text null,
  arquivado_em      timestamptz null,                                 -- RN-06: arquivado, nunca excluído
  criado_em         timestamptz not null default now(),
  atualizado_em     timestamptz not null default now(),

  -- tipo_cobranca=recorrente exige os três campos da mensalidade
  constraint clientes_recorrente_completo
    check (
      tipo_cobranca <> 'recorrente'
      or (valor_recorrente is not null and dia_cobranca is not null and mundo_cobranca is not null)
    )
);

comment on table  clientes is
  'D-04: cliente NÃO tem mundo — cadastro único, 2ª exceção documentada a RN-15. O filtro "clientes do mundo X" é DERIVADO da movimentação (FR-002).';
comment on column clientes.mundo_cobranca is
  'Não é o mundo do cliente: é o mundo em que as ocorrências da mensalidade nascem, porque o lançamento gerado precisa de mundo (RN-15). Obrigatório quando tipo_cobranca=recorrente.';

create unique index clientes_nome_ativos_uidx on clientes (lower(nome)) where arquivado_em is null;

create trigger clientes_atualizado_em before update on clientes
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.7 servicos — com mundo (FR-104)
-- ─────────────────────────────────────────────────────────────────────────────
create table servicos (
  id            uuid primary key default gen_random_uuid(),
  nome          text not null,
  mundo         mundo not null,                                       -- RN-15 — imutável (gatilho em 004)
  ativo         boolean not null default true,
  ordem         integer not null default 0,
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

comment on table servicos is 'FR-104. CRM → digital, Redes → infra. Seed em 008.';

create unique index servicos_nome_uidx on servicos (lower(nome));
create index servicos_mundo_idx on servicos (mundo, ordem) where ativo;

create trigger servicos_atualizado_em before update on servicos
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.5 clientes_servicos — serviços contratados (RF-60)
-- ─────────────────────────────────────────────────────────────────────────────
create table clientes_servicos (
  cliente_id uuid not null references clientes (id) on delete cascade,
  servico_id uuid not null references servicos (id),
  primary key (cliente_id, servico_id)
);

-- A PK já cobre (cliente_id, …); o lado servico_id precisa do seu próprio índice
create index clientes_servicos_servico_idx on clientes_servicos (servico_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.6 funcionarios — com mundo obrigatório e imutável
-- ─────────────────────────────────────────────────────────────────────────────
create table funcionarios (
  id                uuid primary key default gen_random_uuid(),
  nome              text not null,
  funcao            text not null,
  tipo_contratacao  tipo_contratacao not null,
  valor_mensal      numeric(14,2) not null check (valor_mensal > 0),
  dia_pagamento     smallint not null check (dia_pagamento between 1 and 31),
  mundo             mundo not null,                                   -- RN-15 — imutável (gatilho em 004)
  arquivado_em      timestamptz null,                                 -- RN-06
  criado_em         timestamptz not null default now(),
  atualizado_em     timestamptz not null default now()
);

comment on table funcionarios is
  'RN-06: arquivado, nunca excluído. Seed FR-086: Dylan e Marcondes, ambos mundo digital (confirmado 2026-07-30).';

create unique index funcionarios_nome_ativos_uidx on funcionarios (lower(nome)) where arquivado_em is null;
create index funcionarios_mundo_idx on funcionarios (mundo) where arquivado_em is null;

create trigger funcionarios_atualizado_em before update on funcionarios
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.8 centros_custo — com mundo. Ausência no lançamento significa "geral" (RN-13)
-- ─────────────────────────────────────────────────────────────────────────────
create table centros_custo (
  id            uuid primary key default gen_random_uuid(),
  nome          text not null,
  mundo         mundo not null,                                       -- RF-103 — imutável (gatilho em 004)
  arquivado_em  timestamptz null,
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

comment on table centros_custo is
  'RN-13: opcional no lançamento; AUSÊNCIA significa "geral". NÃO se cria um centro chamado "Geral".';

create unique index centros_custo_nome_ativos_uidx on centros_custo (mundo, lower(nome)) where arquivado_em is null;

create trigger centros_custo_atualizado_em before update on centros_custo
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.9 tags — sem hierarquia, sem mundo, sem limite por lançamento (RN-14)
-- ─────────────────────────────────────────────────────────────────────────────
create table tags (
  id            uuid primary key default gen_random_uuid(),
  nome          text not null unique,
  cor           text not null check (cor ~ '^#[0-9A-Fa-f]{6}$'),
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

comment on table tags is 'RN-14: sem hierarquia, sem mundo, sem limite por lançamento.';

create trigger tags_atualizado_em before update on tags
  for each row execute function public.toca_atualizado_em();

-- ─────────────────────────────────────────────────────────────────────────────
-- FKs circulares, no fim do arquivo (data-model §7)
-- ─────────────────────────────────────────────────────────────────────────────
alter table subcategorias
  add constraint subcategorias_cliente_id_fkey
  foreign key (cliente_id) references clientes (id);

alter table subcategorias
  add constraint subcategorias_funcionario_id_fkey
  foreign key (funcionario_id) references funcionarios (id);
