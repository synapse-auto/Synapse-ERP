# Feature Specification: Plataforma Financeira Synapse (ERP interno v1)

**Feature Branch**: `001-erp-financeiro-synapse` (diretório de spec; repositório git ainda não iniciado)

**Created**: 2026-07-29

**Status**: Pronta para planejamento — 0 perguntas em aberto (as 3 pendências foram
respondidas pelo dono do projeto em 2026-07-29; ver §"Decisões resolvidas")

**Input**: User description: "Tudo que eu preciso nesse novo projeto está em `Documentação/Requisitos da Plataforma Financeira.md` — esse é o arquivo principal do projeto inteiro. Analisar em profundidade. Analisar também o UI Mockup do Claude Design: https://claude.ai/design/p/f5d2a73f-43fc-4d92-b46a-b3ef8d637164"

**Fontes analisadas**:

- `Documentação/Requisitos da Plataforma Financeira.md` (v0.2, 2026-07-27) — documento-mestre. Cada requisito abaixo cita o código de origem (`RF-xx`, `RN-xx`, `RNF-xx`).
- `.specify/memory/constitution.md` (v1.0.0) — princípios não-negociáveis do projeto.
- Mockup Claude Design "Synapse ERP Financeiro" — 10 telas navegáveis + "Synapse Design System". Itens derivados só do mockup estão marcados com `(mockup)`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar o dinheiro que entra e sai (Priority: P1)

Lucas (gestor) ou a contadora (operadora) abre o sistema e registra uma movimentação: recebeu de um cliente, pagou uma ferramenta, comprou um equipamento. Escolhe tipo, valor, data, categoria e subcategoria, opcionalmente serviço vinculado, centro de custo, tags, observações e anexos (nota fiscal, comprovante). Depois encontra qualquer lançamento numa lista filtrável, abre o detalhe num clique e edita num duplo clique.

**Why this priority**: sem registro não existe produto. É o núcleo operacional (§3 do documento-mestre) e a base de todos os números do resto do sistema.

**Independent Test**: criar 20 lançamentos variados (receita e despesa, com e sem anexo, com e sem tag), filtrar por categoria e período, editar um, excluir outro e restaurá-lo da lixeira. Já entrega valor sozinho: substitui a planilha.

**Acceptance Scenarios**:

1. **Given** o formulário de novo lançamento aberto, **When** o usuário preenche tipo, valor, data e categoria e salva, **Then** o lançamento aparece na lista com valor em verde (receita) ou vermelho (despesa) e entra nos totais do período.
2. **Given** um lançamento em categoria comum, **When** o usuário deixa a subcategoria vazia, **Then** o sistema salva normalmente.
3. **Given** um lançamento na categoria especial "Clientes", **When** o usuário tenta salvar sem escolher qual cliente, **Then** o sistema bloqueia e sinaliza que a subcategoria é obrigatória.
4. **Given** um lançamento salvo, **When** o usuário clica uma vez na linha, **Then** abre o painel de detalhe com valor, classificação, programação, anexos, observações e histórico de alterações.
5. **Given** um lançamento salvo, **When** o usuário exclui e confirma, **Then** ele some das listas e dos totais, mas continua recuperável na lixeira.
6. **Given** um valor informado em dólar, **When** o usuário salva, **Then** o sistema grava o valor convertido em reais e registra também o valor original em USD e a cotação usada.

---

### User Story 2 - Separar Synapse Digital de Synapse Infra (Priority: P1)

A Synapse opera dois braços com finanças independentes: Digital (CRM, automação com IA, desenvolvimento web) e Infra (redes, segurança, energia solar, ar condicionado, LED, racks). O gestor troca o mundo num seletor no topo e o sistema inteiro se adapta — dashboard, lançamentos, extrato, clientes, funcionários, relatórios e alertas. No modo "Ambos" vê tudo consolidado, com indicação de qual mundo cada item pertence.

**Why this priority**: é uma dimensão obrigatória de todo registro (`RN-15`) e imutável depois de criado. Se entrar depois, todos os dados já cadastrados ficam sem mundo.

**Independent Test**: cadastrar dados nos dois mundos, alternar o seletor entre Digital, Infra e Ambos e verificar que nenhum número do mundo oposto aparece quando filtrado, e que "Ambos" mostra a soma correta com quebra por mundo.

**Acceptance Scenarios**:

1. **Given** o seletor em "Digital", **When** o usuário navega para qualquer tela, **Then** só aparecem dados do mundo Digital e o saldo exibido é o saldo do Digital.
2. **Given** o seletor em "Ambos", **When** o usuário olha o card de saldo, **Then** vê o total consolidado e, abaixo, a quebra Digital / Infra.
3. **Given** o seletor em "Infra", **When** o usuário cria um lançamento, **Then** o campo mundo já vem preenchido com "Infra".
4. **Given** um lançamento já salvo, **When** o usuário tenta alterar o mundo dele, **Then** o sistema não permite e explica que é preciso excluir e recriar.
5. **Given** o seletor em "Digital", **When** o usuário abre Categorias, **Then** vê a lista completa de categorias (elas são compartilhadas), mas os valores e contagens exibidos são só do Digital.
6. **Given** um cliente que fatura nos dois mundos e o seletor em "Digital", **When** o usuário abre a lista de clientes, **Then** o cliente aparece com apenas os valores do Digital — o cadastro é único e compartilhado, a movimentação é que separa.

---

### User Story 3 - Programar o futuro e recuperar o histórico (Priority: P1)

O gestor cria mensalidades de clientes e salários que se repetem sozinhos, contas com data futura e projetos parcelados. Ao cadastrar uma recorrência com data de início no passado, o sistema gera todas as ocorrências históricas já como efetivadas — é assim que os meses anteriores de operação real entram no sistema.

**Why this priority**: sem isso o sistema nasce vazio e exige digitação manual de meses de histórico. É o que torna os números confiáveis desde o primeiro dia.

**Independent Test**: criar uma recorrência mensal de R$ 1.200 com início 5 meses atrás; conferir que foram geradas 5 ocorrências efetivadas mais as futuras programadas, e que o saldo bate com o histórico real.

**Acceptance Scenarios**:

1. **Given** uma recorrência mensal com início retroativo de 5 meses, **When** o usuário salva, **Then** o sistema gera as ocorrências passadas como `Efetivado` e avisa antes de salvar quantas serão criadas.
2. **Given** um lançamento programado com "efetivar automaticamente" ligado, **When** chega a data, **Then** ele vira `Efetivado` sozinho e passa a contar no saldo.
3. **Given** um lançamento programado com "efetivar automaticamente" desligado, **When** chega a data, **Then** ele vira `Pendente`, não conta no saldo e aparece em destaque no Extrato e no Dashboard até alguém confirmar com um clique.
4. **Given** um lançamento gerado por recorrência, **When** o usuário edita, **Then** o sistema pergunta "só este" ou "este e os futuros", e ocorrências passadas nunca mudam.
5. **Given** um projeto de R$ 12.000 em 3x, **When** o usuário salva o parcelamento, **Then** o sistema cria 3 lançamentos vinculados identificados como 1/3, 2/3 e 3/3.
6. **Given** um lançamento não efetivado, **When** a data de vencimento passa, **Then** o status muda para `Atrasado`.

