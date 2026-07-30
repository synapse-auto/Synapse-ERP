# Phase 1 — Modelo de Dados

**Feature**: Plataforma Financeira Synapse (ERP interno v1)
**Banco**: PostgreSQL (Supabase) — ver [research.md](./research.md) D-01
**Data**: 2026-07-29

Nomes de tabelas, colunas e tipos em **português**, por serem domínio (Princípio II da
constituição). Toda tabela tem `criado_em`/`atualizado_em`. Valores monetários são
`numeric(14,2)` — nunca ponto flutuante.

---

## 1. Visão geral

```
usuarios ──┬─< lancamentos >─┬── categorias ──< subcategorias ──┬─> clientes
           │                 ├── servicos                       └─> funcionarios
           │                 ├── centros_custo
           │                 ├──< lancamentos_tags >── tags
           │                 ├──< anexos
           │                 ├─── recorrencias ─┬─> clientes
           │                 │                  └─> funcionarios
           │                 ├─── parcelamentos
           │                 └─── lancamentos (auto-referência: split)
           ├─< notificacoes
           └─< auditoria

configuracoes (chave/valor)      cotacoes_cambio (cache)
```

**Onde `mundo` existe** (`RN-15`): `lancamentos`, `recorrencias`, `parcelamentos`,
`funcionarios`, `servicos`, `centros_custo`.

**Onde `mundo` não existe** (exceções documentadas): `categorias`, `subcategorias`
(`FR-006`), `tags` (`RF-103` não as lista), `clientes` (D-04), e as tabelas de plataforma
(`usuarios`, `configuracoes`, `auditoria`, `cotacoes_cambio`).

---

## 2. Tipos enumerados

| Tipo | Valores | Origem |
|---|---|---|
| `mundo` | `digital`, `infra` | `RN-15` |
| `tipo_lancamento` | `receita`, `despesa` | `RF-10` |
| `status_lancamento` | `programado`, `pendente`, `efetivado`, `atrasado`, `cancelado` | `RN-03` |
| `tipo_categoria` | `receita`, `despesa`, `ambas` | `RF-50` |
| `papel_usuario` | `gestor`, `operador` | `RF-02` |
| `frequencia_recorrencia` | `semanal`, `mensal`, `anual`, `dias` | `RF-15` |
| `tipo_cobranca` | `pontual`, `recorrente`, `parcelada` | `RF-60` |
| `tipo_contratacao` | `pj`, `freelancer` | `RF-65` |
| `moeda` | `BRL`, `USD` | `RN-12` |
| `vinculo_subcategoria` | `cliente`, `funcionario` | `RF-55`, `RF-56`, `RF-57` |
| `tipo_notificacao` | `vencimento`, `inadimplencia`, `resumo_semanal`, `caixa_baixo` | `RF-80`–`RF-83` |
| `acao_auditoria` | `criacao`, `edicao`, `exclusao`, `restauracao` | `RN-08` |
| `escopo_edicao_serie` | `apenas_esta`, `esta_e_futuras` | `RN-07` |

`escopo_edicao_serie` não é coluna — é parâmetro de entrada de endpoint. Listado aqui por
completude do vocabulário.

---

## 3. Entidades

### 3.1. `usuarios`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | **Igual ao `id` do Supabase Auth** — não gera próprio |
| `nome` | text NOT NULL | |
| `email` | text NOT NULL UNIQUE | |
| `papel` | `papel_usuario` NOT NULL DEFAULT `operador` | `RF-02`. Padrão é o menor privilégio |
| `ativo` | boolean NOT NULL DEFAULT true | Desativar, nunca excluir |
| `preferencias` | jsonb NOT NULL DEFAULT `'{}'` | D-09: `{tema, dashboard_cards:[{id,visivel,ordem}]}` (`FR-071`, `FR-109`) |

**Regras**: nunca excluído — só `ativo = false`. O sistema garante ao menos um `gestor`
ativo: rebaixar ou desativar o último gestor é recusado.

