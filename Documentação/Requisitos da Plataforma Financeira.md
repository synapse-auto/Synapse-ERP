---
aliases:
  - Requisitos da Plataforma Financeira
  - ERP Financeiro Synapse
cliente: Synapse (uso interno)
projeto: Plataforma Financeira / ERP
documento: Requisitos e Regras de Negócio
versao: 0.2
status: Em construção — refinando com o Lucas
data: 2026-07-27
tags:
  - requisitos
  - financeiro
  - erp
  - interno
---

# Requisitos — Plataforma Financeira Synapse

> **Produto:** plataforma interna de gestão financeira (mini-ERP) da Synapse.
> **Objetivo:** controlar entradas e saídas, programar lançamentos, enxergar a saúde do caixa num dashboard — com atenção especial a **Clientes** (quem paga) e **Funcionários** (quem custa).
> **Filosofia:** projeto simples, mas com a mesma mentalidade da Base PAI — modular, nada hardcoded, máximo reuso de componentes prontos (shadcn, Reui, templates famosos) e inspiração em ERPs open-source consagrados (Akaunting, ERPNext, Firefly III).

> **Legenda dos códigos**
> `RF` = Requisito Funcional · `RN` = Regra de Negócio · `RNF` = Requisito Não Funcional.
> **Prioridade:** 🔴 Crítico · 🟠 Alta · 🟢 Média.

---

## 1. Visão geral e navegação

### 1.1. Divisão por Mundo — Toggle Global 🔴

O sistema opera com dois **mundos** financeiros independentes dentro da mesma empresa:

| Mundo | Escopo |
| --- | --- |
| **Synapse Digital** | Serviços digitais: CRM, Automação com IA, Desenvolvimento Web. |
| **Synapse Infra** | Serviços físicos: Redes, Segurança, Energia Solar, Ar Condicionados, Painéis de LED, Racks. |

**RF-100 — Toggle de mundo (header global).** 🔴 Na parte superior do site (header), toggle com 3 estados: **Digital** · **Infra** · **Ambos**. Sempre visível, persiste entre navegações.

**RF-101 — Filtragem global por mundo.** 🔴 Ao trocar o toggle, **todo o sistema** se adapta:
- **Dashboard:** cards, gráficos e totais mostram apenas dados do mundo selecionado (ou consolidado em "Ambos").
- **Lançamentos:** lista filtrada pelo mundo. Filtros modulares incluem "mundo" como dimensão.
- **Extrato:** idem, resumo e timeline filtrados.
- **Clientes:** só clientes do mundo selecionado.
- **Funcionários:** só funcionários do mundo selecionado.
- **Relatórios:** DRE, variação mensal, ranking de clientes — tudo filtrado pelo mundo.
- **Notificações/alertas:** alertas de vencimento e inadimplência respeitam o mundo ativo.

**RF-102 — "Ambos" = visão consolidada.** 🟠 No modo "Ambos", o sistema exibe todos os dados unificados, com indicação visual de qual mundo cada item pertence (badge/cor). Cards do Dashboard mostram totais consolidados, e os gráficos por serviço já separam naturalmente (cada serviço pertence a um mundo).

**RF-103 — Mundo no cadastro.** 🔴 Todo formulário de criação (lançamento, cliente, funcionário, serviço vinculado, centro de custo) tem um campo **"Mundo"** com toggle Digital/Infra. Default: o mundo selecionado no toggle global no momento da criação.

**RF-104 — Categorias são compartilhadas.** 🔴 Categorias e subcategorias **não** são divididas por mundo — existem uma única vez e servem para ambos. Evita duplicação de categorias.

**RN-15 — Todo registro tem mundo.** 🔴 Qualquer entidade do sistema (exceto categorias) possui o campo `mundo` (`digital` | `infra`). Este campo é obrigatório e imutável após criação (para mudar, excluir e recriar). Garante a separação total dos dados financeiros entre os dois braços do negócio.

