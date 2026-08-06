-- ─────────────────────────────────────────────────────────────────────────────
-- 015 — custo operacional por cliente (`RF-58`)
--
-- Hoje o cliente só aparece na receita: "Clientes" é a categoria especial com
-- `vinculo = cliente`, e cadastrar um cliente cria a subcategoria espelho dele lá
-- dentro (D-07). O que a Synapse não consegue responder é **quanto cada cliente
-- custa** — servidor, licença, hora de terceiro, deslocamento. Sem isso não existe
-- margem por cliente, só faturamento por cliente.
--
-- ## A escolha: uma segunda categoria especial, não um caso especial no código
--
-- A alternativa era "Custos Operacionais" ganhar tratamento próprio — um
-- `if nome == 'Custos Operacionais'` espalhado por Dashboard, perfil e relatório.
-- É exatamente o que `FR-079` proíbe.
--
-- Então a mecânica é a que já existe: `especial = true` + `vinculo = 'cliente'`. O
-- que muda é que **o vínculo deixa de ser único por si e passa a ser único por
-- (vinculo, tipo)**: um lado de receita e um lado de despesa por vínculo. Quem
-- agrupa continua sem saber que aquela subcategoria é um cliente — continua sendo
-- subcategoria.
--
-- Consequência aceita e dita em voz alta: cada cliente passa a ter **dois**
-- espelhos (um em Clientes, um em Custos Operacionais). O nome, o arquivamento e o
-- desarquivamento continuam vindo do cadastro e valem para os dois de uma vez —
-- `dominio/espelho_subcategoria.py` já opera por `cliente_id`, não por linha.
--
-- Outra consequência: por `RN-01`, lançamento em categoria especial **exige**
-- subcategoria. Custo operacional sem cliente não cabe aqui — vai em
-- Infraestrutura, Ferramentas/Assinaturas ou Outros, como sempre foi.
--
-- ## Por que `tipo <> 'ambas'` vira restrição
--
-- É `tipo` que separa as duas categorias do mesmo vínculo. Uma especial `ambas`
-- deixaria "qual é a categoria de receita do cliente?" sem resposta única — o mesmo
-- buraco que o índice único de `vinculo` fechava antes.
--
-- ## Reaplicar é seguro
--
-- Índices com `if not exists`, promoção idempotente pelo bloco `do`, espelhos com
-- `not exists`, catálogo com a guarda `not (valor @> …)`.
--
-- Tarefa: custo operacional por cliente (2026-08-05)
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. o vínculo passa a ser único por lado ─────────────────────────────────
drop index if exists categorias_vinculo_uidx;

create unique index if not exists categorias_vinculo_tipo_uidx
  on categorias (vinculo, tipo)
  where vinculo is not null and arquivada_em is null;

comment on index categorias_vinculo_tipo_uidx is
  'RF-58: um lado de receita e um lado de despesa por vínculo. É o que deixa dominio/espelho_subcategoria.py responder "em qual categoria nasce o espelho de receita deste cliente?" sem ambiguidade.';

alter table categorias drop constraint if exists categorias_especial_tem_lado;
alter table categorias add constraint categorias_especial_tem_lado
  check (not especial or tipo <> 'ambas');

-- ── 2. um espelho por (categoria, dono) ─────────────────────────────────────
-- Antes bastava "um espelho por dono", e `espelho_subcategoria.cria` conferia isso
-- com um `scalar_one_or_none`. Com dois espelhos por cliente aquilo estouraria; a
-- unicidade que continua valendo é esta, e é ela que o `on conflict do nothing` da
-- criação usa.
create unique index if not exists subcategorias_cliente_categoria_uidx
  on subcategorias (categoria_id, cliente_id) where cliente_id is not null;

create unique index if not exists subcategorias_funcionario_categoria_uidx
  on subcategorias (categoria_id, funcionario_id) where funcionario_id is not null;

-- ── 3. "Custos Operacionais" vira a categoria especial de custo do cliente ──
-- Resolvida por nome **uma única vez, aqui**: seed é dado, e é o único lugar onde
-- nomear a categoria é legítimo. Daqui para a frente todo mundo resolve por
-- `vinculo` + `tipo` (`FR-079`).
do $$
declare
  cat_custos uuid;
  espelhos   int;
begin
  select id into cat_custos
    from categorias
   where lower(nome) = 'custos operacionais' and arquivada_em is null;

  if cat_custos is null then
    insert into categorias (nome, cor, icone, tipo, especial, vinculo, ordem)
    values ('Custos Operacionais', '#D64545', 'receipt', 'despesa', true, 'cliente', 10)
    returning id into cat_custos;
  else
    update categorias
       set especial = true, vinculo = 'cliente', tipo = 'despesa'
     where id = cat_custos;
  end if;

  -- O espelho de cliente arquivado nasce arquivado: ele espelha o cadastro, e um
  -- cliente arquivado não pode voltar a aparecer nos formulários pela porta dos
  -- custos.
  insert into subcategorias (categoria_id, nome, cliente_id, arquivada_em)
  select cat_custos, cl.nome, cl.id, cl.arquivado_em
    from clientes cl
   where not exists (
     select 1 from subcategorias s
      where s.categoria_id = cat_custos and s.cliente_id = cl.id
   );

  get diagnostics espelhos = row_count;
  raise notice 'RF-58: categoria % promovida, % espelhos de cliente criados.',
               cat_custos, espelhos;
end $$;

-- ── 4. o bloco do Dashboard entra no catálogo ───────────────────────────────
-- `FR-106` proíbe rótulo de card escrito no frontend, e a grade ignora em silêncio
-- todo id que o catálogo não declara — sem esta parte o componente existiria e
-- nunca seria desenhado (foi o que aconteceu com `receita_servico` até a `013`).
--
-- Posição 18, logo depois de "Clientes" (17): custo do cliente lê junto do
-- faturamento do cliente. "Funcionários" (18→19) e "Próximos 7 dias" (19→20)
-- descem uma casa. Preferência de usuário não é tocada — ela mora em
-- `usuarios.preferencias` e vence o catálogo no desempate.
update configuracoes
   set valor = (
         select jsonb_agg(entrada order by (entrada ->> 'ordem_padrao')::int)
         from (
           select case
                    when item ->> 'id' in ('bloco_funcionarios', 'linha_tempo_7_dias')
                    then jsonb_set(item, '{ordem_padrao}',
                                   to_jsonb(((item ->> 'ordem_padrao')::int) + 1))
                    else item
                  end as entrada
             from jsonb_array_elements(valor) as item

           union all

           select '{"id": "bloco_custos_cliente", "rotulo": "Custos por cliente",
                    "grupo": "especial", "ordem_padrao": 18, "visivel_padrao": true,
                    "requisito": "RF-58"}'::jsonb
         ) as entradas
       ),
       atualizado_em = now()
 where chave = 'dashboard_cards_disponiveis'
   and not (valor @> '[{"id": "bloco_custos_cliente"}]'::jsonb);