### 3.2. `categorias`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `nome` | text NOT NULL | Único entre as não arquivadas |
| `cor` | text NOT NULL | Hex `#RRGGBB` |
| `icone` | text NOT NULL | Nome do ícone Lucide (`FR-072`) |
| `tipo` | `tipo_categoria` NOT NULL | |
| `especial` | boolean NOT NULL DEFAULT false | `RF-55`–`RF-57` |
| `vinculo` | `vinculo_subcategoria` NULL | Preenchido só quando `especial` |
| `ordem` | integer NOT NULL DEFAULT 0 | |
| `arquivada_em` | timestamptz NULL | Arquivamento, não exclusão |

**Regras**:
- Sem `mundo` — compartilhada pelos dois mundos (`FR-006`).
- `especial = true` exige `vinculo` preenchido; `especial = false` exige `vinculo` nulo
  (constraint `CHECK`).
- **Promover a especial é dado, não código** (`FR-079`): basta gravar `especial = true` e
  `vinculo`. O card do Dashboard e a página de perfil são renderizados a partir de
  `vinculo`, sem `if categoria.nome == 'Clientes'` em nenhum lugar.
- Arquivar com lançamentos exige destino ou vínculo somente-leitura (`RN-06`, `FR-075`) —
  ver §5.3.
- Seed: 9 categorias de `FR-076`, com Clientes (`especial`, `vinculo=cliente`,
  `tipo=receita`) e Funcionários (`especial`, `vinculo=funcionario`, `tipo=despesa`).

### 3.3. `subcategorias`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `categoria_id` | uuid NOT NULL → `categorias` | |
| `nome` | text NOT NULL | Único dentro da categoria, entre as não arquivadas |
| `cor` | text NULL | Herda a da categoria quando nula |
| `cliente_id` | uuid NULL → `clientes` | D-07 |
| `funcionario_id` | uuid NULL → `funcionarios` | D-07 |
| `ordem` | integer NOT NULL DEFAULT 0 | |
| `arquivada_em` | timestamptz NULL | |

**Regras**:
- Exatamente dois níveis — não existe `subcategoria_id` pai (`FR-073`).
- `CHECK`: no máximo um entre `cliente_id` e `funcionario_id` preenchido, e só quando a
  categoria tem o `vinculo` correspondente.
- Nas categorias especiais, as linhas são **espelhadas** de `clientes`/`funcionarios` pelo
  serviço de domínio (D-07): criar cliente cria a subcategoria; arquivar cliente arquiva a
  subcategoria; renomear renomeia.

### 3.4. `clientes`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `nome` | text NOT NULL | |
| `empresa` | text NULL | |
| `contato_email` | text NULL | |
| `contato_telefone` | text NULL | |
| `tipo_cobranca` | `tipo_cobranca` NOT NULL | `RF-60` |
| `valor_recorrente` | numeric(14,2) NULL | Obrigatório quando `tipo_cobranca=recorrente` |
| `dia_cobranca` | smallint NULL | 1–31. Obrigatório quando `recorrente` |
| `mundo_cobranca` | `mundo` NULL | **Ver nota abaixo** |
| `observacoes` | text NULL | |
| `arquivado_em` | timestamptz NULL | `RN-06`: arquivado, nunca excluído |

**Nota sobre `mundo_cobranca`**: o cliente não tem mundo (D-04), mas o lançamento que a
mensalidade gera **precisa** de um (`RN-15`). `mundo_cobranca` diz em qual mundo as
ocorrências da mensalidade nascem. Não é o mundo do cliente — é o mundo da cobrança
recorrente dele. Obrigatório quando `tipo_cobranca = recorrente`.

**Filtro por mundo é derivado** (D-04): "clientes do mundo X" = clientes com ao menos um
lançamento não excluído nesse mundo. Cliente sem lançamento aparece nos três estados do
seletor.