---

### User Story 4 - Ver a saúde do caixa num relance (Priority: P1)

Lucas abre o Dashboard e em segundos entende: quanto tem em caixa, quanto entrou e saiu no período, se o mês deu lucro, qual a margem, o que tem a receber e a pagar, se alguma conta venceu e se o caixa cobre as despesas fixas dos próximos 30 dias. Todo número tem comparativo com o período anterior e todo card leva para a lista filtrada correspondente.

**Why this priority**: é a razão de o produto existir — enxergar a saúde do caixa sem montar planilha.

**Independent Test**: com dados de 12 meses carregados, abrir o Dashboard e conferir que cada card bate com o cálculo manual, que o semáforo de saúde reflete a regra de multiplicadores e que clicar num card leva à lista filtrada certa.

**Acceptance Scenarios**:

1. **Given** dados do mês atual e do anterior, **When** o Dashboard carrega, **Then** cada card numérico mostra o valor do período e a variação percentual contra o período anterior.
2. **Given** existe pelo menos um lançamento `Atrasado`, **When** o Dashboard carrega, **Then** aparece um alerta vermelho fixo no topo com quantidade e valor total vencido, clicável para a lista filtrada por `Atrasado`.
3. **Given** o saldo cobre 1,8× as despesas fixas dos próximos 30 dias, **When** o usuário olha o card "Saúde do caixa", **Then** o semáforo está verde e o texto explica em quantas vezes o saldo cobre essas despesas.
4. **Given** existem lançamentos programados e recorrentes futuros, **When** o usuário olha o gráfico de fluxo de caixa mensal, **Then** os meses futuros aparecem como projeção visualmente distinta dos meses realizados.
5. **Given** o usuário clica numa fatia do gráfico de despesas por categoria, **Then** o sistema abre Lançamentos já filtrado por aquela categoria e período.
6. **Given** o usuário quer outro arranjo, **When** entra em "Configurar cards", **Then** consegue mostrar, ocultar e reordenar os cards, e a escolha persiste.

---

### User Story 5 - Acompanhar quem paga (Clientes) (Priority: P2)

O gestor cadastra clientes, define se a cobrança é pontual, recorrente ou parcelada, e o sistema passa a gerar as mensalidades sozinho. Cada cliente tem um perfil com total recebido, evolução mensal, lançamentos e próximos recebimentos. Quem atrasa além da tolerância configurada aparece destacado no Dashboard e no topo da lista de clientes.

**Why this priority**: "Clientes" é categoria especial e o lado da receita — mas depende do núcleo de lançamentos já existir.

**Independent Test**: cadastrar 3 clientes (um recorrente), deixar um pagamento vencer além da tolerância e verificar que ele aparece marcado como atrasado no Dashboard, na lista e no perfil.

**Acceptance Scenarios**:

1. **Given** um cliente com cobrança recorrente de R$ 2.000 todo dia 10, **When** o cadastro é salvo, **Then** o sistema passa a gerar automaticamente o lançamento programado da mensalidade.
2. **Given** um pagamento esperado não efetivado, **When** passam mais dias que a tolerância configurada (padrão 3), **Then** o cliente é marcado como `Atrasado` e destacado no Dashboard, no card Clientes e no topo da lista de clientes.
3. **Given** um cliente com histórico, **When** o usuário abre o perfil dele, **Then** vê total recebido, gráfico de receita mensal, lista de lançamentos, próximos recebimentos e o status atual.
4. **Given** um cliente que encerrou contrato, **When** o usuário o desliga, **Then** ele é arquivado e o histórico financeiro continua intacto e consultável.

---

### User Story 6 - Acompanhar quanto custa a equipe (Funcionários) (Priority: P2)

O gestor cadastra cada funcionário (nome, função, tipo PJ/freelancer, valor mensal, dia de pagamento) e o sistema cria sozinho a despesa recorrente. O Dashboard mostra a folha do período, quanto ela representa da despesa total e os próximos pagamentos. Bônus, comissões e vales entram como lançamentos avulsos na mesma subcategoria.

**Why this priority**: é a maior despesa fixa recorrente e a segunda categoria especial. Depende do núcleo e da recorrência.

**Independent Test**: cadastrar Dylan (R$ 1.200/mês) e Marcondes (R$ 900/mês), conferir que a folha recorrente é gerada, que a folha do mês soma R$ 2.100 e que o perfil de cada um lista os pagamentos.

**Acceptance Scenarios**:

1. **Given** um funcionário cadastrado com valor mensal e dia de pagamento, **When** o cadastro é salvo, **Then** a despesa recorrente mensal passa a ser gerada automaticamente.
2. **Given** funcionários cadastrados, **When** o usuário olha o card Funcionários no Dashboard, **Then** vê o custo total do período, o comparativo, o custo por funcionário, o percentual da folha sobre as despesas totais e a data e valor da próxima folha.
3. **Given** um bônus pago fora da folha, **When** o usuário registra como lançamento avulso na subcategoria do funcionário, **Then** ele soma ao custo daquele funcionário no período.
4. **Given** um funcionário desligado, **When** o usuário o desliga, **Then** ele é arquivado (nunca excluído) e a recorrência para de gerar novas ocorrências.

---

### User Story 7 - Ler o extrato do período (Priority: P2)

O gestor quer a leitura rápida, sem fricção de gestão: o que entrou e o que saiu, agrupado por dia, semana ou mês, com saldo acumulado ao fim de cada grupo, como um extrato bancário. No topo, o resumo do período com comparativo, e uma seção fixa "A pagar / A receber" com o que está pendente e atrasado.

**Why this priority**: é leitura sobre dados que já existem — valor alto, esforço baixo, mas não bloqueia nada.

**Independent Test**: escolher "Este mês", conferir que a soma dos grupos bate com o cabeçalho-resumo e que o saldo acumulado do último grupo é igual ao saldo final do período.

**Acceptance Scenarios**:

1. **Given** um período selecionado, **When** o Extrato carrega, **Then** o cabeçalho mostra total de receitas, total de despesas, resultado e saldo final, cada um com variação contra o período anterior.
2. **Given** a lista agrupada por dia, **When** o usuário troca para "Por semana" ou "Por mês", **Then** o agrupamento e os saldos acumulados se reorganizam.
3. **Given** existem lançamentos futuros no período, **When** eles aparecem na linha do tempo, **Then** são visualmente marcados como previstos e não somam ao saldo realizado.
4. **Given** existem pendências, **When** o usuário olha a seção "A pagar / A receber", **Then** vê os lançamentos pendentes e atrasados dos próximos dias, com destaque vermelho para os vencidos.

---

### User Story 8 - Fechar o mês com relatórios (Priority: P3)

No fim do mês o gestor (ou a contadora) abre Relatórios e tira: o DRE simplificado do mês e do acumulado do ano, o ranking de clientes por receita, a variação mensal por categoria com destaque automático em variações acima de 20%, e exporta tudo em PDF ou CSV.

