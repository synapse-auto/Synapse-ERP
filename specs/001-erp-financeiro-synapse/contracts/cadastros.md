# Contrato — Cadastros

Convenções gerais em [README.md](./README.md).

Padrão de arquivamento: nenhum destes recursos tem `DELETE` real. `POST
/api/{recurso}/{id}/arquivar` e `/desarquivar` (`RN-06`). Listas aceitam
`?incluir_arquivados=true`.

---

## 1. Categorias (`FR-072`–`FR-079`)

| Endpoint | Papel |
|---|---|
| `GET /api/categorias` | gestor, operador |
| `POST /api/categorias` | gestor |
| `GET /api/categorias/{id}` | gestor, operador |
| `PUT /api/categorias/{id}` | gestor |
| `POST /api/categorias/{id}/arquivar` | gestor |
| `POST /api/categorias/{id}/desarquivar` | gestor |

### `GET /api/categorias`

**Query**: `mundo`, `periodo`, `tipo`, `incluir_arquivados`.

```json
{ "itens": [{
  "id": "…", "nome": "Clientes", "cor": "#2BAE76", "icone": "users",
  "tipo": "receita", "especial": true, "vinculo": "cliente", "ordem": 0,
  "arquivada_em": null,
  "uso": { "quantidade_lancamentos": 42, "total_movimentado": "14000.00" },
  "subcategorias": [{ "id": "…", "nome": "Estrutural Vidros", "cor": null,
                      "cliente_id": "…", "funcionario_id": null,
                      "uso": { "quantidade_lancamentos": 8, "total_movimentado": "4000.00" } }]
}] }
```

A **lista de categorias é a mesma nos três mundos** (`FR-006`), mas `uso` respeita o mundo
ativo (`FR-074`, cenário 5 da história 2).

### `POST` / `PUT /api/categorias/{id}`

```json
{ "nome": "Assinaturas", "cor": "#8B6CF0", "icone": "credit-card",
  "tipo": "despesa", "especial": false, "vinculo": null, "ordem": 9 }
```

- `especial: true` exige `vinculo`; `especial: false` exige `vinculo: null` → `400 validacao`.
- **Promover a especial é só isto** (`FR-079`): `PUT` com `especial: true` e `vinculo`. Não
  há deploy envolvido. Ao promover, as subcategorias existentes que não correspondem a um
  cliente/funcionário são apontadas na resposta como pendentes de vínculo.
- **Um vínculo, uma categoria.** Promover para um `vinculo` que outra categoria ativa já
  ocupa → `409 regra_violada` / `FR-079`, **nomeando a categoria que ocupa** e dizendo o que
  fazer (arquivá-la ou mudar o vínculo dela). O limite não é burocracia: o espelho de
  subcategoria (D-07) precisa saber em qual categoria criar a linha quando um cliente é
  cadastrado, e com duas a pergunta não tem resposta. Até 2026-07-31 esta tentativa batia no
  índice do banco e virava `500`.
- Categoria não aceita `mundo` no corpo → `400 validacao`.

### `POST /api/categorias/{id}/arquivar` (`RN-06`, `FR-075`)

```json
{ "destino_lancamentos": null, "manter_somente_leitura": false }
```

Com lançamentos e sem nenhuma das duas escolhas → `422 confirmacao_necessaria`:

```json
{ "erro": { "codigo": "confirmacao_necessaria", "requisito": "RN-06",
  "mensagem": "Esta categoria tem 42 lançamentos. Escolha mover para outra categoria ou manter o vínculo somente-leitura.",
  "previa": { "quantidade_lancamentos": 42, "valor_total": "14000.00" } } }
```

Nunca deixa lançamento sem categoria.

---

## 2. Subcategorias (`FR-073`)

| Endpoint | Papel |
|---|---|
| `POST /api/categorias/{id}/subcategorias` | gestor |
| `PUT /api/subcategorias/{id}` | gestor |
| `POST /api/subcategorias/{id}/arquivar` | gestor |

Dois níveis apenas — não existe subcategoria de subcategoria.

Em categoria com `vinculo`, criar subcategoria manualmente é recusado
(`409 regra_violada` / `RF-055`): a subcategoria nasce do cadastro do cliente ou do
funcionário (data-model D-07). O erro explica onde criar.

