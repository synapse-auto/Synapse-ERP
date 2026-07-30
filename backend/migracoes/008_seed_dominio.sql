-- 008_seed_dominio.sql
-- Dados iniciais de domínio: 9 categorias (FR-076), 9 serviços (FR-104), 2 funcionários
-- (FR-086) com subcategoria espelho e recorrência de folha (D-07, FR-088).
--
-- Tarefa: T017 · depende de T016 (mundo dos funcionários — confirmado: os dois `digital`)
--
-- ─────────────────────────────────────────────────────────────────────────────
-- TRÊS COISAS QUE PRECISAM SER DITAS EM VOZ ALTA (constituição, Governança)
--
-- 1. USUÁRIO `Sistema`. `recorrencias.criado_por` é NOT NULL e aponta para `usuarios`, mas
--    no momento do seed nenhuma pessoa existe ainda. Sem um autor válido, a recorrência da
--    folha não pode nascer — e quickstart.md §3 confere justamente que ela nasceu. Então
--    entra uma linha `Sistema` com UUID fixo, `ativo = false` e papel `operador`:
--      · `ativo = false` impede login e a exclui da contagem de "último gestor ativo";
--      · `operador` é o menor privilégio (RF-02), e ela nunca autoriza nada — só serve de
--        destino de chave estrangeira para o que o sistema criou sozinho.
--    Isto abre uma exceção à regra "usuarios.id é IGUAL ao id do Supabase Auth"
--    (data-model §3.1): esta única linha não tem contraparte no Auth. Registrado em
--    data-model §3.1 na mesma entrega.
--
-- 2. `dia_pagamento` DOS FUNCIONÁRIOS FOI ASSUMIDO COMO 5. FR-086 dá nome, função e valor,
--    mas não o dia. A coluna é NOT NULL. O dono do projeto ajusta pela tela quando quiser —
--    é dado, não código.
--
-- 3. AS RECORRÊNCIAS NASCEM SEM HISTÓRICO RETROATIVO. `data_inicio` é o próximo dia 5 a
--    partir de hoje, nunca uma data passada. Se fosse retroativa, RN-05a geraria ocorrências
--    já `efetivado` — pagamentos que ninguém conferiu, inventando histórico financeiro.
--    O histórico real é a pendência #5 do plan.md e entra pela importação (FR-044).
-- ─────────────────────────────────────────────────────────────────────────────

-- ─────────────────────────────────────────────────────────────────────────────
-- Usuário `Sistema` — ver nota 1
-- ─────────────────────────────────────────────────────────────────────────────
insert into usuarios (id, nome, email, papel, ativo) values
  ('00000000-0000-0000-0000-000000000000', 'Sistema', 'sistema@synapse.local', 'operador', false)
on conflict (id) do nothing;

comment on column usuarios.id is
  'Igual ao id do Supabase Auth. Única exceção: a linha Sistema (00000000-…-0000), que não tem contraparte no Auth e existe só como autor do que o sistema cria sozinho (seed 008 e rotinas).';

-- ─────────────────────────────────────────────────────────────────────────────
-- 9 categorias (FR-076). Cor e ícone são dados editáveis (FR-072) — os valores abaixo são
-- ponto de partida, não decisão de design. Ícone = nome do componente Lucide.
-- Clientes e Funcionários nascem `especial` com `vinculo` (FR-077, FR-078) — é o `vinculo`
-- que faz o Dashboard montar o card, nunca o nome (FR-079).
-- ─────────────────────────────────────────────────────────────────────────────
insert into categorias (nome, cor, icone, tipo, especial, vinculo, ordem) values
  ('Clientes',                '#8B6CF0', 'users',     'receita', true,  'cliente',     1),
  ('Funcionários',            '#F2769A', 'briefcase', 'despesa', true,  'funcionario', 2),
  ('Infraestrutura',          '#4FA8E0', 'server',    'despesa', false, null,          3),
  ('Ferramentas/Assinaturas', '#5BC8A8', 'wrench',    'despesa', false, null,          4),
  ('Impostos',                '#E8834A', 'landmark',  'despesa', false, null,          5),
  ('Marketing',               '#E0B94F', 'megaphone', 'despesa', false, null,          6),
  ('Equipamentos',            '#7B86C4', 'laptop',    'despesa', false, null,          7),
  ('Transporte',              '#68A25B', 'truck',     'despesa', false, null,          8),
  ('Outros',                  '#8D8A9E', 'ellipsis',  'ambas',   false, null,          9);

