-- 006_rls.sql
-- RLS ligada com NEGAÇÃO para as chaves públicas — research.md D-03a
--
-- O problema que isto fecha: a chave `anon` do Supabase vive no navegador por natureza. Sem
-- esta migração, qualquer pessoa com essa chave leria `lancamentos` direto pelo endereço
-- `/rest/v1/lancamentos`, contornando todo o RBAC do FastAPI. É o lugar em que erro
-- silencioso custa mais caro em todo o projeto — daí a conferência obrigatória de T020.
--
-- A autorização real mora no FastAPI (`exige_papel`). O backend fala com o banco pela
-- credencial de serviço, que tem BYPASSRLS — por isso ligar RLS aqui não afeta o backend.
--
-- Duas camadas, de propósito (Skill: security-privileges + security-rls-basics):
--   1. REVOKE dos privilégios que o Supabase concede por padrão a anon/authenticated.
--      É a defesa principal: sem privilégio, a política nem é consultada.
--   2. ENABLE ROW LEVEL SECURITY sem NENHUMA política permissiva. Em Postgres, RLS ligada
--      com zero políticas nega tudo para quem não é dono e não tem BYPASSRLS. É a rede
--      embaixo — se alguém reconceder GRANT no futuro, a porta continua fechada.
--
-- Tarefa: T014

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Tirar os privilégios padrão das chaves públicas
-- ─────────────────────────────────────────────────────────────────────────────

-- Impede que objetos criados DEPOIS desta migração nasçam com acesso público.
alter default privileges in schema public revoke all on tables    from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke all on functions from anon, authenticated;

revoke all on all tables    in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;

-- `usage` no schema fica revogado também: sem ele não se alcança nem o nome do objeto.
revoke usage on schema public from anon, authenticated;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. RLS ligada em todas as tabelas, sem política permissiva
--
-- `force row level security` faz a regra valer também para o dono da tabela — assim nem
-- uma conexão que por acaso use o papel dono passa por cima. Não afeta a credencial de
-- serviço, que tem BYPASSRLS.
-- ─────────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  tabelas text[] := array[
    -- plataforma
    'usuarios', 'configuracoes', 'auditoria', 'execucoes_rotina', 'cotacoes_cambio',
    -- cadastros
    'categorias', 'subcategorias', 'clientes', 'clientes_servicos',
    'funcionarios', 'servicos', 'centros_custo', 'tags',
    -- núcleo financeiro
    'parcelamentos', 'recorrencias', 'lancamentos', 'lancamentos_tags', 'anexos',
    -- notificações
    'notificacoes'
  ];
begin
  foreach t in array tabelas loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force  row level security', t);
  end loop;
end $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Função pré-existente do projeto: tirar EXECUTE das chaves públicas
--
-- `public.rls_auto_enable()` já existia no projeto antes desta feature — é a rede de
-- proteção do próprio Supabase, ligada ao gatilho de evento `ensure_rls`, que liga RLS
-- automaticamente em toda tabela nova de `public`. Ela só LIGA RLS, nunca desliga.
--
-- O linter do Supabase aponta que `anon` e `authenticated` podem chamá-la por
-- `/rest/v1/rpc/rls_auto_enable`. Na prática a chamada erraria: função que retorna
-- `event_trigger` não pode ser executada como função comum. Mesmo assim o EXECUTE sai —
-- privilégio que não serve a ninguém não deveria existir (Skill: security-privileges).
-- ─────────────────────────────────────────────────────────────────────────────
revoke execute on function public.rls_auto_enable() from anon, authenticated, public;

-- ─────────────────────────────────────────────────────────────────────────────
-- Nenhum `create policy` neste arquivo — é INTENCIONAL. Política permissiva aqui
-- reabriria exatamente o buraco que D-03a fecha. O frontend nunca consulta o banco pelo
-- SDK do Supabase: o SDK no cliente serve só ao login (Princípio IV).
--
-- ⚠️ O linter do Supabase vai apontar `rls_enabled_no_policy` (nível INFO) em todas as
-- tabelas (20, depois que a `011_importacoes.sql` entrou).
-- É o resultado esperado, não um defeito a corrigir. "RLS ligada sem política" é a forma
-- de negar tudo em Postgres. Quem "consertar" isso adicionando política estará abrindo as
-- finanças da empresa para a chave que vive no navegador.
-- ─────────────────────────────────────────────────────────────────────────────