**RN-16 — Caixa por mundo.** 🟠 Saldo do caixa é calculado separadamente por mundo. No modo "Ambos", mostra saldo consolidado + breakdown Digital/Infra. O card "Saúde do caixa" (`RF-46b`) calcula o semáforo por mundo no modo filtrado, e consolidado no modo "Ambos".

### 1.2. Mapa de navegação (menu)

- **HEADER:** Toggle de Mundo (Digital · Infra · Ambos)
- **MENU:** Dashboard · Lançamentos · Extrato · Categorias
- **GESTÃO:** Clientes · Funcionários · Relatórios
- **RODAPÉ:** Configurações · Perfil do usuário

> Estrutura de aba lateral e posição de Configurações/Perfil inspiradas no claude.ai, igual ao padrão já usado no CRM da Estrutural.

### 1.3. Conceitos centrais (vocabulário)

| Conceito | Definição |
| --- | --- |
| **Mundo** | Divisão operacional da Synapse: **Digital** (serviços digitais) ou **Infra** (serviços físicos). Todo dado financeiro pertence a um mundo. Categorias são a única exceção — compartilhadas entre ambos. |
| **Lançamento** | Qualquer movimentação financeira: **receita** (entrada) ou **despesa** (saída). Pertence a um mundo. |
| **Lançamento programado** | Lançamento com data futura, criado antes de acontecer. Efetiva automaticamente na data (ou exige confirmação, ver `RF-17`). |
| **Lançamento recorrente** | Regra que gera lançamentos automaticamente em intervalo fixo (ex.: salário todo dia 5, mensalidade de cliente todo dia 10). |
| **Categoria / Subcategoria** | Classificação em dois níveis. Compartilhada entre mundos. Todo lançamento tem 1 categoria e opcionalmente 1 subcategoria. |
| **Categoria especial** | Categoria com comportamento programado no sistema (cards próprios, telas próprias). Atuais: **Clientes** e **Funcionários**. |
| **Tag** | Rótulo livre (cor + texto) para classificação cruzada. Um lançamento pode ter N tags. Não substitui categoria — complementa. |
| **Serviço vinculado** | Qual serviço da Synapse gerou aquele lançamento. Cada serviço pertence a um mundo (CRM → Digital, Redes → Infra). Alimenta métricas de receita/custo por serviço. |
| **Centro de custo** | Agrupamento transversal por projeto ou cliente grande. Pertence a um mundo. |
| **Caixa** | Visão única de caixa por mundo — saldo calculado separadamente para Digital e Infra. |
| **Status do lançamento** | `Programado` · `Pendente` · `Efetivado` · `Atrasado` · `Cancelado` (ver `RN-03`). |

---

## 2. Papéis e permissões

Três usuários iniciais: Lucas (gestor), sócio (gestor) e contadora (operadora — precisa criar lançamentos).

| Papel | Descrição |
| --- | --- |
| **Gestor** | Acesso total: CRUD lançamentos, categorias, relatórios, configurações, gerenciar usuários. Lucas e sócio. |
| **Operador** | CRUD de lançamentos + visualização de extrato/relatórios. Sem acesso a configurações e gestão de usuários. Contadora. |
| **Visualizador** | (futuro) Só leitura de dashboard e relatórios. |

**RF-01 — Autenticação.** 🔴 Login individual por usuário com sessão segura.
**RF-02 — RBAC ativo.** 🔴 Permissões por papel desde o início. Gestores gerenciam usuários e papéis.
**RF-03 — Auditoria por usuário.** 🟠 Todo lançamento registra quem criou/editou/excluiu + timestamp. Timeline de alterações visível no detalhe do lançamento.

---

## 3. Aba **Lançamentos** (gestão) 🔴

Núcleo operacional: criar, editar, remover e programar lançamentos.

### 3.1. CRUD