**Why this priority**: fecha o ciclo de gestão, mas é consumo de dados já registrados.

**Independent Test**: gerar o DRE de um mês fechado e conferir contra a soma manual das categorias; exportar em CSV e verificar que os números batem.

**Acceptance Scenarios**:

1. **Given** um período fechado, **When** o usuário abre o DRE, **Then** vê receita bruta por categoria, despesas por categoria com quebra por subcategoria, e o lucro ou prejuízo resultante, mensal e acumulado no ano.
2. **Given** clientes com receita no período, **When** o usuário abre o relatório por cliente, **Then** vê o ranking com total recebido, percentual do faturamento, status e evolução mensal de cada um.
3. **Given** uma categoria que variou 35% contra o mês anterior, **When** o usuário abre a variação mensal, **Then** aquela célula aparece destacada visualmente.
4. **Given** qualquer relatório na tela, **When** o usuário exporta, **Then** recebe um PDF formatado ou um CSV com os dados brutos correspondentes ao que está sendo exibido.

---

### User Story 9 - Ser avisado antes do problema (Priority: P3)

O sistema avisa: contas a vencer com dias de antecedência configuráveis, clientes inadimplentes, resumo semanal toda segunda ("entrou X, saiu Y, saldo Z, N pendências") e alerta de caixa baixo quando o saldo não cobre as despesas fixas da semana.

**Why this priority**: transforma o sistema de passivo em ativo, mas depende de todos os dados anteriores existirem.

**Independent Test**: criar uma conta que vence em 3 dias e verificar que a notificação aparece; deixar um cliente ultrapassar a tolerância e verificar o alerta de inadimplência.

**Acceptance Scenarios**:

1. **Given** um lançamento que vence em 3 dias e a antecedência configurada inclui 3 dias, **When** o dia chega, **Then** o usuário recebe a notificação no sistema.
2. **Given** um cliente que ultrapassou a tolerância de inadimplência, **When** o alerta dispara, **Then** ele aparece no Dashboard e no perfil do cliente.
3. **Given** é segunda-feira, **When** o resumo semanal é gerado, **Then** o usuário recebe entrada, saída, saldo e número de pendências da semana anterior.
4. **Given** o saldo não cobre as despesas fixas dos próximos 7 dias, **When** a verificação semanal roda, **Then** o alerta de caixa baixo aparece destacado.

---

### User Story 10 - Trabalhar com papéis diferentes e configurar sem código (Priority: P3)

Cada pessoa entra com o próprio login. Lucas e o sócio são gestores (acesso total). A contadora é operadora: cria e edita lançamentos, vê extrato e relatórios, mas não entra em configurações nem gerencia usuários. Nas configurações, os gestores editam serviços da Synapse, centros de custo, tags, tolerância de inadimplência, limiares do semáforo, dias de antecedência dos alertas, tema e usuários — nada disso é fixo no código.

**Why this priority**: o acesso individual e a auditoria por usuário são exigidos desde o início; a tela de configuração consolida o que já é configurável nas outras histórias.

**Independent Test**: entrar como operadora e confirmar que Configurações não está acessível; alterar a tolerância de inadimplência de 3 para 7 dias e verificar que o comportamento dos alertas muda sem alteração de código.

**Acceptance Scenarios**:

1. **Given** um usuário com papel operador, **When** ele tenta acessar Configurações ou gestão de usuários, **Then** o acesso é negado.
2. **Given** um gestor alterou a tolerância de inadimplência para 7 dias, **When** um pagamento atrasa 5 dias, **Then** o cliente ainda não é marcado como inadimplente.
3. **Given** um gestor adicionou um novo serviço da Synapse, **When** alguém cria um lançamento, **Then** o novo serviço aparece na lista de serviços vinculados.
4. **Given** qualquer lançamento, **When** o usuário abre o histórico de alterações, **Then** vê quem criou, quem editou, o que mudou e quando.
5. **Given** o usuário escolhe tema escuro, **When** navega pelo sistema, **Then** todas as telas, cards, gráficos e tabelas ficam legíveis no tema escolhido.

---

### Edge Cases

- **Recorrência retroativa muito longa**: início 3 anos atrás gera dezenas de ocorrências de uma vez. O sistema mostra a quantidade antes de confirmar e não trava a interface durante a geração.
- **Recorrência em dia inexistente**: mensal "todo dia 31" em fevereiro — a ocorrência cai no último dia do mês.
- **Cotação de câmbio indisponível**: a fonte pública de cotação não responde na hora de salvar um lançamento em dólar.
- **Lançamento em dólar com data passada**: a cotação usada é a da data do lançamento, não a de hoje.
- **Divisão que não fecha**: as partes somam menos ou mais que o lançamento-pai (`RN-11`).
- **Arquivar categoria com lançamentos**: não pode deixar lançamento órfão — exige destino ou mantém vínculo somente-leitura (`RN-06`).
- **Cliente ou funcionário desligado com lançamentos futuros programados**: o que acontece com as ocorrências ainda não efetivadas.
- **Excluir um lançamento gerado por recorrência**: afeta só aquela ocorrência, nunca a série.
- **Restaurar da lixeira depois de 90 dias**: o item já não está mais disponível.
- **Editar valor de ocorrência passada já efetivada**: muda saldos históricos — exige confirmação explícita e fica registrado na auditoria.
- **Dois usuários editando o mesmo lançamento ao mesmo tempo**: a última alteração não pode apagar silenciosamente a anterior sem registro.
- **Lista com milhares de lançamentos**: rolagem e filtros continuam responsivos (`RNF-07`).
- **Anexo grande ou formato não suportado**: o sistema recusa com mensagem clara em vez de falhar em silêncio.
- **Período sem nenhum dado**: cards, gráficos e listas mostram estado vazio explicativo, nunca um número ambíguo ou tela quebrada. *(mockup: "Nada previsto")*
- **Seletor em "Ambos" com dado só de um mundo**: a quebra por mundo mostra o mundo vazio com zero, não some da tela.
- **Cliente cadastrado sem nenhum lançamento**: como o filtro de clientes por mundo é derivado da movimentação (`FR-002`), ele não pertence a mundo nenhum ainda — aparece nos três estados do seletor.
- **Saldo antes de o histórico estar completo**: sem saldo inicial (`FR-114`), o caixa mostra menos que o extrato bancário real até a carga histórica terminar, e o semáforo de saúde fica pessimista. Estado esperado, não defeito.
- **Mensalidade de cliente com efetivação automática ligada**: ela se efetiva na data mesmo sem o dinheiro ter entrado e nunca vira `Atrasado` — o alerta de inadimplência não dispara para esse cliente (`FR-115`).
- **Mudança de tolerância de inadimplência**: clientes já marcados são reavaliados com a nova regra.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Mundos (Digital / Infra)

