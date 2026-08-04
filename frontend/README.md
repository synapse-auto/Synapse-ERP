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
├── tokens.css              design system + as duas divergências do Boss 4
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

## Boss 4 — polimento (2026-08-03)

### Tipografia: Geist

A interface usa **Geist** e **Geist Mono** (as famílias da Vercel), no lugar de Plus Jakarta
Sans + Inter. Decisão do dono do projeto; é a primeira divergência declarada do design
system. Uma família só para título e corpo — a hierarquia vem de peso e tamanho, não da
troca de família.

Carregadas por `next/font/google` (auto-hospedadas, sem requisição ao Google em tempo de
renderização). Os nomes das variáveis não mudaram — `--fonte-display`, `--fonte-body`,
`--fonte-mono` —, então os ~60 `font-[family-name:var(--font-display)]` espalhados pelas
telas continuam valendo sem edição.

> **As classes do `next/font` vão no `<html>`, nunca no `<body>`.** Elas são o que declara
> `--fonte-*`, e `globals.css` consome essas variáveis em `:root`. Com as classes no
> `<body>`, o `:root` não as enxergava — e em CSS um `var()` não resolvido **invalida a
> declaração inteira**, então `html { font-family: var(--font-body) }` caía no valor inicial
> do navegador: **serif**. A interface rodou serifada da Fase C até 2026-08-03, com Plus
> Jakarta e Inter baixadas e nenhuma das duas aplicada — trocar a fonte não mudava nada,
> porque nenhuma fonte estava valendo. O alias também passou a usar a forma com fallback
> (`var(--fonte-body, "Geist")`), que degrada para a família literal em vez de invalidar.
>
> Como conferir depois de mexer em fonte: `getComputedStyle(document.documentElement)
> .fontFamily` tem de começar com `Geist`, e `document.fonts.check("700 24px Geist")` tem de
> ser `true`. Olhar só o CSS gerado **não** pega este bug — o `@font-face` estava lá o tempo
> todo.

### Densidade

Segunda divergência declarada. A escada de raios do Synapse (4/6/10/14/20/28) virou a da
Geist: **4** para marca de seleção, **6** para controle, **8** para botão e item de menu,
**10** para painel interno, **12** para cartão, **16** para destaque. Os 160
`rounded-[Npx]` cravados nas telas foram remapeados na mesma entrega — não existem dois
vocabulários de raio no projeto.

Junto, os 234 tamanhos de fonte quebrados (`text-[12.5px]`, `text-[13.5px]`…) viraram
inteiros. Geist tem altura-x menor que a Inter: arredondar para cima manteve a leitura no
mesmo lugar e tirou o meio-pixel, que borra em tela não-retina.

**Cor, sombra e espaçamento 4pt continuam sendo os do design system, letra por letra.**

### A busca deixou de ser uma janela

Era um `CommandDialog`: clicar no campo escurecia a tela e abria um painel no meio dela.
Agora é um campo comum no cabeçalho que mostra o resultado num dropdown embaixo enquanto se
digita (`componentes/layout/BuscaGlobal.tsx`).

- Padrão `combobox` + `listbox`: o foco **nunca sai do campo**, `↑`/`↓` movem por
  `aria-activedescendant`, `Enter` abre, `Esc` limpa e depois desfoca.
- Cada opção é um `<Link>` de verdade — `⌘`/`Ctrl`+clique abre em outra aba e o endereço
  aparece na barra de status antes do clique.
- `⌘K` e `/` **focam** o campo em vez de abrir alguma coisa. `useEstadoUi.buscaAberta` virou
  `pedidoDeFocoNaBusca`, um contador (apertar `⌘K` duas vezes precisa focar duas vezes).
- **Funcionário entrou na busca** (T212): `GET /api/busca` devolve `funcionarios`, casando
  por nome **e por função**. Clicar leva para `/funcionarios/{id}`. Cliente vai para
  `/clientes/{id}`, lançamento para `/lancamentos?selecionado={id}` e categoria para a lista
  já filtrada.
- `componentes/ui/command.tsx` ficou sem uso e continua no lugar, como o resto dos
  primitivos do shadcn que ainda não foram chamados.

### Estado de tela na URL, nos dois sentidos

Até o Boss 3 a tela só **lia** o endereço na primeira montagem. Duas consequências: copiar o
link depois de filtrar mandava a lista crua, e chegar em `/lancamentos` **já estando lá** não
fazia nada — era o que aconteceria ao clicar num resultado da busca com a tela aberta. Agora
filtro, ordenação, página e o lançamento aberto vão para a URL (`paraUrl`) e voltam dela
(`daUrl`). O mundo da lista viaja como `mundo_lista` para não brigar com o `mundo` global do
cabeçalho.

