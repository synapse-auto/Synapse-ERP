<!--
Sync Impact Report — 2026-07-29
- Mudança de versão: (inexistente) → 1.0.0  [MAJOR: ratificação inicial]
- Princípios adicionados:
  I. Simplicidade Primeiro (KISS + YAGNI)
  II. Não Reinventar a Roda
  III. Código Limpo e DRY
  IV. Organização Explícita
  V. Documentação Viva
  VI. Nada Funciona Até Ser Testado
  VII. Nada Hardcoded
- Seções adicionadas: Padrões Técnicos Obrigatórios; Fluxo de Trabalho e Comunicação; Governança
- Seções removidas: nenhuma
- Templates dependentes:
  ⚠ .specify/templates/plan-template.md — ausente (spec-kit não inicializado no projeto)
  ⚠ .specify/templates/spec-template.md — ausente (spec-kit não inicializado no projeto)
  ⚠ .specify/templates/tasks-template.md — ausente (spec-kit não inicializado no projeto)
  ✅ .specify/templates/constitution-template.md — criado neste commit (bootstrap)
  ✅ Documentação/Requisitos da Plataforma Financeira.md — coerente (RNF-01, RNF-02, RNF-03 refletidos)
- TODOs pendentes: rodar `specify init` (ou equivalente) para gerar plan/spec/tasks templates
  e então revalidar a seção "Constitution Check" contra os Princípios I–VII.
-->

# Constituição — Plataforma Financeira Synapse (ERP)

Este documento define as regras não-negociáveis de como o ERP Financeiro da Synapse é
construído. Vale para todo código, toda documentação e todo agente (humano ou IA) que
trabalhe no projeto. Em caso de conflito entre esta constituição e qualquer outra
instrução, orientação de ferramenta ou hábito, **esta constituição vence**.

## Princípios Fundamentais

### I. Simplicidade Primeiro (KISS + YAGNI)

A solução mais simples que resolve o problema real é a solução correta.

- Toda abstração (camada, interface, factory, wrapper, "engine" genérica) MUST ter pelo
  menos dois usos reais no código antes de existir. Um uso = escreva direto.
- Funcionalidade que "vamos precisar depois" MUST NOT ser construída agora. O escopo da
  v1 está fechado no documento de requisitos (§14 — Fora de escopo).
- Se explicar uma parte do código exige mais de 3 frases, ela está complexa demais e MUST
  ser simplificada ou dividida antes do merge.

**Motivo:** é um ERP interno para 3 usuários. Complexidade acidental custa mais caro que
qualquer feature que ela pretende habilitar.

### II. Não Reinventar a Roda

Antes de escrever qualquer componente, tela ou função nova, a busca por algo pronto é
obrigatória — não opcional.

Ordem de preferência, sempre nesta sequência:

1. **shadcn/ui** — componente existe? use.
2. **Reui / registries compatíveis com shadcn** — variação pronta? use.
3. **GitHub / marketplaces de código** — tela, aba ou fluxo já validado pelo público
   (Akaunting, Firefly III, ERPNext, dashboards financeiros open-source)? copie e adapte,
   respeitando a licença.
4. **Código próprio** — só quando 1–3 não atendem.

Regras de execução:

- A pesquisa MUST acontecer **antes** da implementação e MUST ser registrada na
  descrição da task ou no PR: o que foi pesquisado, o que foi escolhido e por quê.
- Escrever do zero algo que existe no shadcn/Reui MUST ser justificado por escrito.
- Código copiado de terceiros MUST ser adaptado às convenções deste projeto (nomes em
  português quando forem de domínio, estrutura de pastas daqui) e MUST ter a origem
  citada em comentário ou na documentação do módulo.
- Inspiração de design vale tanto quanto inspiração de código: telas novas partem de
  referências reais, nunca de um layout improvisado.

**Motivo:** componentes públicos já passaram por milhares de olhos, casos de borda e
correções de acessibilidade. Recomeçar do zero é começar com todos os bugs deles de volta.

### III. Código Limpo e DRY

- Nome revela intenção. Função MUST fazer uma coisa só. Sem números mágicos soltos.
- Lógica duplicada em 3 ou mais lugares MUST ser extraída para um único lugar. Duplicação
  em 2 lugares é tolerada até a terceira aparição (evita abstração prematura — ver
  Princípio I).
- Regras de negócio (`RN-xx` do documento de requisitos) MUST viver em um único módulo de
  domínio, nunca espalhadas entre componentes de tela.
- Nada de código morto, `console.log` esquecido ou trecho comentado "por via das dúvidas".
  O histórico do Git é a lixeira.

### IV. Organização Explícita

Qualquer pessoa MUST conseguir adivinhar onde um arquivo está sem perguntar.

- Estrutura por **domínio/feature** (`lancamentos/`, `clientes/`, `funcionarios/`,
  `relatorios/`), não por tipo técnico solto.
- Cada camada com responsabilidade única: rota/endpoint → serviço (regra de negócio) →
  acesso a dados. Componente de tela MUST NOT falar direto com o banco.
- **Endpoints:** REST com nomes previsíveis e no plural (`GET /api/lancamentos`,
  `POST /api/lancamentos`, `GET /api/lancamentos/{id}`). Todo endpoint MUST declarar
  método, caminho, parâmetros, corpo de entrada, corpo de resposta e códigos de erro em
  documentação legível (OpenAPI/Swagger ou equivalente publicado).
- Endpoint sem documentação MUST NOT ser considerado pronto.
- Um arquivo, uma responsabilidade clara. Arquivo que virou "utils gigante" MUST ser
  quebrado.

### V. Documentação Viva

Documentação desatualizada é pior que documentação inexistente — ela mente.