**Precisões de B4 (T104)**: `PUT /api/subcategorias/{id}` e `.../arquivar` também recusam
(`409` / D-07) quando a subcategoria é **espelho** — tem `cliente_id` ou `funcionario_id`.
O nome e o arquivamento vêm do cadastro; mexer só de um lado faria a tela de clientes e o
Dashboard mostrarem coisas diferentes.

---

## 3. Clientes (`FR-080`–`FR-084`)

| Endpoint | Papel |
|---|---|
| `GET /api/clientes` | gestor, operador |
| `POST /api/clientes` | gestor |
| `GET /api/clientes/{id}` | gestor, operador |
| `PUT /api/clientes/{id}` | gestor |
| `POST /api/clientes/{id}/arquivar` | gestor |
| `POST /api/clientes/{id}/desarquivar` | gestor |

### `GET /api/clientes`

**Query**: `mundo`, `periodo`, `situacao` (`em_dia`|`atrasado`), `busca`,
`incluir_arquivados`, paginação.

```json
{ "itens": [{
    "id": "…", "nome": "…", "empresa": "…",
    "contato_email": "…", "contato_telefone": "…",
    "tipo_cobranca": "recorrente", "valor_recorrente": "2000.00",
    "dia_cobranca": 10, "mundo_cobranca": "digital",
    "servicos": [{ "id": "…", "nome": "CRM" }],
    "situacao": "atrasado", "dias_atraso": 8, "valor_atrasado": "2000.00",
    "total_recebido_periodo": "4000.00", "total_recebido_historico": "34000.00",
    "arquivado_em": null }],
  "paginacao": {} }
```

- **Sem campo `mundo`** (research.md D-04). `mundo_cobranca` é o mundo em que a mensalidade
  gera lançamento, não o mundo do cliente.
- `?mundo=digital` filtra por **movimentação derivada**: clientes com ao menos um lançamento
  não excluído nesse mundo. Cliente sem nenhum lançamento aparece nos três estados do
  seletor — a resposta o marca com `sem_movimentacao: true` para o frontend poder explicar.
- Ordenação padrão põe os `atrasado` no topo (`FR-083`).
- `situacao` é derivada, nunca gravada (data-model §3.4).

### `POST` / `PUT /api/clientes/{id}`

```json
{ "nome": "…", "empresa": "…", "contato_email": "…", "contato_telefone": "…",
  "tipo_cobranca": "recorrente", "valor_recorrente": "2000.00",
  "dia_cobranca": 10, "mundo_cobranca": "digital",
  "servico_ids": ["…"], "observacoes": null,
  "efetivar_automaticamente": null }
```

**Precisões de B4 (T106–T108)**, todas conferidas por teste:

- A resposta do `POST` traz `subcategoria_id` e o bloco `recorrencia`, com `rotulo`
  ("Mensal, dia 10"), `efetivar_automaticamente` **efetivo** e um `aviso_inadimplencia` em
  PT-BR explicando a consequência. É texto de negócio montado no servidor: a tela precisa
  poder dizer por que um cliente com mensalidade automática nunca aparece como inadimplente.
- A situação vem achatada no item — `situacao`, `dias_atraso`, `valor_atrasado`,
  `quantidade_em_atraso` e `tolerancia_dias`. A tolerância vai junto para a tela **explicar
  o critério**, não só mostrar o rótulo. `dias_atraso` é `null`, não `0`, quando não há
  atraso.
- **Existe `POST /api/clientes/{id}/desarquivar`**, e ele **não** recria a recorrência: as
  ocorrências futuras foram removidas ao arquivar, e trazê-las de volta sem o usuário pedir
  reativaria cobranças que ele desligou. A mensagem manda editar o cliente.
- `tipo_cobranca: "recorrente"` exige `valor_recorrente`, `dia_cobranca` e
  `mundo_cobranca` → `400 validacao`.
- Criar cliente **cria a subcategoria espelho** na categoria com `vinculo=cliente` (D-07) e,
  se recorrente, **cria a recorrência da mensalidade** (`FR-082`). Ambas na mesma transação.
- `efetivar_automaticamente: null` faz a recorrência herdar
  `configuracoes.efetivacao_automatica_padrao_receita_cliente` (research.md D-05). Passar
  `true`/`false` sobrepõe. O frontend mostra o valor efetivo e explica a consequência para o
  alerta de inadimplência.

### `GET /api/clientes/{id}` — perfil (`FR-081`)