Mesma ideia nas outras duas telas com abas: `?aba=` em Relatórios e `?secao=` em
Configurações. "Olha o DRE" e "olha a auditoria" viraram link. O valor padrão não vai para a
URL — endereço que a pessoa copia não carrega ruído.

### A grade do Dashboard e o "Configurar cards"

**O painel tinha uma grade por bloco, cada uma com um filho só.** Cada card não-numérico
saía dentro do seu próprio `<div class="grid lg:grid-cols-2">`, então ocupava metade da
largura e deixava a outra metade vazia, com o card seguinte na linha de baixo. Dois cards de
meia largura nunca chegavam a ficar lado a lado — o que a tela mostrava era uma coluna de
cards pela metade.

Agora é **uma grade só, de duas colunas**, e cada bloco declara quanto ocupa. Os `numerico`
consecutivos continuam numa faixa própria de quatro colunas, como no mockup.

A largura vem do servidor em `cards_disponiveis[].largura` e é resolvida em três degraus:
preferência do usuário → `largura_padrao` da entrada do catálogo → padrão por grupo
(`alerta` inteira, o resto metade). **Nenhum id de card decide layout no frontend** — era
assim que `fluxo_caixa_12m`, `linha_tempo_7_dias` e `alerta_atrasados` estavam escritos à
mão no `TelaDashboard.tsx`.

No diálogo "Configurar cards":

- **Arrastar para reordenar**, com alça (`GripVertical`), realce da linha de destino e
  `select-none` durante o arraste. HTML5 nativo, sem dependência nova.
- **As setas `↑↓` continuam** — arrastar não existe no teclado nem em leitor de tela, e
  trocá-las por arraste seria trocar conveniência por exclusão.
- **Botão de largura** por card: *Metade* (divide a linha, dois lado a lado) ou *Inteira*
  (atravessa). Some nos cards de número, que têm faixa própria.
- Arrastar **insere**, não troca: puxar o primeiro para o quarto lugar empurra os três do
  meio para cima. `moverNaLista` é a única regra de reordenação, usada também pelas setas.

### Os 22 dropdowns

Todas as escolhas do sistema eram `<select>` **nativos**: o menu era desenhado pelo sistema
operacional, então ignorava a fonte Geist, o raio, o roxo da marca e o tema escuro — no
Windows abria uma lista branca no meio da interface escura. A regra de `select { color; }` em
`globals.css` remendava a legibilidade, não a aparência.

Agora são o `Select` do **shadcn/ui** (Radix), que já estava instalado em
`componentes/ui/select.tsx` e nunca tinha sido usado (Princípio II: procurar pronto antes de
escrever — nada foi baixado nem criado do zero).

`componentes/comum/Seletor.tsx` é a casca que evita repetir sete linhas de `<Select>` em cada
uma das 22 trocas: recebe `valor`, `aoMudar` e uma lista de `{ valor, rotulo, cor, detalhe }`.
Ganhos além do visual:

- **ponto colorido** por opção — a cor da categoria vem do banco e é a mesma da tabela, do
  filtro e do gráfico; status e mundo usam as cores que já existem em tokens;
- `detalhe` para desambiguar ("BRL · real", "sugerida" na importação);
- teclado completo e `role="option"` do Radix, com o item ativo destacado e ✓ à direita;
- menu com a superfície, a sombra e o raio do projeto, igual em claro e escuro.

> **Radix proíbe `value=""` num item** — string vazia é o "nada selecionado" dele, e um item
> com esse valor derruba o componente em runtime. Metade dos seletores tem uma opção
> "todos"/"nenhum" que vale exatamente `""` na API. A tradução mora no `Seletor`, num
> sentinela, e **só entra quando existe uma opção vazia**: sem essa condição um campo
> obrigatório ainda em branco apontaria para um item inexistente e o placeholder sumiria. Foi
> o teste que pegou isso, não a leitura.

Nos formulários de lançamento e recorrência os seletores saíram de `register` para
`Controller`: Radix Select não é um `<input>`, então `register` não o alcança.

### A marca e o ícone da aba

**O logotipo da tela era um "S" desenhado à mão em SVG**, herdado do design system — não era
a marca da Synapse. Agora a marca de verdade é a única fonte, recortada em círculo:

| Arquivo | Para quê |
|---|---|
| `app/icon.png` (512×512) | ícone da aba do navegador |
| `app/apple-icon.png` (180×180) | atalho na tela de início do iOS |
| `public/marca-synapse.png` (512×512) | a marca dentro da interface, via `MarcaSynapse` |