**RF-10 — Criar lançamento.** 🔴 Formulário com:
- Tipo (receita/despesa)
- **Valor** (em BRL ou USD — ver `RN-12`)
- **Descrição**
- **Data**
- **Categoria + subcategoria**
- **Serviço vinculado** (opcional — qual serviço da Synapse: CRM, Automação, Solar, Redes, Segurança, Racks, LED, Ar, Web)
- **Centro de custo** (opcional — projeto ou cliente grande)
- **Tags** (livres, N por lançamento)
- Status
- Observações (campo de texto longo)
- **Anexos** (comprovante, NF, contrato — múltiplos arquivos, imagem/PDF)
**RF-11 — Criação rápida.** 🟠 Atalho de "novo lançamento" acessível de qualquer aba (botão global + atalho de teclado). Formulário enxuto com defaults inteligentes (data = hoje, última categoria usada).
**RF-12 — Editar e remover.** 🔴 Edição completa e exclusão com confirmação. Exclusão é **soft delete** (lixeira/restauração — ver `RN-08`).
**RF-13 — Duplicar lançamento.** 🟠 Ação "duplicar" cria cópia com data = hoje e valor preenchido, pronto pra ajustar.
**RF-13a — Split de lançamento.** 🟠 Dividir 1 lançamento em várias categorias. Ex: pagamento de R$500 = R$300 Infraestrutura + R$200 Ferramentas. O sistema mantém o vínculo entre as partes (lançamento-pai). Cada parte tem categoria/subcategoria própria mas compartilha data, descrição e anexos.
**RF-13b — Criação em lote.** 🟠 Criar vários lançamentos de uma vez: formulário com tabela inline (linhas editáveis) para popular múltiplos lançamentos sem sair da tela. Complementa a importação CSV (`RF-21`) para inserção manual rápida.

### 3.2. Programação e recorrência

**RF-14 — Lançamento programado.** 🔴 Criar lançamento com data futura. Aparece nas listas como `Programado` e entra nas projeções de caixa.
**RF-15 — Lançamento recorrente.** 🔴 Regra de recorrência: frequência (semanal, mensal, anual, a cada X dias), dia do vencimento, data de fim opcional (ou nº de parcelas). O sistema gera as ocorrências automaticamente.
**RF-16 — Parcelamento.** 🟠 Lançamento parcelado (ex.: projeto de R$ 12.000 em 3x) gera N lançamentos vinculados, com numeração "2/3" na descrição.
**RF-17 — Efetivação configurável por lançamento.** 🟠 Cada lançamento programado/recorrente tem um checkbox **"Efetivar automaticamente"** (default: ativado). Se ativado, efetiva sozinho na data. Se desativado, vira `Pendente` na data e exige confirmação manual (1 clique).
**RF-17a — Data de início retroativa.** 🔴 Ao criar lançamento recorrente, campo "data de início" (default: hoje). Se a data for no passado, o sistema gera automaticamente todas as ocorrências entre a data de início e hoje, já como `Efetivado` — contabilizando o histórico real da empresa.

### 3.3. Lista e ações

**RF-18 — Tabela de lançamentos.** 🔴 Lista paginada com colunas: data, descrição, categoria/subcategoria (com cor/ícone), serviço vinculado, tags, status, valor (verde receita / vermelho despesa). Ordenável por qualquer coluna.
**RF-19 — Filtros modulares.** 🟠 Filtros combináveis: período, tipo, categoria, subcategoria, serviço vinculado, centro de custo, tags, status, faixa de valor, texto livre. Contador de resultados em tempo real.
**RF-20 — Ações em massa.** 🟠 Selecionar vários lançamentos e: excluir, mudar categoria, mudar status, adicionar/remover tags, exportar.
**RF-21 — Importação CSV/OFX.** 🟢 Importar lançamentos de planilha (CSV) e extrato bancário (OFX), com tela de mapeamento de colunas e sugestão de categoria.
**RF-22 — Exportação.** 🟢 Exportar a lista filtrada em CSV.
**RF-23 — Interações padrão.** 🟠 Um clique → aba lateral com detalhes completos do lançamento (anexos, histórico de edições, recorrência-mãe, tags, serviço vinculado, centro de custo); duplo clique → edição.