**Status de adimplência é derivado**, não gravado: cliente tem lançamento `atrasado` cuja
data venceu há mais de `inadimplencia_dias_tolerancia` (`RN-10`). Não é coluna — muda quando
a configuração muda, e gravar exigiria reescrever todos os clientes a cada mudança de
parâmetro (o *edge case* "mudança de tolerância reavalia os já marcados" resolve-se de graça
sendo derivado).

### 3.5. `clientes_servicos`

| Campo | Tipo |
|---|---|
| `cliente_id` | uuid → `clientes` |
| `servico_id` | uuid → `servicos` |

PK composta. Serviços contratados pelo cliente (`RF-60`).

### 3.6. `funcionarios`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `nome` | text NOT NULL | |
| `funcao` | text NOT NULL | |
| `tipo_contratacao` | `tipo_contratacao` NOT NULL | |
| `valor_mensal` | numeric(14,2) NOT NULL CHECK > 0 | |
| `dia_pagamento` | smallint NOT NULL CHECK 1–31 | |
| `mundo` | `mundo` NOT NULL | `RN-15` — imutável |
| `arquivado_em` | timestamptz NULL | `RN-06` |

**Seed obrigatório** (`FR-086`): Dylan — Automação com n8n e IA — PJ — R$ 1.200,00 —
mundo `digital`; Marcondes — Java e Engenharia de Software — PJ — R$ 900,00 — mundo
`digital`.

> ✅ **Confirmado pelo dono do projeto em 2026-07-30**: os dois funcionários são do mundo
> `digital`. O documento-mestre não declarava o mundo e o seed assumia por inferência das
> funções (n8n/IA e Java); agora é decisão explícita. O campo é imutável (`RN-15`) — mudar
> depois exigiria recriar o funcionário e a subcategoria dele.

### 3.7. `servicos`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `nome` | text NOT NULL | Único |
| `mundo` | `mundo` NOT NULL | CRM → digital, Redes → infra |
| `ativo` | boolean NOT NULL DEFAULT true | |
| `ordem` | integer NOT NULL DEFAULT 0 | |

**Seed** (`FR-104`): Digital — CRM, Automação com IA, Desenvolvimento Web.
Infra — Infraestrutura de Redes, Segurança, Energia Solar, Ar Condicionados, Painéis de LED,
Montagem de Racks.

### 3.8. `centros_custo`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `nome` | text NOT NULL | |
| `mundo` | `mundo` NOT NULL | `RF-103` |
| `arquivado_em` | timestamptz NULL | |

Opcional no lançamento; ausência significa "geral" (`RN-13`). **Não** se cria um centro de
custo chamado "Geral" — ausência é a representação.

### 3.9. `tags`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `nome` | text NOT NULL UNIQUE | |
| `cor` | text NOT NULL | Hex |

Sem hierarquia, sem mundo, sem limite por lançamento (`RN-14`).

