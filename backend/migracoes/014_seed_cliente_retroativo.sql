-- ─────────────────────────────────────────────────────────────────────────────
-- 014 — limite do histórico retroativo de cliente ("cliente desde")
--
-- Cadastrar um cliente que já é cliente há meses passa a poder carregar o passado
-- da mensalidade: as ocorrências do mês de início até o mês atual nascem
-- `efetivado` (`RN-05a`) e entram no saldo (`RN-05`), reconstruindo o histórico de
-- receita que hoje simplesmente não existe — e que faz falta porque **não existe
-- saldo inicial** (research.md D-06).
--
-- ## Por que isto é configuração e não uma constante no código
--
-- "Até quantos meses atrás dá para carregar" é limite de negócio, e `RNF-02` /
-- Princípio VII são explícitos: limite, prazo e multiplicador vêm de `configuracoes`.
-- O código tem `PADRAO_MESES_MAXIMO` em `dominio/cliente_retroativo.py`, mas só para
-- o sistema subir antes desta migração; o valor que decide é este.
--
-- ## Por que 120
--
-- 10 anos. Cobre com folga qualquer cliente real da Synapse e ainda recusa o erro de
-- digitação que importa — trocar 2025 por 2015 num campo de ano.
--
-- `on conflict do nothing`: reaplicar não sobrescreve ajuste feito pela tela (`FR-105`).
--
-- Tarefa: cliente retroativo (2026-08-04)
-- ─────────────────────────────────────────────────────────────────────────────

insert into configuracoes (chave, valor, descricao) values

  ('cliente_retroativo_meses_maximo',
   '120'::jsonb,
   'Até quantos meses atrás o cadastro de cliente aceita carregar o histórico da mensalidade ("cliente desde"). Acima disso o POST /api/clientes responde 400 validacao. As ocorrências passadas nascem efetivado (RN-05a) e entram no saldo (RN-05).')

on conflict (chave) do nothing;