---

## 4. Aba **Extrato** (visualização + resumo) 🟠

Visão de leitura rápida — "o que entrou e saiu", sem fricção de gestão.

**RF-30 — Linha do tempo de lançamentos.** 🟠 Lançamentos agrupados por dia/semana/mês, estilo extrato bancário, com saldo acumulado ao fim de cada grupo.
**RF-31 — Cabeçalho-resumo do período.** 🟠 No topo, para o período filtrado: **total de receitas**, **total de despesas**, **resultado** (receitas − despesas) e **saldo final**. Com comparativo vs. período anterior (▲/▼ %).
**RF-32 — Filtro de período rápido.** 🟠 Chips: Hoje · Esta semana · Este mês · Mês passado · Este ano · Personalizado.
**RF-33 — Mini-gráfico do período.** 🟢 Gráfico compacto de barras (receita × despesa por dia/mês) acima da lista.
**RF-34 — Pendências em destaque.** 🟠 Seção fixa "A pagar / A receber": lançamentos `Pendente` e `Atrasado` dos próximos dias, com badge vermelho se houver vencidos.

---

## 5. Aba **Dashboard** 🔴

Regra de ouro: **5–8 cards principais acima da dobra, todo número com comparativo, todo card clicável (drill-down para a lista filtrada)**.

### 5.1. Controles globais

**RF-40 — Filtro de período global.** 🔴 Seletor de período que afeta todos os cards. Chips rápidos: Este mês · Mês passado · Últimos 3 meses · Este ano · Personalizado.
**RF-48 — Dashboard configurável.** 🟢 Mostrar/ocultar/reordenar cards (padrão *widgets* do Akaunting). Nada de posição hardcoded.

### 5.2. Cards de resumo financeiro

**RF-41 — Cards principais.** 🔴
1. **Saldo atual** do caixa
2. **Receitas do período** (+ comparativo vs. período anterior ▲/▼ %)
3. **Despesas do período** (+ comparativo)
4. **Lucro líquido do período** (receitas − despesas, card destaque verde/vermelho)
5. **Margem operacional %** (lucro ÷ receita × 100 — quanto sobra de cada R$1 faturado)
6. **A receber** (pendentes + programados do período)
7. **A pagar** (pendentes + programados do período)
**RF-47 — Sparklines nos cards.** 🟢 Mini-gráfico de tendência (últimas 4–12 semanas) dentro de cada card numérico.

### 5.3. Gráficos e análises

**RF-42 — Fluxo de caixa mensal.** 🔴 Barras de receitas × despesas × resultado por mês (últimos 12 meses), incluindo **projeção** dos meses futuros com base em programados/recorrentes (linha tracejada).
**RF-42a — Evolução do saldo.** 🟠 Gráfico de linha: saldo final de cada mês nos últimos 12 meses. Mostra tendência de acúmulo ou queima de caixa.
**RF-42b — Comparativo mês atual vs. anterior.** 🟠 Barras lado a lado: receita e despesa do mês atual comparadas com mês anterior, com ▲/▼ %.
**RF-43 — Despesas por categoria.** 🟠 Gráfico de rosca/barras do período, clicável (drill-down filtra Lançamentos).
**RF-43a — Top 5 maiores despesas.** 🟠 Ranking visual dos 5 lançamentos de maior valor no período. Cada item clicável.
**RF-43b — Receita por serviço.** 🟠 Gráfico de barras/rosca: quanto cada serviço da Synapse gerou de receita no período (baseado no campo "serviço vinculado" dos lançamentos). Permite ver quais linhas de negócio são mais rentáveis.

### 5.4. Cards especiais (categorias programadas)