- **FR-001**: O sistema MUST oferecer um seletor de mundo permanente no topo com três estados — Digital, Infra e Ambos — visível em todas as telas e mantido entre navegações e sessões. (`RF-100`)
- **FR-002**: Ao trocar o mundo selecionado, o sistema MUST refiltrar Dashboard, Lançamentos, Extrato, Clientes, Funcionários, Relatórios e alertas, sem exibir nenhum dado do mundo não selecionado. Para Clientes, o filtro MUST ser derivado da movimentação (cliente com lançamento no mundo selecionado), já que o cadastro de cliente não tem mundo próprio — ver `FR-116`. (`RF-101`)
- **FR-003**: No modo "Ambos", o sistema MUST exibir os dados unificados com identificação visual do mundo de cada item e totais consolidados. (`RF-102`)
- **FR-004**: Todo formulário de criação de entidade financeira MUST conter um campo de mundo, preenchido por padrão com o mundo ativo no seletor global. (`RF-103`)
- **FR-005**: Toda entidade do sistema MUST ter mundo obrigatório e imutável após a criação; alterar exige excluir e recriar. São exceções, sem campo de mundo: categorias, subcategorias e o cadastro de cliente (`FR-116`). (`RN-15`)
- **FR-006**: Categorias, subcategorias e cadastros de cliente MUST existir uma única vez e servir aos dois mundos, sem duplicação. (`RF-104`, `FR-116`)
- **FR-007**: O saldo de caixa MUST ser calculado separadamente por mundo; no modo "Ambos" o sistema MUST exibir o consolidado e a quebra Digital / Infra. (`RN-16`)

#### Lançamentos — registro

- **FR-008**: Usuários MUST conseguir criar um lançamento com: tipo (receita ou despesa), valor, descrição, data, categoria, subcategoria, serviço vinculado, centro de custo, tags, status, observações e anexos. (`RF-10`)
- **FR-009**: O valor MUST ser sempre informado como número positivo; o sinal MUST vir do tipo do lançamento, nunca digitado. (`RN-02`)
- **FR-010**: Todo lançamento MUST ter categoria. Subcategoria é opcional, exceto em categorias especiais, onde MUST ser obrigatória. (`RN-01`)
- **FR-011**: O sistema MUST aceitar valor em dólar americano além de real; ao salvar, MUST converter para real usando a cotação da data do lançamento obtida de fonte pública de câmbio, armazenar o valor convertido e registrar valor original, cotação usada e moeda de origem. (`RN-12`)
- **FR-012**: Todo o restante do sistema — saldos, cards, gráficos, relatórios e DRE — MUST operar exclusivamente em real. (`RN-12`, `RNF-03`)
- **FR-013**: O sistema MUST aceitar múltiplos anexos por lançamento em formato de imagem ou PDF (comprovante, nota fiscal, contrato). (`RF-10`)
- **FR-014**: Usuários MUST conseguir criar um lançamento a partir de qualquer tela, por botão global e por atalho de teclado, com formulário enxuto e valores padrão inteligentes (data igual a hoje, última categoria usada). (`RF-11`)
- **FR-015**: O formulário de criação MUST oferecer a ação "salvar e criar outro", que salva e reabre o formulário limpo para lançamento em sequência. *(mockup)*
- **FR-016**: Usuários MUST conseguir editar qualquer campo de um lançamento e excluí-lo mediante confirmação. (`RF-12`)
- **FR-017**: A exclusão MUST ser reversível: itens excluídos vão para uma lixeira e podem ser restaurados por 90 dias. (`RN-08`)
- **FR-018**: Usuários MUST conseguir duplicar um lançamento, gerando uma cópia com data de hoje e valor preenchido. (`RF-13`)
- **FR-019**: Usuários MUST conseguir dividir um lançamento em várias partes com categorias e subcategorias próprias, mantendo o vínculo com o lançamento-pai e compartilhando data, descrição e anexos. (`RF-13a`)
- **FR-020**: A soma das partes de um lançamento dividido MUST ser sempre igual ao valor do lançamento-pai; o sistema MUST impedir salvar em estado inconsistente. (`RN-11`)
- **FR-021**: Usuários MUST conseguir criar vários lançamentos de uma vez por tabela editável na própria tela. (`RF-13b`)
- **FR-022**: O centro de custo MUST ser opcional; lançamento sem centro de custo é tratado como "geral". (`RN-13`)
- **FR-023**: Tags MUST ser livres, sem hierarquia, reutilizáveis, com nome e cor, e sem limite por lançamento. (`RN-14`)

#### Lançamentos — programação, recorrência e status

- **FR-024**: Usuários MUST conseguir criar lançamentos com data futura, que aparecem como `Programado` e entram nas projeções de caixa. (`RF-14`)
- **FR-025**: Usuários MUST conseguir criar regras de recorrência com frequência (semanal, mensal, anual, a cada X dias), dia de vencimento e término opcional por data ou número de parcelas; o sistema MUST gerar as ocorrências automaticamente. (`RF-15`)
- **FR-026**: Ao criar uma recorrência, o sistema MUST aceitar data de início retroativa e, nesse caso, gerar todas as ocorrências entre a data de início e hoje já como `Efetivado`. (`RF-17a`, `RN-05a`)
- **FR-027**: Antes de salvar uma recorrência retroativa, o sistema MUST informar quantas ocorrências históricas serão criadas e o intervalo coberto. *(mockup)*
- **FR-028**: Usuários MUST conseguir parcelar um lançamento em N vezes, gerando N lançamentos vinculados identificados pela posição na série (ex.: "2/3"). (`RF-16`)
- **FR-029**: Cada lançamento programado ou recorrente MUST ter a opção "efetivar automaticamente", ligada por padrão. O valor padrão MUST ser configurável — inclusive de forma distinta para receita de cliente, sem regra fixa no código (`FR-115`, `RNF-02`). (`RF-17`, `RN-04`)
- **FR-030**: Quando "efetivar automaticamente" está ligado, o lançamento MUST virar `Efetivado` sozinho na data. Quando está desligado, MUST virar `Pendente` na data e exigir confirmação manual de um clique. (`RF-17`, `RN-04`)
- **FR-031**: O sistema MUST suportar os status `Programado`, `Pendente`, `Efetivado`, `Atrasado` e `Cancelado`, seguindo o ciclo definido: programado vira efetivado na data; cancelado preserva o histórico. (`RN-03`)
- **FR-032**: Lançamento não efetivado após a data de vencimento MUST passar automaticamente para `Atrasado`, seja receita ou despesa. Como lançamentos com efetivação automática nunca chegam vencidos, `Atrasado` é alcançável somente por lançamentos com o checkbox desligado (`FR-115`). (`RN-03`, `RN-10`)
- **FR-033**: Saldos e totais realizados MUST considerar apenas lançamentos `Efetivado`. Programados entram somente em projeções e nos totais "A pagar" e "A receber", sempre visualmente distintos. (`RN-05`)
- **FR-034**: Ao editar um lançamento gerado por recorrência, o sistema MUST perguntar se a alteração vale só para aquela ocorrência ou também para as futuras; ocorrências passadas nunca mudam retroativamente por essa via. (`RN-07`)
- **FR-035**: Cada lançamento MUST registrar uma única data — a data em que o dinheiro se move. (`RN-09`)

