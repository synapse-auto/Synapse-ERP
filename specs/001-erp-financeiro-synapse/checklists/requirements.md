# Specification Quality Checklist: Plataforma Financeira Synapse (ERP interno v1)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-29
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

### Estado atual

**0 marcadores em aberto.** As 3 pendências foram respondidas pelo dono do projeto em
2026-07-29 e a spec foi atualizada na mesma entrega:

| Requisito | Resposta | Consequência registrada |
|-----------|----------|-------------------------|
| FR-114 — saldo inicial | **Não existe saldo inicial.** O caixa é só o resultado dos lançamentos efetivados | O saldo só bate com o banco depois de o histórico estar carregado; até lá fica menor que a realidade e o semáforo de caixa fica pessimista |
| FR-115 — efetivação de receita de cliente | **Sem regra especial.** Vale o checkbox por lançamento de `RF-17`/`RN-04` | `Atrasado` só é alcançável com o checkbox desligado; o alerta de inadimplência depende disso. O valor padrão vira configuração, não código |
| FR-116 — cliente nos dois mundos | **Cadastro único, sem mundo** | Segunda exceção a `RN-15`; o filtro de clientes por mundo passa a ser derivado da movimentação. Em troca, o perfil e o ranking ganham quebra por mundo |

Detalhamento técnico e alternativas descartadas em [research.md](../research.md) D-04, D-05 e
D-06.

### Verificações feitas

- **Rastreabilidade**: cada FR cita o código de origem (`RF-xx`, `RN-xx`, `RNF-xx`) do documento-mestre. Todos os 100+ requisitos do documento estão cobertos, mais 14 itens derivados só do mockup (marcados `(mockup)`).
- **Sem detalhes de implementação**: banco de dados, bibliotecas de interface e formatos de API foram deliberadamente mantidos fora — vivem na constituição e no futuro `plan.md`.
- **Escopo delimitado**: a seção "Out of Scope (v1)" reproduz §14 do documento-mestre e acrescenta 2 itens que o mockup sugere mas não são v1 (e-mail nas notificações e cobrança automática por WhatsApp).
- **Reconciliação das 3 decisões (2026-07-29)**: as respostas do dono do projeto contradiziam requisitos escritos antes delas. Ajustados na spec: `FR-002` (filtro de cliente por mundo é derivado da movimentação), `FR-005` e `FR-006` (cliente entra como 3ª entidade sem mundo, ao lado de categorias e subcategorias), `FR-029` (padrão do checkbox de efetivação é configuração), `FR-032` (`Atrasado` só alcançável com efetivação manual), `FR-080` (cadastro de cliente sem mundo, com mundo de cobrança na recorrência), `FR-082` (uma recorrência por mundo), `FR-083` (inadimplência depende de confirmação manual), entidade Cliente, cenário 6 da História 2, 3 casos de borda novos e a premissa de atraso. `data-model.md`, `research.md` e `plan.md` já estavam coerentes — nenhum ajuste necessário neles.

### Próximo passo

`/speckit-plan` concluído em 2026-07-29 — ver [plan.md](../plan.md).
Próximo: `/speckit-tasks` para gerar a lista de tarefas.

**Pendências que não bloqueiam esta lista, mas bloqueiam a execução** (detalhe em plan.md):

1. Configuração do MCP do Supabase — bloqueia a Fase A inteira.
2. Confirmar o `mundo` de Dylan e Marcondes — o campo é imutável depois de criado.
3. Aprovar a escala de tema escuro derivada — o design system não define tokens escuros e a
   spec exige tema escuro em 100% das telas (`RNF-09`, `SC-009`).
4. Refletir no documento-mestre: segunda exceção a `RN-15`, filtro de cliente derivado em
   `RF-101`, e `Atrasado` só com efetivação manual em `RN-03`/`RF-17`.