**RF-44 — Card especial Clientes.** 🔴 Card dedicado à categoria especial **Clientes**:
- Total recebido no período (+ comparativo)
- Top 5 clientes por receita
- Nº de clientes ativos
- **Alerta de inadimplência**: destaque vermelho com nome e valor de clientes com pagamento `Atrasado`
**RF-45 — Card especial Funcionários.** 🔴 Card dedicado à categoria especial **Funcionários**:
- Custo total do período (+ comparativo)
- Custo por funcionário
- % da folha sobre despesas totais
- Próximos pagamentos programados

### 5.5. Cards de acompanhamento

**RF-46 — Próximos 7 dias.** 🟠 Timeline compacta dos lançamentos que vencem nos próximos 7 dias — pagar e receber, separados visualmente.
**RF-46a — Alerta de contas vencidas.** 🔴 Banner/card vermelho fixo no topo do dashboard quando existir qualquer lançamento `Atrasado`. Mostra quantidade e valor total vencido. Clicável → filtra Lançamentos por status `Atrasado`.
**RF-46b — Card "Saúde do caixa".** 🟠 Semáforo visual (verde/amarelo/vermelho):
- 🟢 Saldo cobre as despesas fixas dos próximos 30 dias com folga (> 1.5×)
- 🟡 Saldo cobre mas sem folga (1× a 1.5×)
- 🔴 Saldo **não** cobre as despesas fixas projetadas (< 1×)
O cálculo usa despesas recorrentes + programadas dos próximos 30 dias vs. saldo atual.

---

## 6. Aba **Categorias** 🟠

**RF-50 — CRUD de categorias.** 🟠 Criar, editar, arquivar categorias com: nome, **cor**, **ícone**, tipo (receita, despesa ou ambas).
**RF-51 — Subcategorias.** 🟠 Cada categoria pode ter N subcategorias (2 níveis, sem sub-sub — simplicidade).
**RF-52 — Visão de uso.** 🟢 Na lista, cada categoria mostra: nº de lançamentos e total movimentado no período.
**RF-53 — Mesclar/mover.** 🟢 Mover lançamentos de uma categoria para outra ao arquivar (nunca deixar lançamento órfão — `RN-06`).
**RF-54 — Categorias padrão (seed).** 🟢 Sistema nasce com um conjunto inicial editável: Clientes, Funcionários, Infraestrutura, Ferramentas/Assinaturas, Impostos, Marketing, Equipamentos, Transporte, Outros.

### 6.1. Categorias especiais 🔴

**RF-55 — Categoria especial "Clientes".** 🔴 Categoria de **receita** programada no sistema:
- Subcategoria = **cliente** (cadastro próprio — ver aba Clientes, §7).
- Ganha card especial no Dashboard (`RF-44`) e página de perfil por cliente.
- Lançamentos nela alimentam métricas de receita por cliente e inadimplência.
**RF-56 — Categoria especial "Funcionários".** 🔴 Categoria de **despesa** programada no sistema:
- Subcategoria = **funcionário** (cadastro próprio — ver §8).
- Ganha card especial no Dashboard (`RF-45`) e página de perfil por funcionário.
**RF-57 — Extensível.** 🟠 Arquitetura permite promover qualquer categoria a "especial" no futuro (ex.: "Assinaturas" com card de custo recorrente mensal). Comportamento especial = configuração, não código novo.

---

## 7. Aba **Clientes** (gestão da categoria especial) 🟠

**RF-60 — Cadastro de cliente.** 🟠 Nome, empresa, contato, tags de serviço contratado (CRM, automação, solar...), tipo de cobrança (pontual, recorrente, parcelado) e valor/dia da recorrência quando houver.
**RF-61 — Perfil do cliente.** 🟠 Página por cliente: total recebido (histórico e por período), gráfico de receita mensal, lista de lançamentos, próximos recebimentos programados, status (em dia / atrasado).
**RF-62 — Recorrência vinculada.** 🟠 Cliente recorrente gera automaticamente o lançamento programado da mensalidade (integra `RF-15`).
**RF-63 — Alerta de inadimplência.** 🟠 Pagamento esperado não efetivado até X dias após o vencimento → cliente marcado `Atrasado` e destacado no Dashboard (`RF-44`, `RF-46a`) e no topo da lista de clientes (ver `RN-10`).

