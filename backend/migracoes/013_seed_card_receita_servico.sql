-- ─────────────────────────────────────────────────────────────────────────────
-- 013 — o card "Receita por serviço" entra no catálogo do Dashboard (`FR-064`)
--
-- ## O que faltava
--
-- `RF-43b`/`FR-064` pedem o bloco de receita por serviço da Synapse no Dashboard. O
-- dado existe desde B3 (`GET /api/dashboard` devolve `receita_por_servico`) e o
-- componente existe desde C4 (resolvido pelo id `receita_servico`). Só que
-- `dashboard_cards_disponiveis` — a migração `007` — nasceu com **18** entradas e
-- nenhuma delas é essa.
--
-- Como `FR-106` proíbe rótulo de card escrito no frontend, a tela monta a grade a
-- partir do catálogo e **ignora em silêncio** todo id que não esteja lá. Resultado:
-- o bloco nunca era desenhado, sem erro nenhum aparecer. Estava anotado como
-- divergência nº 1 no `frontend/README.md` desde 2026-07-31.
--
-- Esta migração é a correção inteira: nenhuma linha de código muda.
--
-- ## Por que não editar a `007`
--
-- Migração aplicada não se reescreve (mesmo motivo da `009`): o arquivo deixaria de
-- descrever o que de fato rodou no banco.
--
-- ## Por que `update` com `jsonb_agg` e não um valor novo inteiro
--
-- `PUT /api/configuracoes` aceita qualquer chave existente, inclusive esta. Escrever
-- um array literal por cima apagaria um ajuste que o gestor tenha feito pela tela.
-- Aqui cada entrada é reescrita **individualmente**: só as três posições que precisam
-- abrir espaço mudam, e o resto passa intacto.
--
-- A guarda `not (valor @> ...)` deixa a migração idempotente — reaplicar não duplica
-- a entrada nem embaralha a ordem de novo.
--
-- ## A posição escolhida
--
-- 16, logo depois de "Maiores despesas" (15), fechando o grupo `grafico` — é onde o
-- mockup desenha o bloco. Os três cards especiais que vinham depois descem uma casa
-- (16→17, 17→18, 18→19). Preferência de usuário não é tocada: ela mora em
-- `usuarios.preferencias` e vence o catálogo no desempate (`app/dashboard/rotas.py`).
--
-- Tarefa: auditoria de requisitos de 2026-08-03
-- ─────────────────────────────────────────────────────────────────────────────

update configuracoes
   set valor = (
         select jsonb_agg(entrada order by (entrada ->> 'ordem_padrao')::int)
         from (
           -- as 18 já existentes, com os três especiais empurrados uma casa
           select case
                    when item ->> 'id' in ('bloco_clientes', 'bloco_funcionarios',
                                           'linha_tempo_7_dias')
                    then jsonb_set(item, '{ordem_padrao}',
                                   to_jsonb(((item ->> 'ordem_padrao')::int) + 1))
                    else item
                  end as entrada
             from jsonb_array_elements(valor) as item

           union all

           select '{"id": "receita_servico", "rotulo": "Receita por serviço",
                    "grupo": "grafico", "ordem_padrao": 16, "visivel_padrao": true,
                    "requisito": "FR-064"}'::jsonb
         ) as entradas
       ),
       atualizado_em = now()
 where chave = 'dashboard_cards_disponiveis'
   and not (valor @> '[{"id": "receita_servico"}]'::jsonb);
