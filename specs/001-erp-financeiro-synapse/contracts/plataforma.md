# Contrato — Plataforma

Sessão, usuários, configurações, notificações, auditoria e rotinas automáticas.
Convenções gerais em [README.md](./README.md).

---

## 1. Sessão (`FR-101`)

O login é feito pelo **Supabase Auth** direto do navegador (research.md D-03) — o FastAPI
não recebe senha em nenhum endpoint. Isto existe para o backend fechar o ciclo:

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/sessao` | autenticado | Quem sou eu, o que posso, minhas preferências |
| `POST /api/sessao/preferencias` | autenticado | Salva tema e arranjo de cards |

### `GET /api/sessao`

```json
{ "usuario": { "id": "…", "nome": "Lucas", "email": "…", "papel": "gestor" },
  "permissoes": { "configuracoes": true, "usuarios": true, "cadastros": true, "lancamentos": true },
  "preferencias": { "tema": "auto",
    "dashboard_cards": [{ "id": "saldo_atual", "visivel": true, "ordem": 0 }] },
  "notificacoes_nao_lidas": 3 }
```

`permissoes` é booleano explícito e vem do servidor. O frontend esconde a navegação a partir
disso, mas **esconder não é autorizar** — cada endpoint valida o papel de novo (`RF-02`).

### `POST /api/sessao/preferencias` (`FR-071`, `FR-109`)

```json
{ "tema": "escuro",
  "dashboard_cards": [{ "id": "saude_caixa", "visivel": true, "ordem": 0, "largura": "metade" }] }
```

Ids desconhecidos são recusados contra `configuracoes.dashboard_cards_disponiveis` →
`400 validacao`. Persiste por usuário, não global (Assumptions da spec).

**`largura`** (T217) é opcional e vale `"inteira"` ou `"metade"` — é o que põe dois cards
lado a lado no painel. **Omitir a chave volta o card ao padrão do catálogo**; por isso o
servidor grava a preferência com `exclude_none` e nunca persiste `largura: null`, que diria
"escolhi nenhuma largura" em vez de "não escolhi".

---

## 2. Usuários (`FR-102`, `FR-105`)

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/usuarios` | gestor | Lista |
| `POST /api/usuarios` | gestor | Convida: cria no Supabase Auth e a linha em `usuarios` |
| `PUT /api/usuarios/{id}` | gestor | Nome e papel |
| `POST /api/usuarios/{id}/desativar` | gestor | `ativo = false` |
| `POST /api/usuarios/{id}/reativar` | gestor | |

```json
{ "nome": "Contadora", "email": "…", "papel": "operador" }
```

**Nunca há `DELETE`** — usuário desativado precisa continuar existindo para a auditoria
apontar para ele (`RF-03`).

**Trava de segurança**: rebaixar ou desativar o **último gestor ativo** é recusado com
`409 regra_violada` — senão o sistema fica sem ninguém que possa entrar em Configurações.

Papel `visualizador` não existe na v1 (Out of Scope) → `400 validacao`.

---

## 3. Configurações (`FR-104`–`FR-106`, `RNF-02`)

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/configuracoes` | gestor, operador | Todas as chaves |
| `PUT /api/configuracoes` | gestor | Atualiza um conjunto |

**Leitura é de operador também**: o frontend precisa de `anexo_tamanho_max_mb`,
`alerta_vencimento_dias` e os rótulos dos cards para montar a tela. Escrita é só de gestor
(`FR-105`, história 10).

### `GET /api/configuracoes`

```json
{ "inadimplencia_dias_tolerancia": { "valor": 3, "descricao": "Dias de tolerância antes de marcar o cliente como atrasado." },
  "saude_caixa_multiplicadores": { "valor": { "minimo": 1.0, "folga": 1.5 }, "descricao": "…" },
  "alerta_vencimento_dias": { "valor": [1,3,7], "descricao": "…" },
  "efetivacao_automatica_padrao_receita_cliente": { "valor": false, "descricao": "…" } }
```

`descricao` vem do banco, não do frontend — o texto de ajuda da tela de Configurações é dado
(`FR-106`).

### `PUT /api/configuracoes`

```json
{ "inadimplencia_dias_tolerancia": 7 }
```

**Efeito imediato**: alterar `inadimplencia_dias_tolerancia` **reavalia na hora** os clientes
já marcados (*edge case* "mudança de tolerância"), não na próxima rotina. A resposta informa
quantos mudaram de situação:

```json
{ "atualizadas": ["inadimplencia_dias_tolerancia"],
  "efeitos": { "clientes_reavaliados": 6, "deixaram_de_ser_inadimplentes": 2 } }