---

## 8. Aba **Funcionários** 🟠

**RF-65 — Cadastro de funcionário.** 🟠 Nome, função, tipo (PJ/freelancer), valor do pagamento mensal, dia de pagamento.

**Funcionários atuais:**
- **Dylan** — Automação com n8n e IA — R$ 1.200,00/mês
- **Marcondes** — Java e Engenharia de Software — R$ 900,00/mês

**RF-66 — Perfil do funcionário.** 🟠 Custo total (histórico e por período), lista de pagamentos, próximos pagamentos programados.
**RF-67 — Folha automática.** 🟠 Funcionário cadastrado gera automaticamente a despesa recorrente mensal (integra `RF-15`). Extras (bônus, comissão, vale) entram como lançamentos avulsos na mesma subcategoria.

---

## 9. Aba **Relatórios** 🟠

**RF-70 — DRE simplificado.** 🟠 Demonstrativo de Resultado simplificado:
- (+) Receita bruta (total por categoria de receita)
- (−) Despesas (total por categoria de despesa, com breakdown por subcategoria)
- (=) Lucro/Prejuízo
Exibição mensal + acumulado no ano. Comparativo com período anterior.
**RF-71 — Relatório por cliente.** 🟠 Ranking de clientes por receita no período. Para cada cliente: total recebido, % do faturamento total, status (em dia / atrasado), evolução mensal.
**RF-72 — Variação mensal por categoria.** 🟠 Tabela meses × categorias com valor e **% de variação** mês a mês. Destaque visual em variações > 20% (positivas ou negativas) para identificar anomalias rápido.
**RF-73 — Comparativo mensal geral.** 🟢 Matriz meses × categorias com totais (padrão Akaunting/Firefly). Mais granular que RF-72 — mostra todos os valores, sem foco na variação.
**RF-74 — Exportação PDF/CSV.** 🟢 Qualquer relatório exportável em PDF (formatado) ou CSV (dados brutos).

---

## 10. Notificações e Alertas 🟠

**RF-80 — Alerta de vencimento.** 🟠 Notificação no sistema X dias antes de um lançamento vencer. Dias configuráveis (default: 1, 3 e 7 dias antes).
**RF-81 — Alerta de inadimplência.** 🟠 Quando pagamento de cliente não for efetivado até X dias após o vencimento (config, default 3), alerta destacado no Dashboard (`RF-46a`) e no perfil do cliente (`RF-63`).
**RF-82 — Resumo semanal.** 🟠 Relatório automático semanal (toda segunda): "Sua semana: R$X entrou, R$Y saiu, saldo R$Z, N pendências". Entregue por notificação no sistema (expansível para e-mail no futuro).
**RF-83 — Alerta de caixa baixo (semanal).** 🟠 Todo início de semana, se o saldo atual não cobrir as despesas fixas dos próximos 7 dias, alerta destacado. Complementa o card "Saúde do caixa" (`RF-46b`) que olha 30 dias — este foca no curto prazo semanal.

---

## 11. Regras de Negócio

