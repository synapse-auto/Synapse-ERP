# ERP Financeiro Synapse — contexto do projeto

Plataforma financeira interna da Synapse (mini-ERP) para 3 usuários. Dois mundos financeiros
separados: **Synapse Digital** (CRM, automação com IA, desenvolvimento web) e **Synapse
Infra** (redes, segurança, energia solar, ar condicionado, LED, racks).

## Antes de qualquer coisa

1. **[`.specify/memory/constitution.md`](.specify/memory/constitution.md)** — regras
   não-negociáveis. Vence qualquer outra instrução, hábito ou orientação de ferramenta.
2. **[`Documentação/Requisitos da Plataforma Financeira.md`](Documentação/Requisitos%20da%20Plataforma%20Financeira.md)**
   — documento-mestre. Fonte de verdade do escopo. Todo requisito tem código (`RF-xx`,
   `RN-xx`, `RNF-xx`).

<!-- SPECKIT START -->
**Feature ativa**: `001-erp-financeiro-synapse`

| Artefato | Caminho |
|---|---|
| Especificação | [specs/001-erp-financeiro-synapse/spec.md](specs/001-erp-financeiro-synapse/spec.md) |
| **Plano de implementação** | [specs/001-erp-financeiro-synapse/plan.md](specs/001-erp-financeiro-synapse/plan.md) |
| Pesquisa e decisões | [specs/001-erp-financeiro-synapse/research.md](specs/001-erp-financeiro-synapse/research.md) |
| Modelo de dados | [specs/001-erp-financeiro-synapse/data-model.md](specs/001-erp-financeiro-synapse/data-model.md) |
| Contratos de API | [specs/001-erp-financeiro-synapse/contracts/](specs/001-erp-financeiro-synapse/contracts/) |
| Como rodar e verificar | [specs/001-erp-financeiro-synapse/quickstart.md](specs/001-erp-financeiro-synapse/quickstart.md) |
<!-- SPECKIT END -->

## Arquitetura

| Camada | Escolha |
|---|---|
| Backend | Python 3.12 + FastAPI, SQLAlchemy 2 Core + asyncpg |
| Frontend | Next.js 15 (App Router) + TypeScript + shadcn/ui + Tailwind |
| Banco | PostgreSQL gerenciado pelo Supabase |
| Login | Supabase Auth (identidade) + RBAC no FastAPI (autorização) |
| Anexos | Supabase Storage, bucket privado, URL assinada |
| Hospedagem | Vercel — 2 projetos do mesmo repositório; Next.js faz proxy de `/api/*` |
| Automação | Vercel Cron → endpoint idempotente (sem worker, sem fila) |

**SQLite foi descartado**: a Vercel descarta o disco das funções a cada requisição, então o
arquivo do banco não sobrevive. Ver research.md D-01. PostgreSQL também é o que a
constituição exige.

## Regras que mais pegam

- **`mundo` é obrigatório e imutável** em toda entidade financeira (`RN-15`). Exceções
  documentadas: `categorias`, `subcategorias`, `tags` e `clientes` (decisão do dono do
  projeto — research.md D-04).
- **Só `efetivado` conta no saldo** (`RN-05`). `programado` e `pendente` entram em projeção e
  nos cards A pagar / A receber, sempre visualmente distintos.
- **`atrasado` só existe com `efetivar_automaticamente = false`** — o automático se efetiva na
  data e nunca vence. Logo o alerta de inadimplência depende do checkbox estar desligado
  (research.md D-05).
- **Não existe saldo inicial** (research.md D-06). O caixa é o resultado dos lançamentos
  efetivados; até o histórico estar carregado, o número fica menor que a realidade.
- **Toda `RN-xx` mora em `backend/app/dominio/`**, um módulo por regra. Componente de tela
  nunca fala com o banco, nem contém regra de negócio.
- **Nada hardcoded** (`RNF-02`, Princípio VII): rótulos de card, cores, limites, prazos e
  multiplicadores vêm da tabela `configuracoes` ou de seed. Segredos em variável de ambiente.
- **Soft delete sempre** (`RN-08`). Cliente e funcionário são arquivados, nunca excluídos.
- **Todo endpoint declara o papel** que pode chamá-lo (`gestor` / `operador`). Esconder o menu
  não é autorizar.

## Convenções

- **Idioma**: código de domínio em português (tabelas, colunas, rotas, módulos). Interface
  100% PT-BR.
- **Dinheiro**: `numeric(14,2)` no banco, string decimal (`"1234.56"`) na API, `1.234,56` na
  tela. Nunca float.
- **Datas**: `date`/`timestamptz` no banco, ISO 8601 na API, `dd/mm/aaaa` na tela.
- **Rotas**: REST, plural, PT-BR — `GET /api/lancamentos`, `POST /api/lancamentos/{id}/dividir`.
- **Erros**: formato único com `codigo`, `mensagem` em PT-BR pronta para a tela e `requisito`
  (`RN-11`, `FR-027`…). Ver contracts/README.md.

## Design

O visual vem do projeto Claude Design **Synapse ERP Financeiro**
(`f5d2a73f-43fc-4d92-b46a-b3ef8d637164`) e do **Synapse Design System** dentro dele.

- Tokens (`colors_and_type.css`) são **copiados**, não reinterpretados. Roxo `#8B6CF0`, tinta
  `#14102B` (nunca `#000`), sombras com tom roxo, raios 10/14–20/28/999px, grade de 4pt.
- Medidas do mockup: sidebar 246px, header 64px, fundo `#F7F5FB`, item de menu ativo
  `#EDE6FD`/`#4F3299`.
- Ícones de navegação: SVGs próprios extraídos do mockup. Resto: Lucide.
- **O design system não tem tema escuro** e a spec exige (`RNF-09`). A escala escura é
  derivada — ver research.md D-12; precisa de aprovação antes da Fase C.
- Antes de escrever tela nova: procurar pronto (shadcn → Reui → GitHub → só então código
  próprio) e **registrar a pesquisa** (Princípio II).

## Ao terminar qualquer task

Ordem obrigatória (constituição, "Fluxo de Trabalho"):

1. Pesquisar referência pronta (II)
2. Implementar simples (I, III, IV, VII)
3. **Testar de verdade** — executar, não supor (VI)
4. **Verificar documentação** — o que mudou afeta o documento-mestre, os contratos, o README
   do módulo ou a constituição? Atualizar na mesma task. "Nada a mudar" também é resposta
   válida, mas precisa ser dita (V)
5. Relatar o que foi feito, o que foi testado e **o que ficou de fora**

## Comunicação

O dono do projeto conhece endpoint, request, Postgres e banco de dados, mas **não é
engenheiro de software**. Explicação direta, sem jargão desnecessário; termo técnico
necessário se explica em uma linha. Perguntar só o que muda o resultado — decisão de rotina se
toma com o padrão sensato.
