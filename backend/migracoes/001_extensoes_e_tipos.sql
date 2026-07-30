-- 001_extensoes_e_tipos.sql
-- Extensões e tipos enumerados — data-model.md §2
--
-- Skill supabase-postgres-best-practices acionada antes desta migração (plan.md).
-- Aplicado: pg_trgm fica no schema `extensions` (padrão do Supabase — não poluir `public`).
--
-- Tarefa: T009

create extension if not exists pg_trgm with schema extensions;

-- Os 13 tipos de data-model.md §2. `escopo_edicao_serie` está no vocabulário mas é
-- parâmetro de endpoint, não coluna — por isso não vira CREATE TYPE aqui (data-model §2).

create type mundo                   as enum ('digital', 'infra');                                              -- RN-15
create type tipo_lancamento         as enum ('receita', 'despesa');                                            -- RF-10
create type status_lancamento       as enum ('programado', 'pendente', 'efetivado', 'atrasado', 'cancelado');   -- RN-03
create type tipo_categoria          as enum ('receita', 'despesa', 'ambas');                                    -- RF-50
create type papel_usuario           as enum ('gestor', 'operador');                                             -- RF-02
create type frequencia_recorrencia  as enum ('semanal', 'mensal', 'anual', 'dias');                             -- RF-15
create type tipo_cobranca           as enum ('pontual', 'recorrente', 'parcelada');                             -- RF-60
create type tipo_contratacao        as enum ('pj', 'freelancer');                                               -- RF-65
create type moeda                   as enum ('BRL', 'USD');                                                     -- RN-12
create type vinculo_subcategoria    as enum ('cliente', 'funcionario');                                         -- RF-55..57
create type tipo_notificacao        as enum ('vencimento', 'inadimplencia', 'resumo_semanal', 'caixa_baixo');    -- RF-80..83
create type acao_auditoria          as enum ('criacao', 'edicao', 'exclusao', 'restauracao');                    -- RN-08

-- Função de apoio: mantém `atualizado_em` sem o serviço precisar lembrar.
-- search_path fixo e vazio — recomendação de segurança do Supabase para funções.
create or replace function public.toca_atualizado_em()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.atualizado_em := now();
  return new;
end;
$$;

comment on function public.toca_atualizado_em() is
  'Trigger BEFORE UPDATE: atualiza atualizado_em. Usada por todas as tabelas com a coluna.';