```

Chave desconhecida → `400 validacao`. Valor fora do domínio (multiplicador negativo, dias
zero) → `400 validacao` com a faixa aceita.

---

## 4. Notificações (`FR-096`–`FR-100`)

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/notificacoes` | autenticado | Só as do próprio usuário |
| `POST /api/notificacoes/{id}/marcar-lida` | autenticado | |
| `POST /api/notificacoes/marcar-todas-lidas` | autenticado | |

**Query**: `mundo`, `apenas_nao_lidas`, paginação.

```json
{ "itens": [{ "id": "…", "tipo": "inadimplencia",
    "titulo": "Estrutural Vidros está com pagamento atrasado",
    "corpo": "R$ 2.000,00 vencidos há 8 dias.",
    "mundo": "digital", "lancamento_id": "…", "cliente_id": "…",
    "lida_em": null, "criado_em": "…" }],
  "nao_lidas": 3, "paginacao": {} }
```

Alertas respeitam o mundo ativo (`RF-101`); `mundo: null` = consolidada, aparece sempre.
Não existe `POST` de criação — notificação é gerada pelas rotinas (§6), nunca por usuário.

---

## 5. Auditoria (`FR-103`, `RN-08`)

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/auditoria?entidade=&entidade_id=` | gestor, operador | Linha do tempo de um registro |
| `GET /api/auditoria` | gestor | Tudo, com filtros de usuário e período |

```json
{ "itens": [{ "id": 1841, "entidade": "lancamentos", "entidade_id": "…",
    "acao": "edicao", "usuario": { "id": "…", "nome": "Lucas" },
    "criado_em": "…",
    "alteracoes": { "valor": { "de": "1800.00", "para": "2000.00" } },
    "alteracao_historica": true }] }
```

`alteracao_historica: true` marca a edição de ocorrência passada já efetivada
(data-model §5.8). Somente leitura — não há escrita nem exclusão pela API.

---

## 6. Rotinas automáticas

Base da decisão em research.md D-08. Estes endpoints são chamados pelo **Vercel Cron** e
protegidos por segredo compartilhado em cabeçalho (`X-Segredo-Rotina`), não por JWT — não há
usuário na chamada. Segredo em variável de ambiente (Princípio VII).

| Endpoint | O quê | Requisitos |
|---|---|---|
| `POST /api/rotinas/diaria` | Materializa recorrências, aplica o ciclo de status, reavalia inadimplência, gera alertas de vencimento e de caixa baixo | `FR-030`, `FR-032`, `FR-082`, `FR-083`, `FR-096`, `FR-097`, `RN-03`, `RN-10` |
| `GET /api/rotinas/diaria` | **O mesmo**, para o Vercel Cron | idem |
| `POST /api/rotinas/semanal` | Resumo semanal de segunda | `FR-098` |
| `GET /api/rotinas/estado` | Última execução e resultado (papel: gestor) | Princípio VI |

> **Divergência entre o contrato e a plataforma, resolvida em B2/T084.** Este documento
> especificava só o `POST` com `X-Segredo-Rotina`. O **Vercel Cron não envia cabeçalho
> personalizado**: ele invoca o caminho com `GET` e manda `Authorization: Bearer $CRON_SECRET`.
> Aceitar só o `POST` deixaria o cron sem conseguir se autenticar.
>
> A dependência `exige_segredo_da_rotina` aceita os **dois** cabeçalhos e confere o **mesmo**
> segredo, com comparação de tempo constante. Na Vercel, `CRON_SECRET` e `SEGREDO_ROTINA`
> recebem o mesmo valor. O `GET` aparece no `/api/docs` — endpoint que existe e não está
> documentado é divergência, e T208 trata divergência como bug.

### `POST /api/rotinas/diaria`

**200**:

```json
{ "data_processada": "2026-07-29", "ja_executada_hoje": false,
  "resultado": {
    "ocorrencias_geradas": 4,
    "efetivados_automaticamente": 3,
    "movidos_para_pendente": 1,
    "movidos_para_atrasado": 2,
    "recorrencias_processadas": 7,
    "recorrencias_pendentes_de_geracao": 0,
    "clientes_marcados_inadimplentes": 1,
    "notificacoes_criadas": 5,
    "avisos": []
  },
  "duracao_ms": 820 }
