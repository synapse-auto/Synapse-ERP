# Frontend — Synapse ERP Financeiro

Next.js 15 (App Router) + TypeScript + Tailwind v4 + shadcn/ui. Interface 100% PT-BR,
fiel ao projeto Claude Design **Synapse ERP Financeiro**.

## Como rodar

```bash
cp .env.exemplo .env.local     # preencher BACKEND_URL e as duas chaves do Supabase
npm install
npm run dev                    # http://localhost:3000
```

| Script | O que faz |
|---|---|
| `npm run dev` | desenvolvimento |
| `npm run build` | build de produção |
| `npm run tipos` | `tsc --noEmit` |
| `npm run teste` | Vitest + Testing Library |
| `npm run lint` | ESLint |

`/api/*` é reescrito para `BACKEND_URL` pelo `next.config.ts` — mesma origem, sem CORS
(research.md D-02). Sem `BACKEND_URL`, cai em `http://127.0.0.1:8000`.

## Estrutura

```
app/
├── layout.tsx              fontes (next/font) + provedores
├── entrar/                 Supabase Auth — sem cadastro público
└── (app)/                  casca: barra lateral 246px + cabeçalho 64px
    ├── page.tsx            Dashboard
    ├── lancamentos/        lista, lixeira
    ├── extrato/ categorias/ clientes/ funcionarios/ relatorios/ configuracoes/
componentes/
├── ui/                     shadcn/ui — não editado à mão
├── layout/                 barra lateral, cabeçalho, seletores, busca, sino, tema
├── comum/                  Moeda, DataBR, BadgeStatus, BadgeMundo, EstadoVazio, Cartao…
├── lancamentos/            tabela, filtros, formulário, detalhe, split, lote, séries
├── dashboard/              um componente por card, resolvido por id
├── graficos/               wrappers Recharts com tokens do tema
├── clientes/ funcionarios/ categorias/ relatorios/ configuracoes/ importacao/
lib/
├── api.ts                  cliente HTTP + o formato único de erro
├── supabase.ts             só login — o frontend nunca fala com o banco
├── consultas.ts            hooks do TanStack Query, escopo na chave de cache
├── estado-global.ts        zustand: mundo + período (URL + localStorage)
├── formato.ts              R$ 1.234,56 e dd/mm/aaaa (RNF-03)
├── atalhos.ts              teclado (FR-110)
└── tipos.ts                a fronteira com a API, espelhando contracts/
estilos/
├── tokens.css              cópia literal do design system
└── tema-escuro.css         escala derivada (research.md D-12)
```

## Cinco decisões que este código carrega

**1. Nenhum texto de regra de negócio é montado aqui.** `erro.mensagem` vem do backend em
PT-BR pronto para a tela, e é isso que aparece. O único texto próprio é para o que o backend
não pôde responder — rede caída e resposta fora do contrato (`RNF-02`, `lib/api.ts`).

**2. Rótulos e limites vêm do banco.** Os cards do Dashboard são montados a partir de
`configuracoes.dashboard_cards_disponiveis`; os textos de ajuda de Configurações são a
coluna `descricao`; o limiar de destaque da variação vem em `limiar_destaque_percentual`.
Card novo no banco aparece na tela sem deploy (`FR-106`, `RNF-02`).

**3. Mundo e período são um estado só, em três lugares.** Loja (zustand) para os
componentes lerem, URL para o link ser compartilhável, `localStorage` para sobreviver à
sessão. Os dois entram na `queryKey` de toda leitura — trocar de mundo invalida tudo, e é
assim que `SC-005` não depende de disciplina (`lib/estado-global.ts`).

**4. Quem decide o que pode ser feito é o servidor.** O painel de detalhe desenha
`acoes_disponiveis`; o menu esconde Configurações por `permissoes`, mas quem autoriza é o
`403` de cada endpoint. Esconder o menu não é autorizar.

**5. Cor é variável CSS, inclusive nos gráficos.** O SVG do Recharts recebe
`fill="var(--receita-fg)"`, então o gráfico troca de tema junto com o resto — sem `useTheme`
e sem redesenhar (research.md D-12).

## Convenção de nome dos hooks

Os hooks se chamam `useSessao`, `useLancamentos`, `useEscopo` — substantivo em português com
o prefixo `use` do React. A primeira versão usava `usar…`, que é melhor português, e teve de
ser trocada: a regra `react-hooks/rules-of-hooks` do ESLint só reconhece um hook pelo
prefixo `use`, e sem esse reconhecimento ela deixa de acusar chamada condicional de hook
**em qualquer arquivo** — não só nestes. A troca do prefixo mantém o vocabulário do domínio
em português e devolve a checagem.