#### Lançamentos — lista, busca e ações

- **FR-036**: O sistema MUST exibir os lançamentos em lista paginada com data, descrição, categoria e subcategoria (com cor), serviço vinculado, tags, status e valor com cor por tipo, ordenável por qualquer coluna. (`RF-18`)
- **FR-037**: A lista MUST oferecer filtros combináveis por período, tipo, categoria, subcategoria, serviço vinculado, centro de custo, tags, status, faixa de valor, mundo e texto livre, com contador de resultados em tempo real. (`RF-19`)
- **FR-038**: Com filtros aplicados, o sistema MUST exibir junto ao contador a soma de receitas, a soma de despesas e o resultado do conjunto filtrado. *(mockup)*
- **FR-039**: Os filtros ativos MUST ser exibidos como marcadores removíveis individualmente, com uma ação para limpar todos. *(mockup)*
- **FR-040**: Usuários MUST conseguir selecionar vários lançamentos e aplicar em massa: excluir, mudar categoria, mudar status, adicionar ou remover tags e exportar. (`RF-20`)
- **FR-041**: Um clique numa linha MUST abrir o detalhe completo do lançamento em painel lateral, com valor, moeda de origem quando houver, classificação, programação, anexos, observações e histórico de alterações; duplo clique MUST abrir a edição. (`RF-23`)
- **FR-042**: O painel de detalhe MUST oferecer as ações editar, duplicar, dividir e excluir, e — quando o lançamento estiver atrasado — a confirmação direta do recebimento ou pagamento. *(mockup)*
- **FR-043**: Um lançamento gerado por recorrência ou parcelamento MUST indicar a origem no detalhe e permitir navegar para a série completa. *(mockup)*
- **FR-044**: Usuários MUST conseguir importar lançamentos de planilha (CSV) e de extrato bancário (OFX), com mapeamento de colunas e sugestão de categoria. (`RF-21`)
- **FR-045**: Usuários MUST conseguir exportar a lista filtrada em CSV. (`RF-22`)
- **FR-046**: O sistema MUST oferecer busca global acessível por atalho de teclado, cobrindo lançamentos, clientes e categorias. (`RNF-10`, mockup)

#### Extrato

- **FR-047**: O Extrato MUST exibir os lançamentos agrupados por dia, semana ou mês, à escolha do usuário, com saldo acumulado ao fim de cada grupo. (`RF-30`)
- **FR-048**: O Extrato MUST exibir no topo, para o período filtrado, total de receitas, total de despesas, resultado e saldo final, cada um com comparativo percentual contra o período anterior. (`RF-31`)
- **FR-049**: O Extrato MUST oferecer seleção rápida de período: hoje, esta semana, este mês, mês passado, este ano e personalizado. (`RF-32`)
- **FR-050**: O Extrato MUST exibir um gráfico compacto de receitas contra despesas por dia ou mês acima da lista. (`RF-33`)
- **FR-051**: O Extrato MUST exibir uma seção fixa "A pagar / A receber" com os lançamentos pendentes e atrasados dos próximos dias, com destaque para os vencidos. (`RF-34`)
- **FR-052**: Grupos com data futura MUST ser marcados como previstos e não somar ao saldo realizado. *(mockup, `RN-05`)*

#### Dashboard

- **FR-053**: O Dashboard MUST ter um seletor de período que afeta todos os cards, com opções rápidas: este mês, mês passado, últimos 3 meses, este ano e personalizado. (`RF-40`)
- **FR-054**: O Dashboard MUST exibir os cards: saldo atual, receitas do período, despesas do período, lucro líquido do período, margem operacional, a receber e a pagar. (`RF-41`)
- **FR-055**: Todo card numérico MUST exibir comparativo com o período anterior em percentual e direção. (`RF-41`)
- **FR-056**: Os cards "A receber" e "A pagar" MUST detalhar a composição por situação (programado, aguardando confirmação, atrasado). *(mockup)*
- **FR-057**: Cards numéricos MUST exibir um mini-gráfico de tendência das últimas semanas ou meses. (`RF-47`)
- **FR-058**: Todo card MUST ser clicável e levar à lista já filtrada correspondente. (§5 do documento-mestre)
- **FR-059**: O Dashboard MUST exibir um gráfico de fluxo de caixa mensal com receitas, despesas e resultado dos últimos 12 meses, incluindo projeção dos meses futuros baseada em programados e recorrentes, visualmente distinta do realizado. (`RF-42`)
- **FR-060**: O Dashboard MUST exibir a evolução do saldo final de cada mês nos últimos 12 meses. (`RF-42a`)
- **FR-061**: O Dashboard MUST exibir o comparativo de receita e despesa do mês atual contra o mês anterior. (`RF-42b`)
- **FR-062**: O Dashboard MUST exibir a distribuição de despesas por categoria no período, clicável para a lista filtrada. (`RF-43`)
- **FR-063**: O Dashboard MUST exibir o ranking das 5 maiores despesas do período, cada item clicável para o lançamento. (`RF-43a`)
- **FR-064**: O Dashboard MUST exibir a receita por serviço da Synapse no período, com valor e percentual de cada linha de negócio. (`RF-43b`)
- **FR-065**: O Dashboard MUST exibir um card especial de Clientes com total recebido no período e comparativo, top 5 clientes por receita, número de clientes ativos e destaque vermelho para clientes com pagamento atrasado. (`RF-44`)
- **FR-066**: O Dashboard MUST exibir um card especial de Funcionários com custo total do período e comparativo, custo por funcionário, percentual da folha sobre as despesas totais e próximos pagamentos programados. (`RF-45`)
- **FR-067**: O Dashboard MUST exibir uma linha do tempo dos lançamentos que vencem nos próximos 7 dias, separando visualmente o que é a pagar do que é a receber. (`RF-46`)
- **FR-068**: Sempre que existir qualquer lançamento `Atrasado`, o Dashboard MUST exibir um alerta vermelho fixo no topo com quantidade e valor total vencido, clicável para a lista filtrada por `Atrasado`. (`RF-46a`)
- **FR-069**: O Dashboard MUST exibir um card "Saúde do caixa" com semáforo de três estados calculado sobre as despesas fixas dos próximos 30 dias: verde acima do multiplicador de folga, amarelo entre os dois multiplicadores, vermelho abaixo do multiplicador mínimo. Os multiplicadores MUST ser configuráveis (padrão 1× e 1,5×). (`RF-46b`, `RNF-02`)
- **FR-070**: O Dashboard MUST exibir um resumo em linguagem natural do período — resultado, margem e o principal ponto de atenção. *(mockup)*
- **FR-071**: Usuários MUST conseguir mostrar, ocultar e reordenar os cards do Dashboard, e a configuração MUST persistir por usuário. (`RF-48`, `RNF-02`)

#### Categorias

