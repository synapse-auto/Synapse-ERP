-- 011_importacoes.sql — o estado da importação em duas etapas
--
-- Tarefa: T133–T136 (importação CSV/OFX)
--
-- ## Por que a tabela precisa existir
--
-- `contracts/lancamentos.md §6` desenha a importação em **três requisições**: enviar o
-- arquivo (que devolve `importacao_id`), mapear as colunas e confirmar. Entre elas, o
-- conteúdo lido precisa sobreviver.
--
-- Guardar em memória não funciona: cada requisição da Vercel pode cair numa instância
-- diferente (research.md D-01, o mesmo motivo de o SQLite ter sido descartado). Pedir o
-- arquivo de novo a cada etapa jogaria fora a prévia que o usuário acabou de conferir —
-- e a confirmação grava **em lotes com cursor**, então seriam vários reenvios do mesmo
-- arquivo.
--
-- O data-model foi desenhado com 19 tabelas e esta não estava entre elas: a necessidade
-- só ficou clara ao implementar o fluxo de três etapas. Registrado em data-model §7.
--
-- ## Por que `jsonb` e não uma tabela de linhas
--
-- As linhas do arquivo são dado **temporário**, descartado depois de confirmar. Uma
-- tabela `importacao_linhas` com 5.000 registros por importação precisaria de limpeza
-- própria e não seria consultada por nada além do próprio fluxo. O `jsonb` cabe no
-- limite do Postgres com folga para as 5.000 linhas que o leitor aceita.
--
-- ## Por que expira
--
-- Importação abandonada no meio é o caso comum — o usuário vê a prévia, não gosta e
-- fecha a aba. Sem expiração, a tabela vira depósito de arquivos que ninguém vai
-- confirmar. A rotina diária limpa o que passou de `expira_em`.

create table if not exists importacoes (
  id             uuid primary key default gen_random_uuid(),
  usuario_id     uuid not null references usuarios (id),
  nome_arquivo   text not null,
  formato        text not null check (formato in ('csv', 'ofx')),
  colunas        jsonb not null,
  linhas         jsonb not null,                                  -- conteúdo lido, temporário
  mapeamento     jsonb null,                                      -- preenchido na 2ª etapa
  mundo          mundo null,                                      -- escolhido no mapeamento (RN-15)
  cursor         integer not null default 0,                      -- gravação em lotes (D-02a)
  gravados       integer not null default 0,
  concluida_em   timestamptz null,
  criado_em      timestamptz not null default now(),
  expira_em      timestamptz not null default now() + interval '24 hours'
);

comment on table importacoes is
  'FR-044. Estado das três etapas (enviar, mapear, confirmar). Dado TEMPORÁRIO: expira em 24h e é limpo pela rotina diária. Não é histórico financeiro — o que vira lançamento sai daqui e vive em lancamentos.';
comment on column importacoes.linhas is
  'Conteúdo lido do arquivo. jsonb em vez de tabela de linhas porque é descartável e só o próprio fluxo consulta.';
comment on column importacoes.cursor is
  'D-02a: índice da última linha gravada. A confirmação avança em lotes e retoma daqui, como as recorrências.';
comment on column importacoes.mundo is
  'RN-15 não admite lançamento sem mundo, e o arquivo não traz essa informação. Escolhido no mapeamento, vale para o arquivo inteiro.';

create index if not exists importacoes_usuario_idx on importacoes (usuario_id);
-- A varredura da limpeza: só as que ainda não terminaram e já passaram do prazo.
create index if not exists importacoes_expiradas_idx on importacoes (expira_em)
  where concluida_em is null;

-- Mesma política das demais: RLS ligada sem política, negando as chaves públicas
-- (research.md D-03a). O acesso é só pelo backend, com a service_role.
alter table importacoes enable row level security;