### 3.10. `lancamentos` — entidade central

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `mundo` | `mundo` NOT NULL | `RN-15` — **imutável** |
| `tipo` | `tipo_lancamento` NOT NULL | |
| `descricao` | text NOT NULL | |
| `valor` | numeric(14,2) NOT NULL CHECK > 0 | `RN-02` — sempre positivo, sinal vem do `tipo` |
| `data` | date NOT NULL | `RN-09` — data única, quando o dinheiro se move |
| `status` | `status_lancamento` NOT NULL | `RN-03` |
| `categoria_id` | uuid NOT NULL → `categorias` | `RN-01` |
| `subcategoria_id` | uuid NULL → `subcategorias` | Obrigatória se a categoria é especial (`RN-01`) |
| `servico_id` | uuid NULL → `servicos` | |
| `centro_custo_id` | uuid NULL → `centros_custo` | `RN-13` |
| `observacoes` | text NULL | |
| `efetivar_automaticamente` | boolean NOT NULL DEFAULT true | `RF-17`, `RN-04` |
| `efetivado_em` | timestamptz NULL | Quando virou `efetivado` |
| `efetivado_por` | uuid NULL → `usuarios` | Nulo se foi a rotina automática |
| `moeda_origem` | `moeda` NOT NULL DEFAULT `BRL` | `RN-12` |
| `valor_origem` | numeric(14,2) NULL | Valor em USD, quando `moeda_origem=USD` |
| `cotacao` | numeric(14,6) NULL | Taxa usada |
| `cotacao_data` | date NULL | Data da cotação (= `data` do lançamento) |
| `cotacao_manual` | boolean NOT NULL DEFAULT false | Informada à mão porque a fonte falhou |
| `recorrencia_id` | uuid NULL → `recorrencias` | |
| `parcelamento_id` | uuid NULL → `parcelamentos` | |
| `parcela_numero` | smallint NULL | `RF-16` — "2/3" |
| `parcela_total` | smallint NULL | |
| `lancamento_pai_id` | uuid NULL → `lancamentos` | Split (`RF-13a`) |
| `versao` | integer NOT NULL DEFAULT 1 | Ver §5.6 (edição concorrente) |
| `criado_por` | uuid NOT NULL → `usuarios` | `RF-03` |
| `atualizado_por` | uuid NULL → `usuarios` | |
| `excluido_em` | timestamptz NULL | Soft delete (`RN-08`) |
| `excluido_por` | uuid NULL → `usuarios` | |

**Constraints**:
- `moeda_origem = 'USD'` ⇒ `valor_origem`, `cotacao` e `cotacao_data` NOT NULL.
- `moeda_origem = 'BRL'` ⇒ os três nulos.
- `parcela_numero` e `parcela_total` juntos, ou ambos nulos; `parcela_numero <= parcela_total`.
- `lancamento_pai_id` não pode apontar para si mesmo, e uma parte de split não pode ter
  partes (um nível só).
- `mundo` imutável: trigger `BEFORE UPDATE` que recusa mudança (`RN-15`, `FR-005`). É a
  única regra em trigger, porque é uma garantia que não pode depender de o serviço lembrar.

**Índices**:
| Índice | Serve a |
|---|---|
| `(mundo, data DESC) WHERE excluido_em IS NULL` | Lista, extrato, dashboard |
| `(status, data) WHERE excluido_em IS NULL` | Rotina diária, A pagar/A receber, atrasados |
| `(categoria_id, data)`, `(subcategoria_id, data)` | DRE, variação mensal, perfis |
| `(servico_id, data)` | `RF-43b` receita por serviço |
| `(recorrencia_id)`, `(parcelamento_id)`, `(lancamento_pai_id)` | Navegar para a série |
| `(excluido_em) WHERE excluido_em IS NOT NULL` | Lixeira |
| GIN `pg_trgm` em `descricao` | Busca por texto livre (`FR-037`) e busca global (`FR-046`) |

**View `lancamentos_ativos`**: `SELECT * FROM lancamentos WHERE excluido_em IS NULL`. Toda
consulta de negócio parte dela — evita esquecer o filtro de soft delete em algum lugar
(Princípio III).

### 3.11. `lancamentos_tags`

| Campo | Tipo |
|---|---|
| `lancamento_id` | uuid → `lancamentos` ON DELETE CASCADE |
| `tag_id` | uuid → `tags` |

PK composta.

### 3.12. `anexos`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `lancamento_id` | uuid NOT NULL → `lancamentos` | |
| `nome_arquivo` | text NOT NULL | Nome original, para download |
| `caminho_storage` | text NOT NULL | Caminho no bucket do Supabase Storage |
| `mime_type` | text NOT NULL | Só `image/*` e `application/pdf` (`FR-013`) |
| `tamanho_bytes` | bigint NOT NULL | Limite de `configuracoes.anexo_tamanho_max_mb` |
| `criado_por` | uuid NOT NULL → `usuarios` | |

**Bucket privado**. O download passa por URL assinada de curta validade gerada pelo backend
— nunca URL pública, senão qualquer pessoa com o link vê nota fiscal da empresa.

Anexos são **compartilhados** entre as partes de um split (`RF-013a`): a linha continua no
lançamento-pai e as partes leem por herança.