```json
{ "…dados do cliente…",
  "total_recebido_historico": "34000.00", "total_recebido_periodo": "4000.00",
  "quebra_por_mundo": { "digital": "34000.00", "infra": "0.00" },
  "receita_mensal": [{ "mes": "2026-06", "valor": "2000.00" }],
  "lancamentos": { "itens": [], "paginacao": {} },
  "proximos_recebimentos": [{ "lancamento_id": "…", "data": "2026-08-10", "valor": "2000.00", "status": "programado" }],
  "situacao": "atrasado", "dias_atraso": 8,
  "recorrencia": { "id": "…", "rotulo": "Mensal, dia 10", "ativa": true, "efetivar_automaticamente": false } }
```

### `POST /api/clientes/{id}/arquivar` (`RN-06`, `FR-084`)

Arquiva o cliente, arquiva a subcategoria espelho, desativa a recorrência e **remove as
ocorrências futuras não efetivadas**. Lançamentos passados ficam intactos. A resposta
informa quantas ocorrências futuras foram removidas (*edge case* "desligado com lançamentos
futuros programados").

---

## 4. Funcionários (`FR-085`–`FR-089`)

Mesma forma dos clientes, com uma diferença de modelagem: **funcionário tem `mundo`**
(`RN-15`), obrigatório e imutável.

| Endpoint | Papel |
|---|---|
| `GET /api/funcionarios` | gestor, operador |
| `POST /api/funcionarios` | gestor |
| `GET /api/funcionarios/{id}` | gestor, operador |
| `PUT /api/funcionarios/{id}` | gestor |
| `POST /api/funcionarios/{id}/arquivar` | gestor |

### `POST /api/funcionarios`

```json
{ "nome": "Dylan", "funcao": "Automação com n8n e IA", "tipo_contratacao": "pj",
  "valor_mensal": "1200.00", "dia_pagamento": 5, "mundo": "digital" }
```

Cria a subcategoria espelho e a **recorrência mensal da folha** (`FR-088`) na mesma
transação. `PUT` com `mundo` diferente → `409 regra_violada` / `RN-15`.

A folha nasce com **`efetivar_automaticamente = true`** (decidido em B4/T109): é despesa
certa, e deixá-la pendente encheria a caixa de confirmações mensais sem informação nenhuma.
É o oposto da mensalidade de cliente, onde o manual é que faz a cobrança existir (D-05).

### `GET /api/funcionarios/{id}` — perfil (`FR-087`)

Custo histórico e do período, lista de pagamentos, próximos pagamentos programados. Bônus e
vales aparecem como lançamentos avulsos na mesma subcategoria e somam ao custo (`FR-088`).

---

## 5. Serviços da Synapse (`FR-104`)

| Endpoint | Papel |
|---|---|
| `GET /api/servicos` | gestor, operador |
| `POST /api/servicos` | gestor |
| `PUT /api/servicos/{id}` | gestor |
| `POST /api/servicos/{id}/arquivar` | gestor |

```json
{ "nome": "Energia Solar", "mundo": "infra", "ativo": true, "ordem": 5 }
```

`GET` com `?mundo=digital` devolve só os serviços daquele mundo — é o que alimenta o campo
"serviço vinculado" do formulário de lançamento (`FR-104`, `RF-103`).

---

## 6. Centros de custo (`FR-022`, `RN-13`)

| Endpoint | Papel |
|---|---|
| `GET /api/centros-custo` | gestor, operador |
| `POST /api/centros-custo` | gestor |
| `PUT /api/centros-custo/{id}` | gestor |
| `POST /api/centros-custo/{id}/arquivar` | gestor |

```json
{ "nome": "Obra Estrutural Vidros", "mundo": "infra" }
```

Não existe centro de custo "Geral" — ausência de centro **é** "geral" (`RN-13`).

---

## 7. Tags (`FR-023`, `RN-14`)

| Endpoint | Papel |
|---|---|
| `GET /api/tags` | gestor, operador |
| `POST /api/tags` | gestor, operador |
| `PUT /api/tags/{id}` | gestor |
| `DELETE /api/tags/{id}` | gestor |

```json
{ "nome": "urgente", "cor": "#D64545" }
```

Operador **pode criar** tag — são livres (`RN-14`) e criá-las no fluxo de lançamento é o uso
esperado. Renomear e excluir são de gestor, porque afetam os lançamentos de todos.
`DELETE` remove os vínculos; não apaga lançamento. Sem mundo, sem hierarquia.
