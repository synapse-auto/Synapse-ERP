# Contrato — Dashboard, Extrato, Relatórios e Busca

Convenções gerais em [README.md](./README.md). Todos aceitam `mundo` e `periodo`.

Estes endpoints são **somente leitura** e agregam sobre `lancamentos_ativos`. Nenhum deles
grava — exceto o efeito colateral da recuperação da rotina diária
(research.md D-08), que é interno e invisível no contrato.

---

## 1. Dashboard

### `GET /api/dashboard` — tudo de uma vez (`FR-053`–`FR-071`)

**Papel**: gestor, operador

Uma chamada devolve o Dashboard inteiro. **Motivo**: 15 cards em 15 requisições, cada uma
pagando cold start de função serverless (research.md D-02a), tornaria `SC-002` ("entender a
saúde do caixa em 10 segundos") impossível. Uma requisição, uma passada no banco.

**Query**: `mundo`, `periodo` (+ datas), `cards` (opcional — lista de ids para buscar só o
que está visível na configuração do usuário).

**200**:

```json
{
  "periodo": { "inicio": "2026-07-01", "fim": "2026-07-31", "rotulo": "Este mês",
               "anterior": { "inicio": "2026-06-01", "fim": "2026-06-30" } },
  "mundo": "ambos",

  "alerta_atrasados": {
    "quantidade": 2, "valor_total": "3200.00",
    "filtro_drilldown": { "status": ["atrasado"] }
  },

  "cards": [
    { "id": "saldo_atual", "valor": "18450.00",
      "comparativo": { "valor_anterior": "16100.00", "variacao_percentual": "14.6", "direcao": "alta" },
      "quebra_por_mundo": { "digital": "12300.00", "infra": "6150.00" },
      "tendencia": [{ "rotulo": "2026-02", "valor": "9800.00" }],
      "filtro_drilldown": null },

    { "id": "a_receber", "valor": "5400.00",
      "comparativo": {},
      "composicao": [
        { "situacao": "programado", "quantidade": 3, "valor": "3400.00" },
        { "situacao": "pendente",   "quantidade": 1, "valor": "2000.00" },
        { "situacao": "atrasado",   "quantidade": 0, "valor": "0.00" }
      ],
      "filtro_drilldown": { "tipo": "receita", "status": ["programado","pendente","atrasado"] } }
  ],

  "saude_caixa": {
    "semaforo": "verde", "cobertura": "1.83",
    "saldo": "18450.00", "despesas_fixas_horizonte": "10080.00",
    "horizonte_dias": 30, "multiplicadores": { "minimo": 1.0, "folga": 1.5 },
    "explicacao": "O saldo cobre 1,8× as despesas fixas dos próximos 30 dias."
  },

  "fluxo_caixa_mensal": [
    { "mes": "2026-07", "receitas": "18400.00", "despesas": "9250.00", "resultado": "9150.00", "projetado": false },
    { "mes": "2026-08", "receitas": "16000.00", "despesas": "9100.00", "resultado": "6900.00", "projetado": true }
  ],
  "evolucao_saldo": [{ "mes": "2026-07", "saldo_final": "18450.00", "projetado": false }],
  "comparativo_mes": { "atual": {}, "anterior": {} },

  "despesas_por_categoria": [
    { "categoria_id": "…", "nome": "Funcionários", "cor": "#D64545", "valor": "2100.00",
      "percentual": "22.7", "filtro_drilldown": { "categoria_id": ["…"] } }
  ],
  "top_despesas": [{ "lancamento_id": "…", "descricao": "…", "valor": "1200.00", "data": "2026-07-05" }],
  "receita_por_servico": [{ "servico_id": "…", "nome": "CRM", "mundo": "digital", "valor": "8000.00", "percentual": "43.5" }],

  "card_clientes": {
    "total_recebido": "14000.00", "comparativo": {},
    "clientes_ativos": 6,
    "top_clientes": [{ "cliente_id": "…", "nome": "…", "valor": "4000.00" }],
    "inadimplentes": [{ "cliente_id": "…", "nome": "…", "valor_atrasado": "2000.00", "dias_atraso": 8 }]
  },
  "card_funcionarios": {
    "custo_total": "2100.00", "comparativo": {},
    "percentual_sobre_despesas": "22.7",
    "por_funcionario": [{ "funcionario_id": "…", "nome": "Dylan", "valor": "1200.00" }],
    "proximos_pagamentos": [{ "lancamento_id": "…", "funcionario": "Dylan", "data": "2026-08-05", "valor": "1200.00" }]
  },

  "proximos_7_dias": [
    { "data": "2026-07-31", "a_pagar": [{ "lancamento_id": "…", "descricao": "…", "valor": "480.00", "status": "programado" }], "a_receber": [] }
  ],

  "resumo_linguagem_natural": "Julho fechou positivo em R$ 9.150,00, margem de 49,7%. Atenção: 2 contas vencidas somando R$ 3.200,00."
}
```

**Notas de contrato**:

- `cards` é **lista ordenada**, não objeto — a ordem vem de `usuarios.preferencias`
  (`FR-071`). Rótulos vêm de `configuracoes.dashboard_cards_disponiveis`, nunca do código
  do frontend (`FR-106`).
- `filtro_drilldown` é o corpo de query pronto para `GET /api/lancamentos`. O frontend só
  serializa e navega — nenhum card monta filtro à mão (`FR-058`).
- `tendencia` alimenta as sparklines (`FR-057`).
- `projetado: true` marca meses futuros para renderização distinta (`FR-059`, `RN-05`).
- `card_clientes`/`card_funcionarios` são renderizados a partir de `categorias.vinculo`, não
  do nome da categoria (`FR-079`).
- `explicacao` e `resumo_linguagem_natural` são geradas no servidor (`FR-069`, `FR-070`) —
  são texto de negócio, não de interface.
- Período sem dados devolve valores `"0.00"` e listas vazias com `periodo_vazio: true`,
  nunca campo ausente (*edge case* "estado vazio explicativo").

**Precisões de B3 (T090–T094)**, todas conferidas por teste:

- Cada card traz **`rotulo`, `grupo` e `ordem`** junto do valor, vindos de
  `configuracoes.dashboard_cards_disponiveis` cruzados com `usuarios.preferencias`. A
  resposta também traz **`cards_disponiveis`** — o catálogo inteiro, inclusive os ocultos,
  para a tela "Configurar cards" (`FR-071`) não precisar de outra requisição.
- `margem_operacional` traz `"unidade": "percentual"`. Sem isso a tela teria que deduzir a
  unidade pelo id do card, que é regra escondida no frontend.
- **`variacao_percentual` é `null`, não `"0.0"`, quando o período anterior é zero.** Zero por
  cento e "não dá para calcular" são coisas diferentes e a tela mostra as duas de forma
  diferente. Vale para todo percentual da resposta.
- `a_receber`/`a_pagar` e `alerta_atrasados` **ignoram o filtro de período**: conta vencida em
  maio continua a pagar em julho.
- `composicao` sempre traz as três situações, mesmo zeradas.
- `saude_caixa.cobertura` é `null` quando não há despesa fixa no horizonte — mostrar "∞×"
  seria cômodo e enganoso (`dominio/saude_caixa.py`).
- `card_clientes.inadimplentes` vem `[]` até B4/T100: a situação é derivada de `RN-10`, que
  ainda não tem módulo. Lista vazia em vez de campo ausente, para o contrato não mudar de
  forma depois.

---

## 2. Extrato

### `GET /api/extrato` (`FR-047`–`FR-052`)

**Papel**: gestor, operador

**Query**: `mundo`, `periodo` (+ datas), `agrupamento` = `dia` | `semana` | `mes`.

**200**:

```json
{
  "periodo": {},
  "resumo": {
    "total_receitas": "18400.00", "total_despesas": "9250.00",
    "resultado": "9150.00", "saldo_final": "18450.00",
    "comparativos": {
      "total_receitas": { "variacao_percentual": "12.1", "direcao": "alta" },
      "total_despesas": { "variacao_percentual": "-3.4", "direcao": "baixa" },
      "resultado":      { "variacao_percentual": "28.0", "direcao": "alta" },
      "saldo_final":    { "variacao_percentual": "14.6", "direcao": "alta" }
    }
  },
  "grafico": [{ "rotulo": "2026-07-10", "receitas": "2000.00", "despesas": "0.00" }],
  "grupos": [{
    "rotulo": "10/07/2026", "inicio": "2026-07-10", "fim": "2026-07-10",
    "previsto": false,
    "lancamentos": [],
    "totais": { "receitas": "2000.00", "despesas": "0.00" },
    "saldo_acumulado": "14300.00"
  }],
  "pendencias": {
    "a_pagar":   [{ "lancamento_id": "…", "descricao": "…", "valor": "480.00", "data": "2026-07-31", "status": "pendente", "vencido": false }],
    "a_receber": [{ "lancamento_id": "…", "descricao": "…", "valor": "2000.00", "data": "2026-07-20", "status": "atrasado", "vencido": true }]
  }
}
```

- `saldo_acumulado` do último grupo é igual a `resumo.saldo_final` — é o teste de aceitação
  da história 7 e o servidor garante a coerência.
- `previsto: true` em grupos futuros; seus valores **não** entram em `saldo_acumulado`
  (`FR-052`, `RN-05`).
- `pendencias` é a seção fixa de `FR-051` e ignora o filtro de período — pendência não é
  histórico.

---

## 3. Relatórios

Todos: **Papel** gestor, operador. Todos aceitam `formato` = `json` (padrão) | `csv` | `pdf`
(`FR-094`). Com `csv`/`pdf` a resposta é o arquivo, com os mesmos dados do `json` — nunca um
recorte diferente.

### `GET /api/relatorios/dre` (`FR-090`)

```json
{
  "periodo": {}, "acumulado_ano": {},
  "receitas": [{ "categoria_id": "…", "nome": "Clientes", "valor": "14000.00",
                 "subcategorias": [{ "nome": "Estrutural Vidros", "valor": "4000.00" }] }],
  "despesas": [{ "categoria_id": "…", "nome": "Funcionários", "valor": "2100.00",
                 "subcategorias": [{ "nome": "Dylan", "valor": "1200.00" }] }],
  "receita_bruta": "18400.00", "despesa_total": "9250.00",
  "resultado": "9150.00", "margem_percentual": "49.7",
  "comparativo_periodo_anterior": {},
  "leitura_linguagem_natural": "…"
}
```

### `GET /api/relatorios/clientes` (`FR-091`)

```json
{ "faturamento_total": "18400.00",
  "clientes": [{
    "cliente_id": "…", "nome": "…", "total_recebido": "4000.00",
    "percentual_faturamento": "21.7", "situacao": "em_dia",
    "evolucao_mensal": [{ "mes": "2026-06", "valor": "2000.00" }],
    "quebra_por_mundo": { "digital": "4000.00", "infra": "0.00" }
  }] }
```

`quebra_por_mundo` existe porque o cliente não tem mundo (research.md D-04).
`situacao`: `em_dia` | `atrasado`, derivada (data-model §3.4).

### `GET /api/relatorios/variacao-categorias` (`FR-092`)

```json
{ "meses": ["2026-05","2026-06","2026-07"],
  "linhas": [{ "categoria_id": "…", "nome": "Marketing",
    "valores": [{ "mes": "2026-06", "valor": "800.00", "variacao_percentual": "35.0", "destacar": true }] }],
  "limiar_destaque_percentual": 20 }
```

`destacar` é calculado no servidor contra
`configuracoes.variacao_destaque_percentual` — o número 20 não aparece no frontend
(`FR-106`).

### `GET /api/relatorios/matriz-mensal` (`FR-093`)

Matriz meses × categorias com todos os totais, sem foco em variação.

---

## 4. Busca global (`FR-046`)

### `GET /api/busca?q=&limite=`

**Papel**: gestor, operador

```json
{ "lancamentos": [{ "id": "…", "descricao": "…", "valor": "2000.00", "data": "2026-06-10", "mundo": "digital" }],
  "clientes":    [{ "id": "…", "nome": "…", "empresa": "…" }],
  "categorias":  [{ "id": "…", "nome": "…", "cor": "#…" }] }
```

Respeita o `mundo` ativo nos lançamentos; clientes e categorias não têm mundo.
Mínimo 2 caracteres; abaixo disso devolve listas vazias em vez de varrer a tabela.

---

## 5. Saldo

### `GET /api/saldo?mundo=` (`RN-16`, `FR-007`)

```json
{ "saldo": "18450.00", "quebra_por_mundo": { "digital": "12300.00", "infra": "6150.00" },
  "calculado_em": "2026-07-29T14:03:00-03:00" }
```

Endpoint separado porque o cabeçalho global mostra o saldo em todas as telas e não deve
depender de carregar o Dashboard inteiro.