### 3.13. `recorrencias`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `mundo` | `mundo` NOT NULL | |
| `tipo` | `tipo_lancamento` NOT NULL | |
| `descricao` | text NOT NULL | |
| `valor` | numeric(14,2) NOT NULL CHECK > 0 | |
| `categoria_id` | uuid NOT NULL | |
| `subcategoria_id` | uuid NULL | |
| `servico_id` | uuid NULL | |
| `centro_custo_id` | uuid NULL | |
| `frequencia` | `frequencia_recorrencia` NOT NULL | `RF-15` |
| `intervalo_dias` | smallint NULL | Só quando `frequencia=dias` |
| `dia_vencimento` | smallint NULL | Dia do mês (mensal/anual) ou da semana 1–7 (semanal) |
| `mes_vencimento` | smallint NULL | Só quando `frequencia=anual` |
| `data_inicio` | date NOT NULL | **Pode ser retroativa** (`RF-17a`, `RN-05a`) |
| `data_fim` | date NULL | Término opcional |
| `total_parcelas` | smallint NULL | Término alternativo por contagem |
| `efetivar_automaticamente` | boolean NOT NULL DEFAULT true | Herdado pelas ocorrências |
| `gerada_ate` | date NULL | Até onde as ocorrências já foram materializadas |
| `cliente_id` | uuid NULL → `clientes` | Origem: mensalidade (`RF-62`) |
| `funcionario_id` | uuid NULL → `funcionarios` | Origem: folha (`RF-67`) |
| `ativa` | boolean NOT NULL DEFAULT true | Desligar para de gerar novas |
| `criado_por` / `excluido_em` | | |

**Regras**:
- `data_fim` e `total_parcelas` são mutuamente exclusivos.
- `gerada_ate` é o que torna a materialização idempotente (D-08): gerar significa "avançar
  de `gerada_ate` até o horizonte", nunca "criar tudo de novo".
- **Horizonte de geração**: ocorrências futuras são materializadas até
  `configuracoes.recorrencia_horizonte_meses` (padrão 12) à frente. Recorrência sem fim não
  gera linhas infinitas.
- Ocorrências entre `data_inicio` retroativa e hoje nascem `efetivado` (`RN-05a`), **independente**
  de `efetivar_automaticamente` — o passado já aconteceu.
- Editar com escopo `esta_e_futuras` altera a recorrência e regera apenas ocorrências de
  data ≥ hoje ainda não efetivadas. Passado nunca muda por essa via (`RN-07`).
- Excluir uma ocorrência não toca a série (*edge case* da spec).
- Arquivar cliente/funcionário põe `ativa = false` na recorrência de origem e **remove as
  ocorrências futuras não efetivadas** (*edge case* "desligado com lançamentos futuros").

### 3.14. `parcelamentos`

| Campo | Tipo |
|---|---|
| `id` | uuid PK |
| `mundo` | `mundo` NOT NULL |
| `descricao` | text NOT NULL |
| `valor_total` | numeric(14,2) NOT NULL |
| `total_parcelas` | smallint NOT NULL CHECK > 1 |
| `criado_por` / `criado_em` | |

Existe separado de `recorrencias` porque parcelamento é um valor **fechado** dividido
(`RF-16`), não uma regra que gera indefinidamente. `sum(parcelas) = valor_total`, com a
diferença de arredondamento absorvida na última parcela.

### 3.15. `configuracoes`

| Campo | Tipo |
|---|---|
| `chave` | text PK |
| `valor` | jsonb NOT NULL |
| `descricao` | text NOT NULL |
| `atualizado_por` | uuid NULL → `usuarios` |
| `atualizado_em` | timestamptz NOT NULL |

Tabela que materializa `RNF-02`/`FR-106`/Princípio VII. **Seed completo**:

| Chave | Valor padrão | Requisito |
|---|---|---|
| `inadimplencia_dias_tolerancia` | `3` | `RF-81`, `RN-10` |
| `saude_caixa_multiplicadores` | `{"minimo":1.0,"folga":1.5}` | `RF-46b` |
| `saude_caixa_horizonte_dias` | `30` | `RF-46b` |
| `caixa_baixo_horizonte_dias` | `7` | `RF-83` |
| `alerta_vencimento_dias` | `[1,3,7]` | `RF-80` |
| `lixeira_retencao_dias` | `90` | `RN-08` |
| `anexo_tamanho_max_mb` | `10` | Assumptions |
| `anexo_mime_permitidos` | `["image/png","image/jpeg","image/webp","application/pdf"]` | `FR-013` |
| `variacao_destaque_percentual` | `20` | `RF-72` |
| `recorrencia_horizonte_meses` | `12` | §3.13 |
| `recorrencia_aviso_ocorrencias` | `24` | `FR-027` — a partir de quantas ocorrências avisar |
| `tema_padrao` | `"auto"` | `FR-109` |
| `efetivacao_automatica_padrao` | `true` | `RF-17` |
| `efetivacao_automatica_padrao_receita_cliente` | `false` | D-05 — ver research.md |
| `dashboard_cards_disponiveis` | `[{id,rotulo,grupo,ordem_padrao,visivel_padrao}, …]` | `RF-48`, `FR-071` |
| `cambio_fonte_primaria` / `cambio_fonte_alternativa` | `"awesomeapi"` / `"bcb_ptax"` | `RN-12` |

Rótulos dos cards vivem em `dashboard_cards_disponiveis` — nenhum texto de card no código
(`FR-106`).

### 3.16. `notificacoes`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | uuid PK | |
| `usuario_id` | uuid NOT NULL → `usuarios` | Uma linha por destinatário |
| `tipo` | `tipo_notificacao` NOT NULL | |
| `titulo` / `corpo` | text NOT NULL | |
| `mundo` | `mundo` NULL | Nulo = consolidada. Alertas respeitam o mundo ativo (`RF-101`) |
| `lancamento_id` / `cliente_id` | uuid NULL | Para clicar e ir ao item |
| `chave_deduplicacao` | text NOT NULL | Ver abaixo |
| `lida_em` | timestamptz NULL | Contador de não lidas (`FR-100`) |

**`chave_deduplicacao`** com UNIQUE `(usuario_id, chave_deduplicacao)`: a rotina diária pode
rodar mais de uma vez (D-08). Sem essa chave, o mesmo "vence em 3 dias" viraria três
notificações. Formato: `vencimento:{lancamento_id}:{dias}`,
`inadimplencia:{cliente_id}:{aaaa-mm-dd}`, `resumo_semanal:{aaaa-Www}`,
`caixa_baixo:{mundo}:{aaaa-Www}`.

### 3.17. `auditoria`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | bigserial PK | |
| `entidade` | text NOT NULL | Nome da tabela |
| `entidade_id` | uuid NOT NULL | |
| `acao` | `acao_auditoria` NOT NULL | |
| `alteracoes` | jsonb NOT NULL | `{campo: {de, para}}` — só o que mudou |
| `usuario_id` | uuid NOT NULL → `usuarios` | |
| `criado_em` | timestamptz NOT NULL | |

Índice `(entidade, entidade_id, criado_em DESC)` — a linha do tempo no painel de detalhe
(`FR-041`, `FR-103`).

**Nunca apagada** (Assumptions: histórico financeiro é permanente). Não tem soft delete —
não faria sentido.

### 3.18. `cotacoes_cambio`

| Campo | Tipo |
|---|---|
| `data` | date |
| `par` | text (`'USDBRL'`) |
| `taxa` | numeric(14,6) NOT NULL |
| `fonte` | text NOT NULL |
| `obtida_em` | timestamptz NOT NULL |

PK `(data, par)`. Cache — ver research.md §5.

### 3.19. `execucoes_rotina`

