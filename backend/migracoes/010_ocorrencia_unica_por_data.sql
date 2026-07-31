-- 010_ocorrencia_unica_por_data.sql — uma ocorrência por data em cada recorrência
--
-- Tarefa: T076/T083 (materialização idempotente)
--
-- Por que existe: D-08 diz que a rotina diária é idempotente — rodar duas vezes no
-- mesmo dia não duplica nada. O jeito de garantir isso **sem** consultar antes de cada
-- insert é deixar o banco recusar a segunda tentativa: `insert ... on conflict do
-- nothing` precisa de um índice único para ter no que conflitar.
--
-- Sem este índice, a proteção seria um `select` por ocorrência dentro do laço da rotina
-- — N+1 numa função com duração limitada — e ainda assim ficaria de pé só enquanto duas
-- invocações não rodassem ao mesmo tempo. O índice fecha o caso de corrida também.
--
-- Deliberadamente **não** é parcial em `excluido_em is null`: excluir uma ocorrência da
-- série não pode fazer ela renascer na próxima execução da rotina (data-model §3.13,
-- edge case "excluir uma ocorrência não toca a série"). A linha excluída continua
-- ocupando a data.
--
-- Parcial em `recorrencia_id is not null` porque a esmagadora maioria dos lançamentos é
-- avulsa: sem o filtro, o índice carregaria todas as linhas com `null` sem nunca ser
-- usado para elas.

create unique index if not exists lancamentos_recorrencia_data_uk
  on lancamentos (recorrencia_id, data)
  where recorrencia_id is not null;

comment on index public.lancamentos_recorrencia_data_uk is
  'D-08: é o que torna a materialização de recorrências idempotente. A rotina diária tenta inserir e o banco recusa a repetição, em vez de a rotina consultar antes de cada insert.';