- **FR-072**: Usuários MUST conseguir criar, editar e arquivar categorias com nome, cor, ícone e tipo (receita, despesa ou ambas). (`RF-50`)
- **FR-073**: Cada categoria MUST aceitar N subcategorias, em exatamente dois níveis, sem sub-subcategorias. (`RF-51`)
- **FR-074**: A lista de categorias MUST exibir, para cada categoria, o número de lançamentos e o total movimentado no período — respeitando o mundo ativo. (`RF-52`, mockup)
- **FR-075**: Ao arquivar uma categoria ou subcategoria que possui lançamentos, o sistema MUST exigir um destino para mover os lançamentos ou manter o vínculo somente-leitura, nunca deixando lançamento órfão. (`RF-53`, `RN-06`)
- **FR-076**: O sistema MUST nascer com um conjunto inicial editável de categorias: Clientes, Funcionários, Infraestrutura, Ferramentas/Assinaturas, Impostos, Marketing, Equipamentos, Transporte e Outros. (`RF-54`)
- **FR-077**: O sistema MUST tratar "Clientes" como categoria especial de receita, cujas subcategorias são os clientes cadastrados, com card próprio no Dashboard e página de perfil por cliente. (`RF-55`)
- **FR-078**: O sistema MUST tratar "Funcionários" como categoria especial de despesa, cujas subcategorias são os funcionários cadastrados, com card próprio no Dashboard e página de perfil por funcionário. (`RF-56`)
- **FR-079**: Promover qualquer categoria a especial MUST ser uma operação de configuração, sem alteração de código. (`RF-57`, `RNF-02`)

#### Clientes

- **FR-080**: Usuários MUST conseguir cadastrar clientes com nome, empresa, contato, serviços contratados, tipo de cobrança (pontual, recorrente ou parcelada) e, quando recorrente, valor, dia de cobrança e em qual mundo a mensalidade gera lançamento. O cadastro MUST NOT ter campo de mundo — o mesmo cliente atende Digital e Infra (`FR-116`). (`RF-60`)
- **FR-081**: Cada cliente MUST ter uma página de perfil com total recebido histórico e por período, gráfico de receita mensal, lista de lançamentos, próximos recebimentos programados e status atual. (`RF-61`)
- **FR-082**: Cliente com cobrança recorrente MUST gerar automaticamente o lançamento programado da mensalidade, no mundo declarado no cadastro. Um cliente que paga nos dois mundos MUST poder ter uma recorrência por mundo. (`RF-62`, `FR-116`)
- **FR-082a**: O cadastro de cliente **recorrente** MUST aceitar um mês de início no passado ("cliente desde") e, nesse caso, gerar as ocorrências da mensalidade daquele mês até o mês atual **já efetivadas** (`RN-05a`), na mesma transação do cadastro. MUST recusar mês no futuro e mês além do limite configurado (`configuracoes.cliente_retroativo_meses_maximo`), MUST NOT oferecer o recurso em cobrança pontual ou parcelada, e mês corrente MUST se comportar como hoje — sem duplicar o mês. Existe porque não há saldo inicial (D-06): sem carregar o passado, o caixa de quem já tinha clientes nasce menor que a realidade. (`RF-64`, 2026-08-04)
- **FR-083**: Cliente cujo pagamento esperado não for efetivado além da tolerância configurada (padrão 3 dias) MUST ser marcado como atrasado e destacado no Dashboard, no card Clientes e no topo da lista de clientes. A detecção depende de a mensalidade estar em confirmação manual — mensalidade com efetivação automática nunca gera inadimplência (`FR-115`). (`RF-63`, `RN-10`)
- **FR-084**: Clientes desligados MUST ser arquivados, nunca excluídos, preservando todo o histórico financeiro. (`RN-06`)

#### Funcionários

- **FR-085**: Usuários MUST conseguir cadastrar funcionários com nome, função, tipo (PJ ou freelancer), valor do pagamento mensal e dia de pagamento. (`RF-65`)
- **FR-086**: O sistema MUST nascer com os dois funcionários atuais cadastrados: Dylan (automação com n8n e IA, R$ 1.200,00/mês) e Marcondes (Java e engenharia de software, R$ 900,00/mês). (`RF-65`)
- **FR-087**: Cada funcionário MUST ter uma página de perfil com custo total histórico e por período, lista de pagamentos e próximos pagamentos programados. (`RF-66`)
- **FR-088**: Funcionário cadastrado MUST gerar automaticamente a despesa recorrente mensal; extras (bônus, comissão, vale) entram como lançamentos avulsos na mesma subcategoria. (`RF-67`)
- **FR-089**: Funcionários desligados MUST ser arquivados, nunca excluídos. (`RN-06`)

#### Relatórios

- **FR-090**: O sistema MUST gerar um DRE simplificado com receita bruta por categoria, despesas por categoria com quebra por subcategoria e o lucro ou prejuízo resultante, exibido por mês e acumulado no ano, com comparativo contra o período anterior. (`RF-70`)
- **FR-091**: O sistema MUST gerar o ranking de clientes por receita no período, com total recebido, percentual do faturamento total, status e evolução mensal de cada cliente. (`RF-71`)
- **FR-092**: O sistema MUST gerar a tabela de variação mensal por categoria, com valor e percentual de variação mês a mês, destacando visualmente variações acima de 20% em qualquer direção. (`RF-72`)
- **FR-093**: O sistema MUST gerar a matriz comparativa de meses por categorias com todos os totais. (`RF-73`)
- **FR-094**: Qualquer relatório MUST ser exportável em PDF formatado ou CSV com os dados brutos. (`RF-74`)
- **FR-095**: A tela de relatórios MUST apresentar uma leitura do período em linguagem natural, resumindo o que os números mostram. *(mockup)*

#### Notificações e alertas

- **FR-096**: O sistema MUST notificar dentro da aplicação com antecedência configurável antes de um lançamento vencer (padrão: 1, 3 e 7 dias). (`RF-80`, `RNF-02`)
- **FR-097**: O sistema MUST alertar quando um pagamento de cliente ultrapassar a tolerância de inadimplência configurada, destacando no Dashboard e no perfil do cliente. (`RF-81`)
- **FR-098**: O sistema MUST gerar um resumo semanal toda segunda-feira com entradas, saídas, saldo e número de pendências da semana. (`RF-82`)
- **FR-099**: No início de cada semana, se o saldo atual não cobrir as despesas fixas dos próximos 7 dias, o sistema MUST exibir alerta de caixa baixo. (`RF-83`)
- **FR-100**: O sistema MUST indicar no topo da interface a quantidade de notificações não lidas. *(mockup)*

#### Acesso, papéis e auditoria

- **FR-101**: O sistema MUST exigir login individual por usuário com sessão segura. (`RF-01`)
- **FR-102**: O sistema MUST aplicar controle de acesso por papel desde o início: gestor (acesso total, incluindo configurações e gestão de usuários) e operador (criar e editar lançamentos, ver extrato e relatórios, sem acesso a configurações e gestão de usuários). (`RF-02`)
- **FR-103**: O sistema MUST registrar, em toda criação, edição e exclusão, quem fez, o que mudou e quando, exibindo a linha do tempo no detalhe do lançamento. (`RF-03`, `RN-08`)

#### Configurações