| Campo | Tipo |
|---|---|
| `nome` | text PK (`'diaria'`, `'semanal'`) |
| `ultima_execucao_em` | timestamptz NOT NULL |
| `ultima_data_processada` | date NOT NULL |
| `ultimo_resultado` | jsonb NOT NULL |

Suporta a idempotência e a recuperação na leitura de D-08. `ultimo_resultado` guarda o que a
rotina fez (quantos efetivados, quantos atrasados) — é o registro de verificação que o
Princípio VI exige.

---

## 4. Ciclo de status (`RN-03`, `RN-04`)

```
                      ┌──────────────┐
       criado com     │  programado  │  data futura
       data futura →  └──────┬───────┘
                             │ chega a data
              ┌──────────────┴──────────────┐
   efetivar_auto = true          efetivar_auto = false
              │                              │
              ▼                              ▼
       ┌─────────────┐              ┌──────────────┐
       │  efetivado  │◄─────────────│   pendente   │
       └─────────────┘  1 clique    └──────┬───────┘
              ▲                            │ passa do vencimento
              │                            ▼
              │  1 clique          ┌──────────────┐
              └────────────────────│   atrasado   │
                                   └──────────────┘

   criado com data ≤ hoje  →  efetivado (direto)
   qualquer estado         →  cancelado (preserva histórico, sai dos totais)
```

**Consequência de D-05**: `atrasado` só é alcançável com `efetivar_automaticamente = false`.
Lançamento automático se efetiva na data e nunca vence.

**Só `efetivado` entra no realizado** (`RN-05`). `programado` e `pendente` entram em
projeção e nos cards A pagar / A receber. `cancelado` e excluído não entram em nada.

---

## 5. Regras de integridade e onde elas moram

Cada regra abaixo tem **um** módulo dono em `backend/app/dominio/` (Princípio III).

### 5.1. `RN-15` — mundo obrigatório e imutável → `dominio/mundo.py` + trigger
Trigger de banco recusa `UPDATE` de `mundo`. Exceções documentadas: `categorias`,
`subcategorias`, `tags`, `clientes` (D-04).

### 5.2. `RN-05` / `RN-16` — saldo → `dominio/saldo.py`
`saldo(mundo) = Σ(efetivado, receita) − Σ(efetivado, despesa)`, excluído `excluido_em NOT
NULL` e `cancelado`. Sem saldo inicial (D-06). Modo "Ambos" = soma dos dois + quebra.

### 5.3. `RN-06` — nunca lançamento órfão → `dominio/arquivamento.py`
Arquivar categoria/subcategoria com lançamentos exige uma de duas escolhas explícitas do
usuário: **mover** os lançamentos para outro destino, ou **manter vínculo somente-leitura**
(a categoria arquivada não aparece em formulários novos, mas os lançamentos antigos seguem
apontando para ela). Nunca `NULL`. Cliente/funcionário: sempre arquivar, nunca excluir.

### 5.4. `RN-11` — integridade do split → `dominio/split.py`
`Σ(partes) = valor(pai)`, comparado em `numeric` (não float). Salvar em estado inconsistente
é recusado com a diferença explicitada. O pai deixa de contar nos totais quando tem partes —
só as partes contam, senão o valor entra em dobro.

### 5.5. `RN-12` — conversão USD→BRL → `dominio/cambio.py`
Cotação da **data do lançamento** (não de hoje). Consulta o cache, depois a fonte primária,
depois a alternativa; se todas falharem, exige cotação manual e grava
`cotacao_manual = true`. Nunca grava valor sem cotação registrada.

### 5.6. Edição concorrente → `versao` em `lancamentos`
*Edge case* "dois usuários editando o mesmo lançamento": o `PUT` envia a `versao` que leu;
se não bater com a do banco, responde `409` com o que mudou desde então. Sem isso, a última
gravação apaga a anterior em silêncio — o que a spec proíbe explicitamente. Um `integer`
resolve; travar linha ou pôr fila não se justifica para 3 usuários (Princípio I).

