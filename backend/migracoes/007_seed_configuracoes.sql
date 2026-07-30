-- 007_seed_configuracoes.sql
-- Seed da tabela `configuracoes` — data-model.md §3.15
--
-- É esta migração que materializa o Princípio VII e RNF-02/FR-106: rótulo de card, cor,
-- limite, prazo e multiplicador vêm daqui, nunca do meio do código.
--
-- ⚠️ Contagem: data-model §3.15 tem 16 LINHAS de tabela, mas a última linha declara DUAS
-- chaves (`cambio_fonte_primaria` e `cambio_fonte_alternativa`). Logo são **17 chaves**, e
-- não 16. quickstart.md §3 e a task T015 diziam 16 — corrigido na mesma entrega (Princípio V).
--
-- `on conflict do nothing`: a migração pode ser reaplicada sem sobrescrever valor que o
-- gestor já ajustou pela tela (FR-105).
--
-- Tarefa: T015

insert into configuracoes (chave, valor, descricao) values

  ('inadimplencia_dias_tolerancia',
   '3'::jsonb,
   'Dias de atraso tolerados antes de o cliente ser considerado inadimplente (RF-81, RN-10). Mudar aqui reavalia todos os clientes na hora, porque a situação é derivada e não gravada.'),

  ('saude_caixa_multiplicadores',
   '{"minimo": 1.0, "folga": 1.5}'::jsonb,
   'Semáforo de saúde do caixa (RF-46b): verde acima de folga, amarelo entre os dois, vermelho abaixo de minimo — multiplicado pelas despesas fixas do horizonte.'),

  ('saude_caixa_horizonte_dias',
   '30'::jsonb,
   'Janela de despesas fixas futuras que o semáforo de saúde do caixa considera (RF-46b).'),

  ('caixa_baixo_horizonte_dias',
   '7'::jsonb,
   'Janela usada pelo alerta semanal de caixa baixo (RF-83, FR-099).'),

  ('alerta_vencimento_dias',
   '[1, 3, 7]'::jsonb,
   'Antecedências, em dias, em que a rotina diária avisa de vencimento (RF-80, FR-096).'),

  ('lixeira_retencao_dias',
   '90'::jsonb,
   'Prazo para restaurar da lixeira (RN-08). Passado o prazo a restauração é recusada, mas a linha NUNCA é apagada — histórico financeiro é permanente.'),

  ('anexo_tamanho_max_mb',
   '10'::jsonb,
   'Tamanho máximo de anexo em megabytes. Acima disso o upload responde 413 arquivo_grande (FR-013).'),

  ('anexo_mime_permitidos',
   '["image/png", "image/jpeg", "image/webp", "application/pdf"]'::jsonb,
   'Formatos de anexo aceitos. Fora da lista, o upload responde 415 formato_nao_suportado (FR-013).'),

  ('variacao_destaque_percentual',
   '20'::jsonb,
   'Percentual de variação mensal a partir do qual a categoria é destacada no relatório (RF-72, FR-092). Nunca fixo em 20 no código.'),

  ('recorrencia_horizonte_meses',
   '12'::jsonb,
   'Até quantos meses à frente as ocorrências futuras de uma recorrência são materializadas. Recorrência sem fim não gera linhas infinitas (data-model §3.13).'),

  ('recorrencia_aviso_ocorrencias',
   '24'::jsonb,
   'A partir de quantas ocorrências a criação de recorrência exige confirmação explícita, respondendo 422 confirmacao_necessaria com a prévia (FR-027).'),

  ('tema_padrao',
   '"auto"'::jsonb,
   'Tema de quem ainda não escolheu: claro | escuro | auto (FR-109).'),

  ('efetivacao_automatica_padrao',
   'true'::jsonb,
   'Valor padrão do campo "efetivar automaticamente" em lançamento novo (RF-17). Com true, o lançamento se efetiva na data e nunca fica atrasado.'),

  ('efetivacao_automatica_padrao_receita_cliente',
   'false'::jsonb,
   'Padrão específico de receita de cliente (D-05). Fica false de propósito: o alerta de inadimplência só existe se a efetivação for manual, porque só assim o lançamento pode ficar atrasado (RN-03, FR-115).'),

  ('cambio_fonte_primaria',
   '"awesomeapi"'::jsonb,
   'Primeira fonte consultada para a cotação USD→BRL da data do lançamento (RN-12).'),

  ('cambio_fonte_alternativa',
   '"bcb_ptax"'::jsonb,
   'Fonte consultada quando a primária falha. Se as duas falharem, o sistema exige cotação manual e grava cotacao_manual = true (RN-12).'),

  -- FR-106 / FR-071 / RF-48: rótulo, grupo e ordem de CADA card do Dashboard vivem aqui.
  -- Nenhum texto de card no código do frontend — T175 monta a grade a partir desta lista,
  -- resolvendo o componente por `id`.
  --   grupo: numerico | grafico | especial | alerta
  ('dashboard_cards_disponiveis',
   '[
      {"id": "saldo_atual",          "rotulo": "Saldo atual",              "grupo": "numerico", "ordem_padrao":  1, "visivel_padrao": true,  "requisito": "FR-054"},
      {"id": "receitas_periodo",     "rotulo": "Receitas do período",      "grupo": "numerico", "ordem_padrao":  2, "visivel_padrao": true,  "requisito": "FR-054"},
      {"id": "despesas_periodo",     "rotulo": "Despesas do período",      "grupo": "numerico", "ordem_padrao":  3, "visivel_padrao": true,  "requisito": "FR-054"},
      {"id": "lucro_liquido",        "rotulo": "Lucro líquido",            "grupo": "numerico", "ordem_padrao":  4, "visivel_padrao": true,  "requisito": "FR-054"},
      {"id": "margem_operacional",   "rotulo": "Margem operacional",       "grupo": "numerico", "ordem_padrao":  5, "visivel_padrao": true,  "requisito": "FR-054"},
      {"id": "a_receber",            "rotulo": "A receber",                "grupo": "numerico", "ordem_padrao":  6, "visivel_padrao": true,  "requisito": "FR-054, FR-056"},
      {"id": "a_pagar",              "rotulo": "A pagar",                  "grupo": "numerico", "ordem_padrao":  7, "visivel_padrao": true,  "requisito": "FR-054, FR-056"},
      {"id": "alerta_atrasados",     "rotulo": "Lançamentos atrasados",    "grupo": "alerta",   "ordem_padrao":  8, "visivel_padrao": true,  "requisito": "FR-068"},
      {"id": "saude_caixa",          "rotulo": "Saúde do caixa",           "grupo": "especial", "ordem_padrao":  9, "visivel_padrao": true,  "requisito": "FR-069"},
      {"id": "resumo_periodo",       "rotulo": "Resumo do período",        "grupo": "especial", "ordem_padrao": 10, "visivel_padrao": true,  "requisito": "FR-070"},
      {"id": "fluxo_caixa_12m",      "rotulo": "Fluxo de caixa (12 meses)","grupo": "grafico",  "ordem_padrao": 11, "visivel_padrao": true,  "requisito": "FR-059"},
      {"id": "evolucao_saldo",       "rotulo": "Evolução do saldo",        "grupo": "grafico",  "ordem_padrao": 12, "visivel_padrao": true,  "requisito": "FR-060"},
      {"id": "comparativo_mensal",   "rotulo": "Mês atual x anterior",     "grupo": "grafico",  "ordem_padrao": 13, "visivel_padrao": true,  "requisito": "FR-061"},
      {"id": "despesas_categoria",   "rotulo": "Despesas por categoria",   "grupo": "grafico",  "ordem_padrao": 14, "visivel_padrao": true,  "requisito": "FR-062"},
      {"id": "top_despesas",         "rotulo": "Maiores despesas",         "grupo": "grafico",  "ordem_padrao": 15, "visivel_padrao": true,  "requisito": "FR-063"},
      {"id": "bloco_clientes",       "rotulo": "Clientes",                 "grupo": "especial", "ordem_padrao": 16, "visivel_padrao": true,  "requisito": "FR-065"},
      {"id": "bloco_funcionarios",   "rotulo": "Funcionários",             "grupo": "especial", "ordem_padrao": 17, "visivel_padrao": true,  "requisito": "FR-066"},
      {"id": "linha_tempo_7_dias",   "rotulo": "Próximos 7 dias",          "grupo": "especial", "ordem_padrao": 18, "visivel_padrao": true,  "requisito": "FR-067"}
    ]'::jsonb,
   'RF-48/FR-071/FR-106: rótulo, grupo e ordem padrão de cada card. Os blocos de Clientes e Funcionários são resolvidos por categorias.vinculo, nunca por comparação de nome (FR-079).')

on conflict (chave) do nothing;