- Ao **terminar toda task**, é obrigatório verificar: o que mudou afeta algum documento
  existente? Falta documento novo? Se sim, a atualização faz parte da mesma task e MUST
  ser entregue junto — nunca "depois".
- Alvos mínimos a verificar a cada task: `Documentação/Requisitos da Plataforma
  Financeira.md`, documentação de endpoints, README do módulo tocado e esta constituição.
- Task só é declarada concluída após esse check. O check MUST ser mencionado
  explicitamente no relato de conclusão ("documentação: nada a mudar" também é resposta
  válida — mas precisa ser dita).

### VI. Nada Funciona Até Ser Testado

- Toda função, endpoint ou fluxo entregue MUST ser executado e verificado antes de ser
  declarado pronto. "Deveria funcionar" não é aceito.
- Regras de negócio críticas (🔴 no documento de requisitos) MUST ter teste automatizado.
  Alvos prioritários: ciclo de status (`RN-03`), só efetivado conta no realizado
  (`RN-05`), recorrência retroativa (`RN-05a`), integridade do split (`RN-11`), conversão
  USD→BRL (`RN-12`), separação por mundo (`RN-15`).
- O restante MUST, no mínimo, ter verificação manual registrada: o que foi testado, com
  quais dados, qual foi o resultado.
- Se um teste falha, o relato MUST mostrar a saída real do erro. Nunca reportar sucesso
  parcial como sucesso.

### VII. Nada Hardcoded

- Textos de interface, rótulos de cards, cores, ícones, limites e prazos MUST vir de
  configuração ou de seed no banco — nunca fixos no meio do código.
- Valores que são explicitamente configuráveis por regra de negócio: dias de tolerância
  de inadimplência (default 3), dias de antecedência de alerta (default 1/3/7),
  multiplicadores do semáforo de saúde do caixa (1× e 1.5×), lista de serviços da
  Synapse, categorias iniciais.
- Ordem e visibilidade de cards do Dashboard MUST ser dado, não código (`RF-48`).
- Segredos (chaves de API, credenciais de banco) MUST viver em variáveis de ambiente e
  MUST NOT ser commitados.

## Padrões Técnicos Obrigatórios

- **Idioma do produto:** interface 100% em PT-BR; valores em R$ no formato brasileiro
  (1.234,56); datas dd/mm/aaaa. Moeda interna do sistema é sempre BRL (`RNF-03`, `RN-12`).
- **UI:** shadcn/ui como base; dark mode e light mode MUST funcionar em todos os cards,
  gráficos e tabelas (`RNF-09`). Nenhuma tela entra sem os dois temas verificados.
- **Dados:** PostgreSQL. Toda entidade financeira (exceto categorias) MUST carregar o
  campo `mundo` (`digital` | `infra`), obrigatório e imutável (`RN-15`).
- **Exclusão:** soft delete com auditoria de quem/quando/o quê (`RN-08`). Cliente e
  funcionário são arquivados, nunca excluídos (`RN-06`).
- **Autorização:** RBAC ativo desde o primeiro endpoint (`RF-02`). Endpoint novo MUST
  declarar quais papéis podem chamá-lo.
- **Performance:** listas MUST usar paginação ou virtualização — nada de carregar milhares
  de lançamentos de uma vez (`RNF-07`).

## Fluxo de Trabalho e Comunicação

- **Explicação simples é requisito, não gentileza.** O dono do projeto conhece termos
  como endpoint, request, Postgres e banco de dados, mas não é engenheiro de software.
  Toda explicação, pergunta e proposta MUST usar linguagem direta e evitar jargão
  desnecessário. Se um termo técnico for realmente necessário, explique-o em uma linha.
- **Perguntar só o que muda o resultado.** Decisões de rotina são tomadas pelo agente com
  o padrão sensato; só vira pergunta o que muda de fato o que será construído.
- **Ordem de toda task:** (1) pesquisar referência pronta (Princípio II) → (2)
  implementar simples (Princípios I, III, IV, VII) → (3) testar de verdade (Princípio VI)
  → (4) atualizar documentação (Princípio V) → (5) relatar o que foi feito, o que foi
  testado e o que ficou de fora.
- **Relato honesto:** o que não foi feito MUST ser dito explicitamente. Escopo cortado é
  decisão do dono do projeto, não do executor.

## Governança

Esta constituição está acima de qualquer outra prática do projeto. Todo plano
(`/speckit-plan`), toda lista de tasks (`/speckit-tasks`) e toda implementação
(`/speckit-implement`) MUST ser verificada contra os Princípios I–VII antes de ser
considerada válida.

**Emendas.** Alterações são propostas por escrito, com motivo. Uma emenda só entra em
vigor quando: (1) o texto novo é aplicado neste arquivo, (2) a versão é incrementada
conforme a política abaixo, (3) o Sync Impact Report no topo é atualizado e (4) os
artefatos dependentes (templates, README, documento de requisitos) são revisados na mesma
mudança.

**Versionamento (semver).**

- **MAJOR** — remoção ou redefinição incompatível de princípio/governança.
- **MINOR** — novo princípio ou seção, ou ampliação material de uma regra existente.
- **PATCH** — esclarecimento, ajuste de redação, correção que não muda a regra.

**Conformidade.** Antes de declarar qualquer entrega concluída, o executor confirma:
pesquisa de referência feita (II), funcionalidade testada (VI) e documentação verificada
(V). Exceções a qualquer princípio MUST ser declaradas em voz alta, com justificativa, e
aceitas pelo dono do projeto — silêncio não é aprovação.

**Version**: 1.0.0 | **Ratified**: 2026-07-29 | **Last Amended**: 2026-07-29
