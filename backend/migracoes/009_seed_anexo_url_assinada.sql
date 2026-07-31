-- 009_seed_anexo_url_assinada.sql — validade da URL assinada de anexo
--
-- Tarefa: T064 (anexos)
--
-- Por que uma migração nova em vez de encostar no 007: migração aplicada não se
-- reescreve. O 007 já rodou no banco em 2026-07-30 (T018); mudá-lo faria o arquivo
-- deixar de descrever o que de fato foi aplicado, e a próxima pessoa que rodasse a
-- sequência do zero teria um banco diferente do que está no ar.
--
-- Por que a chave existe: o bucket `anexos` é privado (data-model §3.12) e o download
-- passa por URL assinada gerada pelo backend. "Curta validade" é um prazo — e prazo é
-- exatamente o que o Princípio VII (RNF-02) manda tirar do código. Com a chave no banco,
-- encurtar a janela de exposição de uma nota fiscal é um UPDATE, não um deploy.
--
-- 300 segundos: tempo de sobra para o navegador começar o download depois do clique, e
-- curto o bastante para um link vazado no histórico não servir a quem o achar depois.

insert into configuracoes (chave, valor, descricao) values
  ('anexo_url_assinada_segundos',
   '300'::jsonb,
   'Validade, em segundos, da URL assinada de download de anexo (FR-013). O bucket é privado: não existe URL pública, então esta é a única janela de acesso ao arquivo.')
on conflict (chave) do nothing;