O recorte é uma **máscara alfa de verdade**, não `border-radius`: os quatro cantos do PNG têm
`alpha = 0`. Importa porque a aba do navegador não aplica CSS — um quadrado arredondado só
por CSS voltaria a ser quadrado ali.

`app/favicon.ico` foi removido. Era um **PNG com extensão `.ico`**, e no App Router o
`favicon.ico` tem precedência sobre `icon.png` — mantê-lo faria o ícone novo nunca aparecer.
O conteúdo dele é a fonte dos três arquivos acima.

`MarcaSynapse` virou um `next/image` com `width`/`height` explícitos (sem eles a imagem
empurra o layout ao carregar) e `priority`, porque a marca está sempre acima da dobra. A prop
`idGradiente`, que existia só para o `<linearGradient>` do SVG não colidir quando a marca
aparecia duas vezes na página, deixou de fazer sentido e saiu dos quatro usos.

### "O mouse avisa que dá para clicar"

Uma regra em `app/globals.css` — não `cursor-pointer` repetido em duzentos lugares. Vale
para `button`, `a[href]`, `select`, `summary`, `label` que aponta ou embrulha o controle, e
os papéis ARIA que o Radix põe em `div` (`option`, `menuitem`, `tab`, `switch`, `checkbox`,
`radio`, `combobox`). `button` do HTML nasce com `cursor: default` — era isso que fazia o
ponteiro não mudar em metade dos botões. Desabilitado ganha `not-allowed`.

### Varredura contra o Web Interface Guidelines

Rodada com a skill `/web-design-guidelines` (regras da Vercel). O que foi corrigido:

| Área | Correção |
|---|---|
| Foco | linha da tabela ganhou anel interno (o anel roxo padrão contornava a tela toda) |
| Teclado | `Espaço` abre a linha da tabela, além de `Enter` |
| Movimento | `useMovimentoReduzido()` desliga a animação **em JavaScript** do Recharts — a regra CSS de `prefers-reduced-motion` não alcança SVG redesenhado quadro a quadro |
| Movimento | `transition-all` saiu de sete primitivos do shadcn; a lista de propriedades é explícita |
| Formulários | `name`, `autocomplete`, `inputmode`, `type` correto e `spellcheck` nos campos de cliente, funcionário e login; placeholders com exemplo |
| Formulários | fechar o formulário de lançamento com campo preenchido pergunta antes de descartar |
| Formulários | botão de envio vira "Salvando…"/"Entrando…" durante a requisição, com `aria-busy` |
| Tema escuro | `select` nativo recebe cor e fundo explícitos — no Windows ele desenhava texto preto em fundo preto |
| Celular | tabela de lançamentos rola **dentro de si** (`min-w` + `overflow-x-auto`), não arrasta a página |
| Celular | padding das telas caiu de 30px para 16px abaixo de `sm`; painéis de 360–400px passaram a `min(…, 100vw − 24px)` |
| Acessibilidade | "Pular para o conteúdo" como primeiro foco tabulável; `<main id="conteudo-principal">` |
| Acessibilidade | `aria-live` na contagem de resultados da busca; `role="radiogroup"`/`radio` nos segmentados de mundo, período, extrato e cadastro |
| Hover | linhas de pendência, de top clientes, de funcionários e os "Ver todos" do Dashboard ganharam estado de hover — eram clicáveis mudos |
| Toque | `touch-action: manipulation` e `-webkit-tap-highlight-color` na raiz; `overscroll-behavior: contain` em diálogo, gaveta e popover |
| Conteúdo | rótulos de botão em caixa de frase ("Limpar tudo", "Cancelar seleção", "Tirar") e alvos de clique de 18–20px onde eram de 13 |

## Tema escuro

Não existe no design system. A escala é derivada pelas cinco regras de research.md D-12 e
mora em `estilos/tema-escuro.css`, sobrescrevendo os **mesmos papéis** do claro — nenhum
componente sabe que existe tema. `next-themes` marca `class="dark"` e `data-theme="dark"`
ao mesmo tempo, porque o Tailwind espera o primeiro e D-12 escreve o segundo.

## Cliente retroativo — "Já era cliente antes do sistema" (2026-08-04)

