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
  "dashboard_cards": [{ "id": "saude_caixa", "visivel": true, "ordem": 0 }] }
```

Ids desconhecidos são recusados contra `configuracoes.dashboard_cards_disponiveis` →
`400 validacao`. Persiste por usuário, não global (Assumptions da spec).

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
| `POST /api/rotinas/semanal` | Resumo semanal de segunda | `FR-098` |
| `GET /api/rotinas/estado` | Última execução e resultado (papel: gestor) | Princípio VI |

### `POST /api/rotinas/diaria`

**200**:

```json
{ "data_processada": "2026-07-29", "ja_executada_hoje": false,
  "resultado": {
    "ocorrencias_geradas": 4,
    "efetivados_automaticamente": 3,
    "movidos_para_pendente": 1,
    "movidos_para_atrasado": 2,
    "clientes_marcados_inadimplentes": 1,
    "notificacoes_criadas": 5
  },
  "duracao_ms": 820 }
```

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

---

## 8. Exportação completa (`FR-112`, `RNF-06`)

| Endpoint | Papel | O quê |
|---|---|---|
| `POST /api/exportacoes/completa` | gestor | Inicia a exportação de todos os dados |
| `GET /api/exportacoes/{id}` | gestor | Estado e link assinado quando pronto |

Assíncrona por lote, com cursor — o mesmo padrão das recorrências longas, pela mesma razão
(limite de duração da função, research.md D-02a). ZIP com um CSV por tabela mais os anexos.
`SC-011` pede menos de 5 minutos; o formato por lote é o que torna isso alcançável sem
worker dedicado.

O **backup automático** de `RNF-06` é o backup gerenciado do Supabase, não código deste
sistema. Registrar isso na documentação faz parte da Fase A.