```

`recorrencias_pendentes_de_geracao` e `avisos` foram acrescentados em B2/T083. O primeiro
conta as séries que não couberam numa invocação e continuam na próxima (D-02a); `avisos` traz
frases em PT-BR sobre o que **não** foi ideal — dia perdido recuperado, teto de recorrências
atingido. Sem eles, uma execução parcial pareceria idêntica a uma completa.

`clientes_marcados_inadimplentes` e `notificacoes_criadas` já vêm no corpo, sempre `0` até
B6 (T125–T127) — o contrato não muda de forma quando eles forem implementados.

**Idempotente**: rodar duas vezes no mesmo dia não duplica nada — cada passo traz o estado
até hoje em vez de avançar um dia, e as notificações são desduplicadas por
`chave_deduplicacao` (data-model §3.16).

**Recuperação de dia perdido**: a rotina processa de `execucoes_rotina.ultima_data_processada`
até hoje. Um cron perdido é recuperado na execução seguinte, não esquecido.

**Chamada implícita**: se a rotina não rodou hoje, a primeira leitura de
`/api/dashboard`, `/api/extrato`, `/api/lancamentos` ou `/api/saldo` a dispara antes de
responder. É o que garante que um cron falho não vire número errado na tela.

**Nota sobre o plano da Vercel**: o plano gratuito limita a frequência dos crons a uma
execução diária. O desenho acima funciona nesse limite — nenhuma regra da spec exige
granularidade menor que um dia. O resumo semanal é gerado pela rotina diária ao detectar que
é segunda-feira, com `chave_deduplicacao` por semana ISO; `/api/rotinas/semanal` existe para
poder ser disparado à mão.

---

## 7. Saúde do serviço

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/saude` | público | `{ "status": "ok", "banco": "ok", "versao": "…" }` |

Sem dado de negócio. Só para confirmar que o deploy subiu e o banco responde.

**`GET /` e `GET /api` redirecionam (307) para `/api/docs`.** Não são endpoints e por isso
não entram no OpenAPI — se entrassem, `/api/docs` passaria a listar rota que este contrato
não declara, e `T208` trata essa divergência como bug. Existem por um motivo prático: todo
endpoint mora sob `/api/...`, então a raiz da URL do deploy caía no 404 e quem a abria no
navegador concluía que o serviço estava fora do ar — exatamente ao contrário, já que a
mensagem de erro que aparecia era a **nossa**.

---

## 8. Exportação completa (`FR-112`, `RNF-06`)

| Endpoint | Papel | O quê |
|---|---|---|
| `POST /api/exportacoes/completa` | gestor | Devolve o ZIP com um CSV por tabela |

ZIP com **um CSV por tabela de negócio**, em formato de dados (separador vírgula, decimal
com ponto, datas ISO 8601), mais um `LEIA-ME.txt` com a contagem por tabela. A resposta é
`application/zip`, com `X-Total-Lancamentos` no cabeçalho para conferir sem abrir o arquivo.

**Duas coisas que este endpoint não faz, e o porquê de cada uma:**

1. **Os arquivos anexados não vão no pacote.** Eles vivem no bucket privado e embutir
   dezenas de PDFs estouraria a memória da função. `anexos.csv` traz o caminho de cada um.
   `RNF-06` ("propriedade total dos dados") fica atendido para o dado financeiro; para os
   arquivos em si, o caminho é o Storage do Supabase.
2. **A tabela `importacoes` fica de fora.** É rascunho descartável que expira em 24h
   (§6 de lancamentos.md), não histórico.

**Sobre ser síncrono.** O desenho original previa `GET /api/exportacoes/{id}` e gravação por
lote com cursor, como as recorrências longas. Não foi o que se implementou: o `POST` monta o
ZIP inteiro numa invocação e devolve na hora. Com o volume desta empresa — 3 usuários,
dezenas a poucas centenas de lançamentos por mês — isso cabe com folga e é bem mais simples
(Princípio I). **A troca declarada**: quando o histórico crescer o bastante para a montagem
passar da duração máxima da função, a exportação passa a falhar em vez de degradar, e aí o
formato por lote volta a ser necessário para garantir `SC-011`. É o que a medição de T210
existe para detectar.

O **backup automático** de `RNF-06` é o backup gerenciado do Supabase, não código deste
sistema. Registrar isso na documentação faz parte da Fase A (T008).