Em `componentes/clientes/FormCliente.tsx`, dentro do bloco de cobrança recorrente: um
checkbox que revela **mês** e **ano** de início (`RF-64`). Ao salvar, o servidor cria as
mensalidades passadas já efetivadas e a resposta traz o texto pronto ("18 cobranças do
histórico foram lançadas…") e o total — a tela mostra, não remonta a conta (`RNF-02`).

Três condições valem na tela porque valem no servidor, e errar aqui só apareceria como um
`400` depois de a pessoa preencher tudo: o bloco **não** existe em cobrança pontual ou
parcelada, **não** existe na edição (o `PUT` recusa `cliente_desde`) e avisa quando o mês
escolhido é o corrente — caso em que nada de histórico é criado.

**Pesquisa antes de escrever (Princípio II).** Procurado um seletor de mês/ano pronto:

| Onde | O que tem | Serve? |
|---|---|---|
| `shadcn` | `search -q "month picker"` volta **vazio**; `-q "month"` acha só o bloco `login-02` | não |
| `Reui` | 500 resultados com "month", todos calendário de **dia** (`c-calendar-8`, "Month and year selection", é a legenda de um calendário completo) ou agenda de eventos | não |
| GitHub | `react-month-picker` e parentes | traz CSS próprio para reconciliar com os tokens |

O campo é **dois valores fechados**, não uma data. Dois `Seletor` — o componente que este
projeto já usa no lugar de `<select>` nativo — custam zero dependência e já respeitam fonte,
raio, cor e os dois temas. A lista de anos vai 10 anos para trás; quem manda no limite de
verdade é `configuracoes.cliente_retroativo_meses_maximo`, no servidor.

O `POST` de cliente passou a mandar `Idempotency-Key` (`novaChaveIdempotencia()`): sem ela,
a repetição depois de um timeout criaria um segundo cliente com o histórico inteiro de novo.

**Onde o passado aparece depois**: perfil ("Cliente desde 03/2025" no cabeçalho, gráfico
mensal cobrindo o tempo de casa em vez de 12 meses fixos, total histórico, lançamentos),
lista de clientes ("cliente há 1 ano e 6 meses"), e — por serem lançamentos normais —
Dashboard, Relatórios e Lançamentos, sem nada de específico ter sido escrito para isso.

## Divergências e pendências conhecidas

| # | O quê | Situação |
|---|---|---|
| 1 | **`receita_por_servico` não tinha entrada no catálogo de cards** (`FR-064`). A API devolvia o dado e o componente existia, mas o id não estava nas 18 chaves de `dashboard_cards_disponiveis`, e a grade ignora em silêncio id sem catálogo — o bloco nunca aparecia. Resolvido pela migração **`013`**, que acrescenta o 19º card na posição 16. Nenhuma linha de código mudou | resolvida em 2026-08-03 |
| 2 | **T154 — projeto `synapse-erp-web` na Vercel** | aberta: é painel, não código |
| 3 | **`GET /api/exportacoes/{id}` não existe**: a exportação completa é síncrona (contracts/plataforma.md §8). Por isso a tela não tem barra de progresso nem link assinado ao final | alinhado ao contrato |
| 4 | **`npm audit`: 3 vulnerabilidades `high`**, todas transitivas do próprio Next.js (`postcss`, `sharp`) e de tempo de build. O "fix" oferecido rebaixaria o Next para a versão 9 | sem ação |
| 5 | **`app/page.tsx` do `create-next-app` sombreava o Dashboard.** Grupo de rotas não cria segmento de URL, então `app/page.tsx` e `app/(app)/page.tsx` disputavam `/` — e quem ganhava era o boilerplate. A raiz do sistema mostrava "Deploy now / Read our docs", sem erro de build nem de tipo. Removido junto com os cinco SVGs do template, que só ele usava | resolvida em 2026-08-02 |
| 6 | **Cabeçalho com 285px em vez de 64px** em toda tela ≥ `md`. `CascaApp` passava `flex-1` ao `CabecalhoGlobal`: abaixo de `md` é o certo (a faixa é flex em linha ao lado do botão de menu), mas de `md` para cima o invólucro vira `contents` e o cabeçalho passa a ser filho direto da coluna `h-dvh flex-col` — ali `flex-1` cresce na vertical e atropela o `h-[--cabecalho-altura]`. Corrigido com `md:flex-none` | resolvida em 2026-08-02 |
| 7 | **`FuncionarioPerfil.pagamentos` estava tipado como `PaginaDe<Lancamento>`.** A API devolve lista simples, com `lancamento_id` — igual ao campo irmão `proximos_pagamentos` —, e `f.pagamentos.itens` derrubava a tela de detalhe do funcionário. O tipo virou `PagamentoDoFuncionario[]`. O perfil do **cliente** é o oposto: ali o contrato promete envelope paginado, e era o backend que não mandava o campo | resolvida em 2026-08-02 |
| 8 | **`RNF-10` pede os atalhos `1`–`7`** para navegar entre as abas e só existiam as sequências `G`+letra. Os números entraram junto, sem tirar as sequências; a folha de atalhos (`?`) mostra os dois | resolvida em 2026-08-03 |
| 9 | **"Exportar" da barra de ações em massa ignorava a seleção** e baixava a lista filtrada inteira (`FR-040`). `GET /api/lancamentos/exportacao` ganhou o parâmetro repetível `id` e a tela passa os marcados | resolvida em 2026-08-03 |
| 10 | **Tipografia e raios divergem do design system de propósito** (Boss 4): Geist no lugar de Plus Jakarta + Inter, e a escada de raios da Geist no lugar da do Synapse. Decisão do dono do projeto, marcada em `estilos/tokens.css` nos dois blocos. Cor, sombra e espaçamento continuam idênticos | divergência declarada |
| 11 | **`cmdk` continua no `package.json` sem uso**, junto com 16 outros primitivos do shadcn que ainda não foram chamados. Não foi removido para não mexer no lockfile numa entrega de polimento | sem ação |
| 12 | **A interface inteira renderizava em serif desde a Fase C.** As classes do `next/font` estavam no `<body>` e o alias `--font-body: var(--fonte-body), …` no `:root`; o `var()` não resolvia, a declaração morria e o navegador usava a família inicial. Nem Plus Jakarta nem Inter chegaram a aparecer na tela. Achado pelo dono do projeto ao ver que a troca para Geist "não mudou nada" | resolvida em 2026-08-03 |
| 13 | **O Dashboard nunca pôs dois cards lado a lado.** Cada bloco não-numérico ganhava um `grid lg:grid-cols-2` **próprio, com um filho só** — meia largura ocupada, meia vazia, o vizinho embaixo. Virou uma grade única de duas colunas, com a largura vindo do servidor (`cards_disponiveis[].largura`) e configurável card a card. Achado pelo dono do projeto | resolvida em 2026-08-03 |

## Testes

`npm run teste` — 64 testes cobrindo o que quebra em silêncio: formatação brasileira
(inclusive o erro de fuso que faria `2026-07-31` virar dia 30), tradução de filtros e
drill-down, a ida e a volta dos filtros pela URL, envelope de erro da API, os componentes
comuns, os seis casos da busca global (é campo e não janela; funcionário aparece; clicar
leva para a tela dele; os quatro grupos no mesmo dropdown; seta + `Enter`; `Esc` limpa) e a
reordenação do "Configurar cards" (arrastar **insere**, não troca) e os cinco casos do
`Seletor` — com destaque para a opção de valor vazio, que é onde o Radix quebra. Desde
2026-08-04, também os seis casos do **cliente retroativo** (não aparece em pontual, aparece
em recorrente, os campos só depois do checkbox, some na edição, avisa no mês corrente, e o
corpo sai como `AAAA-MM` sem dia) e o "tempo de casa" contado em meses de calendário.

O que **não** está coberto por teste automatizado e depende de olhar a tela ou de dados
reais: a conferência visual dos dois temas tela a tela (T202), o comportamento com 5.000
lançamentos (T204) e a verificação de aceitação de quickstart.md §8 (T206). **O Boss 4 não
fecha nenhum desses três** — a varredura foi de código, com build, tipos, lint e testes
verdes.

A tipografia, essa sim, foi conferida em navegador de verdade (Chrome headless na página
servida): `getComputedStyle` do `<html>`, do `<body>` e de um `<h2>` começando em `Geist`,
`document.fonts.check("700 24px Geist")` verdadeiro e captura de `/entrar` sem serifa. Foi
preciso: a checagem anterior — procurar `font-family: 'Geist'` no CSS gerado — passava com o
bug do item 12 ativo, porque o `@font-face` sempre esteve lá. **Declaração no CSS não é
prova de aplicação na tela.**

**Passagem manual de 2026-08-02**, com login real (Supabase Auth) contra o backend
implantado e o banco de produção: as nove rotas de tela abrem sem erro de cliente, nos dois
temas, com o cabeçalho medido em 64px de 390px a 1920px de largura. Conferidos com dado
verdadeiro: Dashboard (A pagar R$ 25.200,00, saúde do caixa "Crítico"), Extrato (gráfico e
grupos), Categorias (Funcionários com 2 subcategorias), Lançamentos (lista e filtros),
Relatórios (as quatro abas), a busca global do `Ctrl K` e as duas telas de detalhe —
`funcionarios/[id]` com o Dylan real, `clientes/[id]` com um cliente criado e apagado no
teste. O que **não** foi exercitado, por ser escrita: criar/editar/arquivar pela tela,
split, lote, importação de CSV e anexos.