## Tema escuro

Não existe no design system. A escala é derivada pelas cinco regras de research.md D-12 e
mora em `estilos/tema-escuro.css`, sobrescrevendo os **mesmos papéis** do claro — nenhum
componente sabe que existe tema. `next-themes` marca `class="dark"` e `data-theme="dark"`
ao mesmo tempo, porque o Tailwind espera o primeiro e D-12 escreve o segundo.

## Divergências e pendências conhecidas

| # | O quê | Situação |
|---|---|---|
| 1 | **`receita_por_servico` não tem entrada no catálogo de cards.** A API devolve o dado e o mockup desenha o bloco, mas as 18 chaves de `dashboard_cards_disponiveis` (migração `007`) não incluem esse id. O componente existe e é resolvido por `receita_servico` — basta acrescentar a chave no seed para o bloco aparecer, sem tocar em código | aberta, decisão do dono |
| 2 | **T154 — projeto `synapse-erp-web` na Vercel** | aberta: é painel, não código |
| 3 | **`GET /api/exportacoes/{id}` não existe**: a exportação completa é síncrona (contracts/plataforma.md §8). Por isso a tela não tem barra de progresso nem link assinado ao final | alinhado ao contrato |
| 4 | **`npm audit`: 3 vulnerabilidades `high`**, todas transitivas do próprio Next.js (`postcss`, `sharp`) e de tempo de build. O "fix" oferecido rebaixaria o Next para a versão 9 | sem ação |
| 5 | **`app/page.tsx` do `create-next-app` sombreava o Dashboard.** Grupo de rotas não cria segmento de URL, então `app/page.tsx` e `app/(app)/page.tsx` disputavam `/` — e quem ganhava era o boilerplate. A raiz do sistema mostrava "Deploy now / Read our docs", sem erro de build nem de tipo. Removido junto com os cinco SVGs do template, que só ele usava | resolvida em 2026-08-02 |
| 6 | **Cabeçalho com 285px em vez de 64px** em toda tela ≥ `md`. `CascaApp` passava `flex-1` ao `CabecalhoGlobal`: abaixo de `md` é o certo (a faixa é flex em linha ao lado do botão de menu), mas de `md` para cima o invólucro vira `contents` e o cabeçalho passa a ser filho direto da coluna `h-dvh flex-col` — ali `flex-1` cresce na vertical e atropela o `h-[--cabecalho-altura]`. Corrigido com `md:flex-none` | resolvida em 2026-08-02 |
| 7 | **`FuncionarioPerfil.pagamentos` estava tipado como `PaginaDe<Lancamento>`.** A API devolve lista simples, com `lancamento_id` — igual ao campo irmão `proximos_pagamentos` —, e `f.pagamentos.itens` derrubava a tela de detalhe do funcionário. O tipo virou `PagamentoDoFuncionario[]`. O perfil do **cliente** é o oposto: ali o contrato promete envelope paginado, e era o backend que não mandava o campo | resolvida em 2026-08-02 |

## Testes

`npm run teste` — 37 testes cobrindo o que quebra em silêncio: formatação brasileira
(inclusive o erro de fuso que faria `2026-07-31` virar dia 30), tradução de filtros e
drill-down, envelope de erro da API e os componentes comuns.

O que **não** está coberto por teste automatizado e depende de dados reais: a conferência
visual dos dois temas tela a tela (T202), o comportamento com 5.000 lançamentos (T204) e a
verificação de aceitação de quickstart.md §8 (T206).

**Passagem manual de 2026-08-02**, com login real (Supabase Auth) contra o backend
implantado e o banco de produção: as nove rotas de tela abrem sem erro de cliente, nos dois
temas, com o cabeçalho medido em 64px de 390px a 1920px de largura. Conferidos com dado
verdadeiro: Dashboard (A pagar R$ 25.200,00, saúde do caixa "Crítico"), Extrato (gráfico e
grupos), Categorias (Funcionários com 2 subcategorias), Lançamentos (lista e filtros),
Relatórios (as quatro abas), a busca global do `Ctrl K` e as duas telas de detalhe —
`funcionarios/[id]` com o Dylan real, `clientes/[id]` com um cliente criado e apagado no
teste. O que **não** foi exercitado, por ser escrita: criar/editar/arquivar pela tela,
split, lote, importação de CSV e anexos.
