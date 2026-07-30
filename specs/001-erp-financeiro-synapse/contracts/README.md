# Contratos de API — Plataforma Financeira Synapse

**Estilo**: REST, recursos no plural, em português (Princípio IV da constituição).
**Base**: `/api`. O OpenAPI é gerado pelo FastAPI e publicado em `/api/docs`.

> **Regra da constituição**: "Endpoint sem documentação MUST NOT ser considerado pronto."
> Estes arquivos são o contrato **acordado**; o `/api/docs` é o contrato **executável**. Os
> dois têm que bater — divergência é bug.

## Índice

| Arquivo | Domínios |
|---|---|
| [lancamentos.md](./lancamentos.md) | Lançamentos, recorrências, parcelamento, split, lote, lixeira, anexos, importação/exportação |
| [consultas.md](./consultas.md) | Dashboard, Extrato, Relatórios, busca global |
| [cadastros.md](./cadastros.md) | Categorias, subcategorias, clientes, funcionários, serviços, centros de custo, tags |
| [plataforma.md](./plataforma.md) | Sessão, usuários, configurações, notificações, auditoria, rotinas |

---

## Convenções válidas para todos os endpoints

### Autenticação

Toda rota exige `Authorization: Bearer <jwt-do-supabase>`, exceto `/api/sessao/*`.
Sem token → `401`. Token válido mas papel insuficiente → `403`.

### Papel exigido

Cada endpoint declara `Papel: gestor` ou `Papel: gestor, operador`. É obrigatório
(constituição, "Padrões Técnicos Obrigatórios") — endpoint novo sem papel declarado não
passa.

Regra geral: **operador** cria e edita lançamentos e lê tudo. **Gestor** faz o resto —
configurações, usuários, cadastros estruturais (categorias, serviços, centros de custo,
tags), clientes e funcionários.

### Mundo (`RF-101`)

Todo endpoint de leitura de dado financeiro aceita `?mundo=digital|infra|ambos`.
Ausente = `ambos`. Nunca é inferido do último uso no servidor — o cliente sempre manda.
Endpoints que devolvem consolidado incluem a quebra por mundo (`RF-102`).

### Período

Endpoints de período aceitam `?periodo=` com um atalho — `hoje`, `esta_semana`,
`este_mes`, `mes_passado`, `ultimos_3_meses`, `este_ano`, `personalizado` — e, quando
`personalizado`, `?data_inicio=&data_fim=` (`YYYY-MM-DD`). A resolução dos atalhos é do
servidor, para que o comparativo com o período anterior use exatamente a mesma régua.

### Paginação (`RNF-07`)

```
?pagina=1&por_pagina=50        # por_pagina: 1..200, padrão 50
?ordenar=data&direcao=desc
```

Resposta:

```json
{
  "itens": [],
  "paginacao": { "pagina": 1, "por_pagina": 50, "total": 0, "total_paginas": 0 }
}
```

### Formato de dados na fronteira

- **Valores monetários**: string decimal (`"1234.56"`), não float. Formatação brasileira
  (`1.234,56`) é responsabilidade do frontend (`RNF-03`).
- **Datas**: `YYYY-MM-DD`. Instantes: ISO 8601 com fuso (`2026-07-29T14:03:00-03:00`).
  `dd/mm/aaaa` é apresentação, nunca transporte.
- **Ausência**: `null` explícito, não campo omitido.

### Erros

```json
{
  "erro": {
    "codigo": "regra_violada",
    "mensagem": "A soma das partes (R$ 480,00) não fecha com o valor do lançamento (R$ 500,00).",
    "requisito": "RN-11",
    "campos": { "partes": "Faltam R$ 20,00." }
  }
}
```

`mensagem` é texto em PT-BR pronto para a tela — o frontend não monta texto de erro de
regra de negócio (`RNF-02`: nada hardcoded). `requisito` cita o código de origem, o que
torna o erro rastreável até o documento-mestre.

| HTTP | `codigo` | Quando |
|---|---|---|
| 400 | `validacao` | Corpo malformado, tipo errado |
| 401 | `nao_autenticado` | Token ausente, expirado ou inválido |
| 403 | `sem_permissao` | Papel insuficiente (`RF-02`) |
| 404 | `nao_encontrado` | Inexistente, excluído ou de outro escopo |
| 409 | `conflito_versao` | Edição concorrente (data-model §5.6) |
| 409 | `regra_violada` | Regra de negócio recusou (`RN-xx`) |
| 413 | `arquivo_grande` | Anexo acima do limite configurado |
| 415 | `formato_nao_suportado` | Anexo em formato não permitido |
| 422 | `confirmacao_necessaria` | Operação exige confirmação explícita (ver abaixo) |
| 502 | `fonte_externa_indisponivel` | Cotação de câmbio não respondeu |

### Confirmação em duas etapas (`422`)

Operações que a spec exige confirmar antes de executar respondem `422` na primeira chamada,
descrevendo o impacto, e executam quando o cliente reenvia com o campo de confirmação:

| Operação | Campo | Requisito |
|---|---|---|
| Recorrência retroativa | `confirmar_geracao_retroativa` | `FR-027` |
| Editar ocorrência passada efetivada | `confirmar_alteracao_historica` | *edge case* |
| Arquivar categoria com lançamentos | `destino_lancamentos` ou `manter_somente_leitura` | `RN-06` |
| Alterar mundo de lançamento | — | recusado sempre com `regra_violada`/`RN-15` |

Exemplo de `422`:

```json
{
  "erro": {
    "codigo": "confirmacao_necessaria",
    "mensagem": "Serão criadas 17 ocorrências entre 01/03/2025 e 01/07/2026, sendo 5 já efetivadas.",
    "requisito": "FR-027",
    "previa": {
      "total_ocorrencias": 17,
      "retroativas_efetivadas": 5,
      "primeira": "2025-03-01",
      "ultima": "2026-07-01",
      "valor_total_retroativo": "6000.00"
    }
  }
}
```

### Auditoria

Toda escrita registra autor, momento e diferença (`RF-03`, `RN-08`) sem campo extra no
corpo — o autor vem do token.

### Idempotência

`POST` de criação aceita `Idempotency-Key` opcional. Necessário porque a Vercel pode
repetir uma invocação após timeout de rede — sem isso, um clique lento cria dois
lançamentos.