-- ─────────────────────────────────────────────────────────────────────────────
-- 9 serviços (FR-104), divididos por mundo conforme data-model §3.7
-- ─────────────────────────────────────────────────────────────────────────────
insert into servicos (nome, mundo, ordem) values
  ('CRM',                       'digital', 1),
  ('Automação com IA',          'digital', 2),
  ('Desenvolvimento Web',       'digital', 3),
  ('Infraestrutura de Redes',   'infra',   4),
  ('Segurança',                 'infra',   5),
  ('Energia Solar',             'infra',   6),
  ('Ar Condicionados',          'infra',   7),
  ('Painéis de LED',            'infra',   8),
  ('Montagem de Racks',         'infra',   9);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2 funcionários (FR-086), ambos `digital` (T016, confirmado em 2026-07-30), cada um com
-- subcategoria espelho na categoria Funcionários e recorrência mensal da folha — tudo na
-- mesma transação, como D-07/FR-088 exigem.
-- ─────────────────────────────────────────────────────────────────────────────
do $$
declare
  cat_funcionarios uuid;
  usuario_sistema  uuid := '00000000-0000-0000-0000-000000000000';
  f                record;
  id_funcionario   uuid;
  id_subcategoria  uuid;
  primeiro_venc    date;
begin
  select id into strict cat_funcionarios
    from categorias where vinculo = 'funcionario' and arquivada_em is null;

  for f in
    select * from (values
      ('Dylan',     'Automação com n8n e IA',        'pj'::tipo_contratacao, 1200.00::numeric(14,2), 5::smallint, 'digital'::mundo),
      ('Marcondes', 'Java e Engenharia de Software',  'pj'::tipo_contratacao,  900.00::numeric(14,2), 5::smallint, 'digital'::mundo)
    ) as t(nome, funcao, tipo_contratacao, valor_mensal, dia_pagamento, mundo)
  loop
    insert into funcionarios (nome, funcao, tipo_contratacao, valor_mensal, dia_pagamento, mundo)
      values (f.nome, f.funcao, f.tipo_contratacao, f.valor_mensal, f.dia_pagamento, f.mundo)
      returning id into id_funcionario;

    -- Subcategoria espelho (D-07). `cor` nula = herda a da categoria.
    insert into subcategorias (categoria_id, nome, funcionario_id, ordem)
      values (cat_funcionarios, f.nome, id_funcionario, f.dia_pagamento)
      returning id into id_subcategoria;

    -- Primeiro vencimento: próximo dia `dia_pagamento` a partir de hoje. Nunca retroativo
    -- (nota 3 no topo). `make_date` + o menor entre o dia pedido e o último dia do mês
    -- resolve o mês curto — a mesma regra de clamp que dominio/recorrencia.py aplica.
    primeiro_venc := make_date(
      extract(year  from current_date)::int,
      extract(month from current_date)::int,
      least(f.dia_pagamento::int, extract(day from (date_trunc('month', current_date) + interval '1 month - 1 day'))::int)
    );
    if primeiro_venc < current_date then
      primeiro_venc := make_date(
        extract(year  from (current_date + interval '1 month'))::int,
        extract(month from (current_date + interval '1 month'))::int,
        least(f.dia_pagamento::int, extract(day from (date_trunc('month', current_date + interval '1 month') + interval '1 month - 1 day'))::int)
      );
    end if;

    -- Recorrência da folha (FR-088, RF-67). `gerada_ate` nulo: nada materializado ainda —
    -- a rotina diária gera até o horizonte de configuracoes.recorrencia_horizonte_meses.
    insert into recorrencias (
      mundo, tipo, descricao, valor,
      categoria_id, subcategoria_id,
      frequencia, dia_vencimento, data_inicio,
      efetivar_automaticamente, funcionario_id, criado_por
    ) values (
      f.mundo, 'despesa', 'Pagamento — ' || f.nome, f.valor_mensal,
      cat_funcionarios, id_subcategoria,
      'mensal', f.dia_pagamento, primeiro_venc,
      true, id_funcionario, usuario_sistema
    );
  end loop;
end $$;