- **FR-104**: Gestores MUST conseguir gerenciar a lista de serviços da Synapse usada no campo "serviço vinculado", com dados iniciais: CRM, Automação com IA, Infraestrutura de Redes, Segurança, Energia Solar, Ar Condicionados, Painéis de LED, Montagem de Racks e Desenvolvimento Web. (`RF-90`)
- **FR-105**: Gestores MUST conseguir gerenciar centros de custo, tags globais, dias de tolerância de inadimplência, multiplicadores do semáforo de saúde do caixa, dias de antecedência dos alertas de vencimento, tema e usuários com seus papéis. (`RF-90`)
- **FR-106**: Nenhum rótulo de card, cor, texto, limite ou prazo MUST ser fixo no código — todos vêm de configuração ou de dados iniciais. (`RNF-02`)

#### Experiência de uso

- **FR-107**: A navegação MUST seguir a estrutura: seletor de mundo e de período no topo; menu lateral com Dashboard, Lançamentos, Extrato e Categorias; grupo Gestão com Clientes, Funcionários e Relatórios; e, no rodapé da lateral, Configurações e perfil do usuário. (§1.2, mockup)
- **FR-108**: A interface MUST estar 100% em português do Brasil, com valores em reais no formato brasileiro (1.234,56) e datas no formato dd/mm/aaaa. (`RNF-03`)
- **FR-109**: O sistema MUST suportar tema claro, escuro e automático, com todos os cards, gráficos e tabelas legíveis em ambos. (`RNF-09`)
- **FR-110**: O sistema MUST oferecer atalhos de teclado para as ações frequentes: novo lançamento, busca global, navegação entre abas do menu e fechar painel ou modal. (`RNF-10`)
- **FR-111**: Dashboard e Extrato MUST ser utilizáveis em tela de celular; as demais telas priorizam desktop. (`RNF-05`)
- **FR-112**: O sistema MUST permitir exportação completa dos dados a qualquer momento e manter backup automático. (`RNF-06`)
- **FR-113**: Listas com milhares de lançamentos MUST permanecer responsivas. (`RNF-07`)

#### Decisões resolvidas

Respondidas pelo dono do projeto em 2026-07-29. O detalhamento técnico e as consequências
estão em [research.md](./research.md) D-04, D-05 e D-06.

- **FR-114**: O sistema MUST NOT ter saldo inicial de caixa. O saldo de cada mundo é
  integralmente o resultado dos lançamentos `Efetivado` — não existe campo de saldo de
  abertura nem lançamento de abertura. **Consequência aceita**: o saldo só corresponde ao
  extrato bancário real depois que o histórico estiver completo no sistema, via recorrência
  retroativa (`RN-05a`) e importação (`RF-21`); até lá o card "Saldo atual" mostra menos que a
  realidade e o semáforo de saúde do caixa (`RF-46b`) fica pessimista. Ajuste posterior, se
  necessário, é um lançamento comum.
- **FR-115**: O sistema MUST NOT ter regra de efetivação especial para a categoria "Clientes".
  Vale o mecanismo já definido em `RF-17`/`RN-04` — o checkbox "efetivar automaticamente" por
  lançamento. Em consequência, `Atrasado` MUST ser alcançável **somente** por lançamentos com
  o checkbox desligado (os automáticos se efetivam na data e nunca vencem), e o alerta de
  inadimplência (`RF-63`, `RN-10`) MUST depender de a mensalidade do cliente ter o checkbox
  desligado. O valor padrão desse checkbox para receita de cliente MUST ser configurável
  (`RNF-02`), não fixo no código.
- **FR-116**: Um cliente MUST ser representado por um cadastro único, **sem** campo de mundo —
  quem carrega o mundo é cada lançamento dele. Isto abre uma segunda exceção documentada a
  `RN-15`, ao lado de categorias. **Consequência aceita**: o filtro "clientes do mundo ativo"
  de `RF-101` passa a ser derivado (clientes com movimentação no mundo selecionado), e cliente
  ainda sem nenhum lançamento aparece nos três estados do seletor. Em troca, o perfil do
  cliente e o ranking (`RF-71`) exibem a quebra por mundo. Cliente com cobrança recorrente
  MUST declarar em qual mundo a mensalidade gera lançamento.

### Key Entities

- **Mundo**: divisão operacional da Synapse — Digital ou Infra. Marca praticamente todo dado financeiro e é imutável após a criação do registro.
- **Lançamento**: uma movimentação financeira. Tipo (receita ou despesa), valor em reais, data, descrição, status, observações. Pertence a um mundo, a uma categoria e opcionalmente a uma subcategoria, serviço, centro de custo e tags. Pode ter anexos, valor de origem em moeda estrangeira, vínculo com uma recorrência, com uma série de parcelas ou com um lançamento-pai de divisão.
- **Regra de recorrência**: define frequência, dia de vencimento, data de início (possivelmente retroativa), término opcional e se as ocorrências se efetivam sozinhas. Gera lançamentos.
- **Série de parcelamento**: conjunto de lançamentos vinculados que representam um valor único dividido em N vezes, cada um com sua posição na série.
- **Divisão de lançamento**: relação entre um lançamento-pai e suas partes, cuja soma é sempre igual ao valor do pai.
- **Categoria**: classificação de primeiro nível, com nome, cor, ícone e tipo. Compartilhada entre os mundos. Pode ser marcada como especial.
- **Subcategoria**: classificação de segundo nível dentro de uma categoria. Nas categorias especiais, corresponde a um cliente ou a um funcionário.
- **Cliente**: quem paga. Nome, empresa, contato, serviços contratados, tipo de cobrança e condições de recorrência. **Não tem mundo** — é compartilhado entre Digital e Infra, como as categorias; o mundo vive nos lançamentos dele. Tem status de adimplência. Arquivável, nunca excluível.
- **Funcionário**: quem custa. Nome, função, tipo de contratação, valor mensal e dia de pagamento. Arquivável, nunca excluível.
- **Serviço da Synapse**: linha de negócio que originou o lançamento. Pertence a um mundo. Lista editável.
- **Centro de custo**: agrupamento transversal por projeto ou cliente grande. Opcional no lançamento.
- **Tag**: rótulo livre com nome e cor, sem hierarquia, reutilizável, N por lançamento.
- **Anexo**: arquivo de imagem ou PDF vinculado a um lançamento (nota fiscal, comprovante, contrato).
- **Usuário**: pessoa com login individual e um papel (gestor ou operador).
- **Registro de auditoria**: quem fez o quê, em qual registro e quando.
- **Notificação**: aviso gerado pelo sistema (vencimento, inadimplência, resumo semanal, caixa baixo), com estado de lida ou não lida.
- **Configuração**: parâmetros ajustáveis do sistema — tolerância de inadimplência, multiplicadores do semáforo, antecedências de alerta, tema, visibilidade e ordem dos cards.
- **Cotação de câmbio**: taxa usada na conversão de um valor em dólar para real, com a data de referência, guardada junto ao lançamento.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O usuário registra um lançamento completo (com categoria, serviço e anexo) em menos de 60 segundos, e um lançamento rápido em menos de 20 segundos.
- **SC-002**: Ao abrir o Dashboard, o gestor identifica em até 10 segundos se o mês está positivo ou negativo e se existe conta vencida, sem clicar em nada.
- **SC-003**: 100% dos lançamentos efetivados são refletidos no saldo e 0% dos lançamentos programados afetam o saldo realizado, verificado por conferência manual de um mês completo.
- **SC-004**: Uma recorrência com início retroativo de 12 meses produz exatamente 12 ocorrências históricas efetivadas, e o saldo resultante bate com o registro real da empresa com diferença de R$ 0,00.
- **SC-005**: Trocar o mundo no seletor global atualiza todas as telas sem exibir nenhum dado do outro mundo — zero vazamentos em auditoria de 100% das telas.
- **SC-006**: Um cliente que ultrapassa a tolerância de inadimplência aparece destacado no Dashboard no mesmo dia em que a tolerância vence, em 100% dos casos.
- **SC-007**: Com 5.000 lançamentos cadastrados, aplicar um filtro devolve o resultado em menos de 2 segundos e a rolagem da lista permanece fluida.
- **SC-008**: O fechamento mensal (conferir o mês e exportar o DRE) leva menos de 10 minutos, contra o processo atual em planilha.
- **SC-009**: 100% das telas, cards, gráficos e tabelas permanecem legíveis nos temas claro e escuro.
- **SC-010**: A contadora consegue registrar lançamentos sem nenhum acesso a configurações ou gestão de usuários — zero acessos indevidos em teste com o papel de operador.
- **SC-011**: O gestor consegue exportar todos os dados financeiros do sistema em menos de 5 minutos, a qualquer momento.
- **SC-012**: O gestor confere o caixa pelo celular no Dashboard e no Extrato sem rolagem horizontal e sem precisar ampliar a tela.
- **SC-013**: Alterar qualquer parâmetro configurável (tolerância de inadimplência, multiplicadores do semáforo, antecedências de alerta, lista de serviços) muda o comportamento do sistema sem nenhuma alteração de código.
- **SC-014**: Todo lançamento criado, editado ou excluído tem autor e data recuperáveis na tela de detalhe — 100% de cobertura.