### 5.7. `RN-08` — soft delete e lixeira → `dominio/lixeira.py`
`excluido_em` + `excluido_por`. Restaurável enquanto
`agora - excluido_em < lixeira_retencao_dias`. Passado o prazo, a restauração é recusada
(*edge case*), mas **a linha não é apagada** — o histórico financeiro é permanente
(Assumptions). A lixeira apenas para de oferecer a restauração.

### 5.8. Editar ocorrência passada já efetivada → `dominio/status.py`
Permitido, mas exige confirmação explícita (o endpoint recebe
`confirmar_alteracao_historica=true`) e a auditoria registra que foi mudança retroativa
(*edge case*).

---

## 6. Rastreabilidade requisito → tabela

| Requisito | Onde vive |
|---|---|
| `FR-001`–`FR-007` (mundos) | coluna `mundo`, trigger, `dominio/mundo.py`, `dominio/saldo.py` |
| `FR-008`–`FR-023` (registro) | `lancamentos`, `lancamentos_tags`, `anexos`, `tags`, `centros_custo` |
| `FR-024`–`FR-035` (programação) | `recorrencias`, `parcelamentos`, `status`, `efetivar_automaticamente` |
| `FR-036`–`FR-046` (lista/busca) | índices de `lancamentos`, GIN `pg_trgm`, view `lancamentos_ativos` |
| `FR-047`–`FR-052` (extrato) | agregações sobre `lancamentos_ativos` |
| `FR-053`–`FR-071` (dashboard) | agregações + `usuarios.preferencias` + `configuracoes` |
| `FR-072`–`FR-079` (categorias) | `categorias`, `subcategorias` |
| `FR-080`–`FR-084` (clientes) | `clientes`, `clientes_servicos`, `recorrencias.cliente_id` |
| `FR-085`–`FR-089` (funcionários) | `funcionarios`, `recorrencias.funcionario_id` |
| `FR-090`–`FR-095` (relatórios) | agregações; nenhuma tabela nova |
| `FR-096`–`FR-100` (notificações) | `notificacoes`, `execucoes_rotina` |
| `FR-101`–`FR-103` (acesso/auditoria) | `usuarios`, `auditoria`, Supabase Auth |
| `FR-104`–`FR-106` (configurações) | `configuracoes`, `servicos`, `centros_custo`, `tags` |
| `FR-107`–`FR-113` (experiência) | frontend; `versao`, índices, paginação |
| `FR-114` | resolvido: nada a modelar (D-06) |
| `FR-115` | resolvido: `efetivar_automaticamente` + chave de configuração (D-05) |
| `FR-116` | resolvido: `clientes` sem `mundo`, `mundo_cobranca` para a mensalidade (D-04) |

---

## 7. Ordem de aplicação das migrações

| Arquivo | Conteúdo |
|---|---|
| `001_extensoes_e_tipos.sql` | `pg_trgm`, todos os `CREATE TYPE` |
| `002_plataforma.sql` | `usuarios`, `configuracoes`, `auditoria`, `execucoes_rotina`, `cotacoes_cambio` |
| `003_cadastros.sql` | `categorias`, `subcategorias`, `clientes`, `clientes_servicos`, `funcionarios`, `servicos`, `centros_custo`, `tags` |
| `004_lancamentos.sql` | `parcelamentos`, `recorrencias`, `lancamentos`, `lancamentos_tags`, `anexos`, view `lancamentos_ativos`, índices, trigger de `mundo` |
| `005_notificacoes.sql` | `notificacoes` |
| `006_rls.sql` | RLS ligada com negação para `anon`/`authenticated` (D-03a) |
| `007_seed_configuracoes.sql` | tabela `configuracoes` completa (§3.15) |
| `008_seed_dominio.sql` | 9 categorias, 9 serviços, 2 funcionários — **depende da confirmação do mundo dos funcionários** (§3.6) |

As `003`/`004` têm dependência circular entre `subcategorias.cliente_id` e
`clientes` — resolvida criando as tabelas primeiro e as FKs no fim do arquivo `003`.
