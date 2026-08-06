-- ─────────────────────────────────────────────────────────────────────────────
-- 015a — o card de custos por cliente aponta para `RF-58`, não `RF-105`
--
-- A `015` nasceu com `"requisito": "RF-105"` e foi aplicada assim. O código foi
-- renumerado para **`RF-58`** minutos depois, ainda na mesma entrega, por um motivo
-- de leitura: `FR-105` já existe na spec (tolerância de inadimplência) e as duas
-- famílias de código convivem no mesmo texto — `RF-105` ao lado de `FR-105` é um
-- convite a erro. `RF-58` também fica onde deveria: logo depois de `RF-55`, `RF-56`
-- e `RF-57`, na seção de categorias especiais.
--
-- A `015` já foi corrigida no arquivo, então um banco novo nunca passa por aqui. Esta
-- migração existe só para o banco que rodou a versão anterior — daí a guarda pelo
-- valor antigo, que a torna inofensiva em qualquer outro caso.
--
-- Tarefa: custo operacional por cliente (2026-08-05)
-- ─────────────────────────────────────────────────────────────────────────────

update configuracoes
   set valor = (
         select jsonb_agg(
                  case when item ->> 'id' = 'bloco_custos_cliente'
                       then jsonb_set(item, '{requisito}', '"RF-58"'::jsonb)
                       else item
                  end
                  order by (item ->> 'ordem_padrao')::int
                )
           from jsonb_array_elements(valor) as item
       ),
       atualizado_em = now()
 where chave = 'dashboard_cards_disponiveis'
   and valor @> '[{"id": "bloco_custos_cliente", "requisito": "RF-105"}]'::jsonb;