---

## Out of Scope (v1)

Registrado explicitamente para não voltar como escopo silencioso (§14 do documento-mestre):

- Multi-empresa — a Lumina fica fora; o sistema atende só a Synapse. (`RNF-08`)
- Emissão de nota fiscal, boletos e integração bancária (Open Finance).
- Conciliação bancária automática.
- Contabilidade formal — partidas dobradas e plano de contas contábil.
- Orçamentos por categoria com planejado contra realizado — candidato forte a v2.
- Metas financeiras.
- Múltiplas contas ou carteiras bancárias com saldo por conta — o caixa é único por mundo.
- Multi-moeda completa — na v1 só entrada em dólar convertida para real.
- Regime de competência — na v1, competência e caixa são a mesma data. (`RN-09`)
- Envio de notificações por e-mail — a v1 entrega dentro do sistema. O mockup mostra a opção "enviar também por e-mail" nas configurações; ela fica para v2.
- Cobrança automática de inadimplentes por WhatsApp — o mockup menciona lembretes automáticos no detalhe de um lançamento atrasado; não é requisito da v1.
- Papel "Visualizador" (somente leitura) — previsto no documento-mestre como futuro.

---

## Assumptions

**Premissas assumidas na ausência de definição explícita:**

- **Usuários e volume**: 3 usuários simultâneos no máximo (Lucas, sócio, contadora). O volume esperado é de dezenas a poucas centenas de lançamentos por mês, mas o sistema é dimensionado para milhares acumulados.
- **Atraso**: qualquer lançamento em confirmação manual não efetivado após a data de vencimento passa a `Atrasado`, seja receita ou despesa. Lançamentos com efetivação automática não passam por esse estado (`FR-115`). A tolerância configurável em dias aplica-se especificamente à marcação de inadimplência do cliente.
- **Falha na cotação de câmbio**: se a fonte pública de cotação não responder, o sistema permite informar a cotação manualmente e registra que ela foi informada à mão, em vez de bloquear o registro ou gravar um valor incorreto.
- **Data da cotação**: a conversão de dólar usa a cotação da data do lançamento; para datas passadas, a cotação daquela data.
- **Retenção da lixeira**: 90 dias, conforme `RN-08`. Após esse prazo o item deixa de ser restaurável.
- **Auditoria**: mantida por tempo indeterminado — o histórico financeiro é tratado como permanente.
- **Anexos**: formatos de imagem comuns e PDF; arquivos acima de um limite razoável (na ordem de 10 MB por arquivo) são recusados com mensagem clara.
- **Detalhe do lançamento**: o painel lateral é a forma principal de visualização; o mockup mostra também variações em modal e em página inteira — tratadas como alternativas de apresentação da mesma informação, não como requisitos adicionais.
- **Seletor de período**: o mockup posiciona o período no cabeçalho global, o documento-mestre o descreve no Dashboard. Assume-se o comportamento do mockup — período global no topo, aplicado às telas que dependem de período.
- **Notificações**: entregues dentro do sistema, com contador de não lidas no topo. Nenhum canal externo na v1.
- **Ordem e visibilidade dos cards**: preferência por usuário, não global.
- **Idioma**: todo o conteúdo do produto e da documentação em português do Brasil.

**Dependências:**

- **Documento-mestre**: `Documentação/Requisitos da Plataforma Financeira.md` (v0.2) é a fonte de verdade do escopo. Qualquer decisão tomada nesta spec que altere aquele documento precisa ser refletida lá na mesma entrega (Princípio V da constituição).
- **Constituição do projeto**: `.specify/memory/constitution.md` v1.0.0 — em especial "Não reinventar a roda" (partir de componentes e telas já validados publicamente antes de escrever qualquer coisa nova) e "Nada hardcoded".
- **Mockup de interface**: projeto Claude Design "Synapse ERP Financeiro" (`https://claude.ai/design/p/f5d2a73f-43fc-4d92-b46a-b3ef8d637164`), com as telas navegáveis — Dashboard (3 variações de arranjo), Lançamentos, Extrato, Categorias, Clientes (lista e perfil), Funcionários (lista e perfil), Relatórios (DRE, ranking de clientes, variação por categoria), Configurações (7 seções), painel de detalhe do lançamento e formulário de novo lançamento.
- **Design system**: "Synapse Design System", incluído no mesmo projeto de design — define paleta (roxo suave sobre branco), tipografia, espaçamento, raios, sombras, ícones de traço e regras de interação. É a referência visual da implementação.
- **Fonte pública de cotação de câmbio**: necessária para a conversão de dólar para real (`RN-12`). Sem ela, a entrada em dólar cai no fluxo manual descrito acima.
- **Dados iniciais reais**: os 2 funcionários atuais, os 9 serviços da Synapse, as 9 categorias iniciais e as mensalidades dos clientes ativos precisam ser fornecidos para o sistema nascer com o histórico correto.