**RN-01 — Todo lançamento tem categoria.** 🔴 Sem categoria não salva. Subcategoria opcional, **exceto** nas categorias especiais: lançamento em Clientes/Funcionários **exige** a subcategoria (qual cliente / qual funcionário).
**RN-02 — Valor sempre positivo + tipo.** 🟠 O sinal vem do tipo (receita/despesa), nunca digitado. Moeda padrão: BRL (ver `RN-12` para USD).
**RN-03 — Ciclo de status.** 🔴
- `Programado` → (chegou a data) → efetiva automaticamente → `Efetivado`.
- Se algo impedir a efetivação (ex: cancelado antes) → `Cancelado` (mantém histórico).
- Lançamento de cliente não confirmado manualmente (receita esperada não recebida) após o vencimento → `Atrasado` (automático, ver `RN-10`).
**RN-04 — Efetivação configurável.** 🟠 Cada lançamento programado/recorrente define via checkbox se efetiva automático ou exige confirmação manual. Default: automático. Lançamentos com confirmação manual viram `Pendente` na data e ficam destacados no Extrato (`RF-34`) e Dashboard (`RF-46`) até serem confirmados.
**RN-05 — Só `Efetivado` conta no realizado.** 🔴 Saldos e totais realizados consideram apenas `Efetivado`. `Programado` entra apenas em **projeções** e nos cards "A pagar/A receber" — sempre visualmente distintos (ex.: linha tracejada, cor atenuada).
**RN-05a — Data de início retroativa.** 🔴 Recorrência com data de início no passado gera ocorrências históricas já `Efetivadas`. Permite popular o sistema com meses anteriores de operação real.
**RN-06 — Nunca lançamento órfão.** 🟠 Arquivar categoria/subcategoria com lançamentos exige destino (mesclar) ou mantém vínculo somente-leitura. Cliente/funcionário desligado é **arquivado**, nunca excluído — histórico é sagrado.
**RN-07 — Edição de recorrência.** 🟠 Ao editar lançamento gerado por recorrência, perguntar: "só este" ou "este e os futuros" (padrão Google Agenda). Ocorrências passadas nunca mudam retroativamente.
**RN-08 — Soft delete + auditoria.** 🟠 Exclusões vão para lixeira (restauráveis por 90 dias). Toda criação/edição/exclusão registra quem, quando e o quê (timeline no detalhe do lançamento).
**RN-09 — Datas: competência = caixa na v1.** 🟢 Uma data só por lançamento (quando o dinheiro se move). Regime de competência fica para v2.
**RN-10 — Inadimplência.** 🟠 Cliente com lançamento `Atrasado` há mais de X dias (config, default 3) aparece no card de alerta do Dashboard (`RF-46a`), no card Clientes (`RF-44`) e no topo da lista de clientes.
**RN-11 — Split mantém integridade.** 🟠 Lançamento com split (`RF-13a`): a soma das partes = valor total do lançamento-pai. Editar o valor de uma parte recalcula ou exige ajuste manual da outra.
**RN-12 — Moeda estrangeira (USD → BRL).** 🟠 O formulário de lançamento aceita valor em **USD** (dólar americano) além de BRL. Ao salvar lançamento em USD:
- O sistema consulta **API pública de câmbio** (ex.: AwesomeAPI, Banco Central) para obter a cotação do dia.
- O valor é **convertido automaticamente para BRL** e armazenado assim.
- O lançamento registra: valor original em USD, cotação usada e valor convertido em BRL.
- **Todo o restante do sistema** (saldos, cards, relatórios, DRE) opera **exclusivamente em BRL**. A moeda estrangeira é apenas uma conveniência de entrada.
**RN-13 — Centro de custo é opcional.** 🟢 Centro de custo não é obrigatório. Lançamento sem centro de custo = "geral". Relatórios por centro de custo só aparecem se houver ao menos 1 centro cadastrado.
**RN-14 — Tags são livres.** 🟢 Tags não têm hierarquia e são reutilizáveis. Servem para filtros e agrupamentos ad-hoc. Cor + nome. Sem limite por lançamento.

---

## 12. Requisitos Não Funcionais

**RNF-01 — Máximo reuso.** 🔴 Preferir componentes/telas prontos e consagrados: shadcn/ui, Reui, templates de dashboard financeiro open-source. Copiar abas inteiras quando fizer sentido e adaptar. Inspiração de arquitetura: Akaunting (Laravel/Vue), Firefly III, ERPNext — estudar antes de codar.
**RNF-02 — Nada hardcoded.** 🔴 Nomes de cards, cores, textos, limites (dias de inadimplência, dias de projeção, limiar do semáforo de saúde) vivem em configuração — herança direta da filosofia Base PAI.
**RNF-03 — PT-BR + BRL.** 🔴 Interface em português, valores em R$ com formatação brasileira (1.234,56), datas dd/mm/aaaa. Entrada em USD convertida automaticamente (`RN-12`).
**RNF-04 — Design sob medida.** 🟠 Front moderno, sem cara de "template de IA". Aba lateral estilo claude.ai (padrão da casa).
**RNF-05 — Responsivo.** 🟠 Desktop primeiro; Dashboard e Extrato utilizáveis no celular (conferir o caixa de qualquer lugar).
**RNF-06 — Backup dos dados.** 🟠 Dados financeiros com backup automático e exportação completa a qualquer momento (propriedade total dos dados).
**RNF-07 — Performance.** 🟢 Listas com milhares de lançamentos sem travar (paginação/virtualização).
**RNF-08 — Empresa única (Synapse).** 🟢 Sem multi-empresa. Modelo focado e simples.
**RNF-09 — Tema claro/escuro.** 🟠 Suporte a dark mode e light mode, alternável nas configurações ou por preferência do sistema. Todos os cards, gráficos e tabelas devem funcionar bem em ambos os temas.
**RNF-10 — Atalhos de teclado.** 🟢 Atalhos para ações frequentes:
- `N` ou `Ctrl+N` → novo lançamento (criação rápida)
- `Ctrl+K` → busca global
- `1–7` → navegar entre abas do menu
- `Esc` → fechar aba lateral / modal

---

## 13. Configurações 🟠

**RF-90 — Tela de configurações.** 🟠 Acesso restrito a gestores. Inclui:
- **Serviços da Synapse** — lista editável dos serviços para o campo "serviço vinculado" dos lançamentos. Seed inicial: CRM, Automação com IA, Infraestrutura de Redes, Segurança, Energia Solar, Ar Condicionados, Painéis de LED, Montagem de Racks, Desenvolvimento Web.
- **Centros de custo** — CRUD de centros de custo / projetos.
- **Tags** — gerenciar tags globais (nome + cor).
- **Inadimplência** — dias de tolerância antes de marcar cliente como atrasado (default: 3).
- **Saúde do caixa** — multiplicadores do semáforo (default: 1× e 1.5× despesas fixas).
- **Notificações** — dias de antecedência dos alertas de vencimento (default: 1, 3, 7).
- **Tema** — claro / escuro / automático.
- **Gestão de usuários** — convidar, editar papel, desativar.

---

## 14. Fora de escopo da v1 (anotado para não esquecer)

- Multi-empresa (Lumina separada).
- Emissão de nota fiscal / boletos / integração bancária (Open Finance).
- Conciliação bancária automática.
- Contabilidade formal (partidas dobradas, plano de contas contábil).
- Orçamentos (budget por categoria com variação real vs. planejado) — candidato forte a v2.
- Metas financeiras.
- Múltiplas contas/carteiras bancárias com saldo por conta.
- Multi-moeda completa (só USD→BRL de entrada na v1).

---

## 15. Decisões confirmadas (Lucas, 2026-07-27)

1. **Caixa único** — sem separação por contas bancárias.
2. **Só Synapse** — sem multi-empresa.
3. **3 usuários:** Lucas (gestor), sócio (gestor), contadora (operadora — faz lançamentos).
4. **Clientes recorrentes existem** — mensalidades ativas. Data de início retroativa essencial para popular histórico.
5. **2 funcionários:** Dylan (n8n/IA, R$1.200/mês), Marcondes (Java, R$900/mês).
6. **Efetivação automática por padrão** — checkbox por lançamento; default ativado, desativável quando quiser confirmação manual.
7. **USD → BRL** — entrada em dólar convertida via API pública; todo o sistema opera em real.
