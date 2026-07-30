# Contrato — Lançamentos

Convenções gerais em [README.md](./README.md).

---

## 1. Lançamentos

### `GET /api/lancamentos` — lista filtrada (`FR-036`–`FR-039`)

**Papel**: gestor, operador

**Query**: `mundo`, `periodo` (+ `data_inicio`/`data_fim`), `tipo`, `categoria_id[]`,
`subcategoria_id[]`, `servico_id[]`, `centro_custo_id[]`, `tag_id[]`, `status[]`,
`valor_min`, `valor_max`, `busca` (texto livre em descrição e observações),
`pagina`, `por_pagina`, `ordenar` (`data|valor|descricao|categoria|status`), `direcao`.

Todos combináveis. `[]` aceita repetição do parâmetro.

**200**:

```json
{
  "itens": [{
    "id": "…", "mundo": "digital", "tipo": "receita",
    "descricao": "Mensalidade CRM — Junho", "valor": "2000.00", "data": "2026-06-10",
    "status": "efetivado", "efetivar_automaticamente": false,
    "categoria": { "id": "…", "nome": "Clientes", "cor": "#2BAE76", "icone": "users", "especial": true, "vinculo": "cliente" },
    "subcategoria": { "id": "…", "nome": "Estrutural Vidros", "cor": null, "cliente_id": "…" },
    "servico": { "id": "…", "nome": "CRM", "mundo": "digital" },
    "centro_custo": null,
    "tags": [{ "id": "…", "nome": "recorrente", "cor": "#8B6CF0" }],
    "moeda_origem": "BRL", "valor_origem": null, "cotacao": null,
    "origem": { "tipo": "recorrencia", "id": "…", "rotulo": "Mensal desde 01/03/2025" },
    "tem_anexos": true, "quantidade_anexos": 2,
    "versao": 3
  }],
  "paginacao": { "pagina": 1, "por_pagina": 50, "total": 128, "total_paginas": 3 },
  "resumo_filtrado": {
    "total_receitas": "18400.00", "total_despesas": "9250.00", "resultado": "9150.00",
    "quantidade": 128
  },
  "quebra_por_mundo": { "digital": "7200.00", "infra": "1950.00" }
}
```

`resumo_filtrado` atende `FR-038` (soma do conjunto filtrado ao lado do contador).
`quebra_por_mundo` só vem quando `mundo=ambos` (`FR-003`).
`origem.tipo`: `recorrencia` | `parcelamento` | `split` | `manual` | `importacao` (`FR-043`).

### `POST /api/lancamentos` — criar (`FR-008`–`FR-014`)

**Papel**: gestor, operador

```json
{
  "mundo": "digital", "tipo": "despesa",
  "descricao": "Assinatura n8n Cloud", "data": "2026-07-29",
  "moeda": "USD", "valor": "50.00", "cotacao_manual": null,
  "categoria_id": "…", "subcategoria_id": null,
  "servico_id": null, "centro_custo_id": null,
  "tag_ids": ["…"], "observacoes": null,
  "efetivar_automaticamente": true
}
```

- `valor` é sempre positivo; o sinal vem de `tipo` (`RN-02`).
- `moeda: "USD"` → o servidor busca a cotação de `data` e grava BRL convertido, valor
  original, cotação e data (`RN-12`). `cotacao_manual` só é aceita quando a fonte externa
  falhou; nesse caso a resposta marca `cotacao_manual: true`.
- `data` no passado ou hoje → nasce `efetivado`. Futura → `programado` (`FR-024`).
- Categoria especial exige `subcategoria_id` (`RN-01`) → `409 regra_violada` / `RN-01`.
- `mundo` ausente → o cliente é obrigado a mandar; o servidor não adivinha do último uso.
  O **padrão do formulário** (mundo ativo, `FR-004`) é do frontend.

**201** devolve o lançamento no formato da lista.

### `GET /api/lancamentos/{id}` — detalhe (`FR-041`)

**Papel**: gestor, operador

Acrescenta ao formato da lista:

```json
{
  "anexos": [{ "id": "…", "nome_arquivo": "nf-1234.pdf", "mime_type": "application/pdf", "tamanho_bytes": 184320, "url": "<assinada, expira>" }],
  "partes_split": [{ "id": "…", "descricao": "…", "valor": "300.00", "categoria": {} }],
  "lancamento_pai": null,
  "serie": { "tipo": "recorrencia", "id": "…", "posicao": null, "total": null, "rotulo": "Mensal, dia 10" },
  "historico": [{ "acao": "edicao", "usuario": { "id": "…", "nome": "Lucas" }, "criado_em": "…", "alteracoes": { "valor": { "de": "1800.00", "para": "2000.00" } } }],
  "acoes_disponiveis": ["editar", "duplicar", "dividir", "excluir", "confirmar_efetivacao"]
}
```

`acoes_disponiveis` é calculado no servidor a partir do status e do papel — o frontend não
decide quando mostrar "confirmar recebimento" (`FR-042`).

### `PUT /api/lancamentos/{id}` — editar (`FR-016`, `RN-07`)

**Papel**: gestor, operador

Mesmo corpo do `POST`, mais:

```json
{
  "versao": 3,
  "escopo_serie": "apenas_esta",
  "confirmar_alteracao_historica": false
}
```

- `versao` obrigatória. Divergente → `409 conflito_versao` com o estado atual.
- `escopo_serie` obrigatório quando o lançamento vem de recorrência (`RN-07`); omitido →
  `422 confirmacao_necessaria` pedindo a escolha.
- Editar ocorrência passada já `efetivado` → `422` até `confirmar_alteracao_historica: true`.
- `mundo` no corpo diferente do gravado → `409 regra_violada` / `RN-15` (`FR-005`).

### `DELETE /api/lancamentos/{id}` — soft delete (`FR-017`, `RN-08`)

**Papel**: gestor, operador · **204**

Só a ocorrência; nunca a série (*edge case*). Split: excluir o pai exclui as partes; excluir
uma parte quebra `RN-11` → `409` orientando a ajustar as outras primeiro.

### `POST /api/lancamentos/{id}/efetivar` — confirmar de 1 clique (`FR-030`, `FR-042`)

**Papel**: gestor, operador · **200** com o lançamento atualizado

`pendente`/`atrasado` → `efetivado`, gravando `efetivado_em` e `efetivado_por`.
Já `efetivado` → `409`.

### `POST /api/lancamentos/{id}/cancelar` (`RN-03`)

**Papel**: gestor, operador · **200**

### `POST /api/lancamentos/{id}/duplicar` (`FR-018`)

**Papel**: gestor, operador · **201**

Cópia com `data` = hoje, status recalculado, sem anexos, sem vínculo de série.

### `POST /api/lancamentos/{id}/dividir` (`FR-019`, `FR-020`, `RN-11`)

**Papel**: gestor, operador

```json
{ "partes": [
  { "descricao": "Infraestrutura", "valor": "300.00", "categoria_id": "…", "subcategoria_id": null, "centro_custo_id": null },
  { "descricao": "Ferramentas",    "valor": "200.00", "categoria_id": "…", "subcategoria_id": null, "centro_custo_id": null }
] }
```

Soma ≠ valor do pai → `409 regra_violada` / `RN-11` com a diferença em `campos.partes`.
As partes herdam `mundo`, `data`, `tipo` e anexos do pai. Depois do split, **o pai sai dos
totais** — só as partes contam.

### `POST /api/lancamentos/lote` (`FR-021`)

**Papel**: gestor, operador

```json
{ "lancamentos": [ { …corpo do POST… } ] }
```

**Tudo ou nada**: uma linha inválida recusa o lote inteiro, apontando o índice.
Meio lote gravado em tabela editável é pior que nenhum.

**207 / 400**:

```json
{ "criados": 0, "erros": [{ "indice": 3, "codigo": "regra_violada", "requisito": "RN-01", "mensagem": "…" }] }
```

### `POST /api/lancamentos/acoes-em-massa` (`FR-040`)

**Papel**: gestor, operador

```json
{
  "lancamento_ids": ["…"],
  "acao": "mudar_categoria",
  "parametros": { "categoria_id": "…" }
}
```

`acao`: `excluir` | `mudar_categoria` | `mudar_status` | `adicionar_tags` | `remover_tags`.
Também tudo-ou-nada. Exportar em massa usa `GET /api/lancamentos/exportacao`.

---

## 2. Lixeira (`FR-017`, `RN-08`)

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/lixeira` | gestor, operador | Excluídos dentro do prazo de retenção, com `dias_restantes` |
| `POST /api/lixeira/{id}/restaurar` | gestor, operador | Restaura. Fora do prazo → `409 regra_violada` / `RN-08` |

Não existe exclusão definitiva por API — o histórico financeiro é permanente
(data-model §5.7).

---

## 3. Recorrências (`FR-025`–`FR-027`, `FR-034`)

| Endpoint | Papel | O quê |
|---|---|---|
| `GET /api/recorrencias` | gestor, operador | Lista, com `proxima_ocorrencia` e `ocorrencias_geradas` |
| `POST /api/recorrencias/previa` | gestor, operador | **Não grava.** Devolve a prévia de `FR-027` |
| `POST /api/recorrencias` | gestor, operador | Cria e materializa |
| `GET /api/recorrencias/{id}` | gestor, operador | Regra + ocorrências |
| `PUT /api/recorrencias/{id}` | gestor, operador | `escopo_serie` obrigatório (`RN-07`) |
| `POST /api/recorrencias/{id}/desativar` | gestor, operador | Para de gerar; remove futuras não efetivadas |
| `DELETE /api/recorrencias/{id}` | gestor | Soft delete da regra; ocorrências efetivadas ficam |

**`POST /api/recorrencias`**:

```json
{
  "mundo": "digital", "tipo": "receita",
  "descricao": "Mensalidade CRM — Estrutural Vidros", "valor": "2000.00",
  "categoria_id": "…", "subcategoria_id": "…",
  "servico_id": "…", "centro_custo_id": null,
  "frequencia": "mensal", "intervalo_dias": null,
  "dia_vencimento": 10, "mes_vencimento": null,
  "data_inicio": "2025-03-10", "data_fim": null, "total_parcelas": null,
  "efetivar_automaticamente": false,
  "cliente_id": "…", "funcionario_id": null,
  "confirmar_geracao_retroativa": false
}
```

- `data_inicio` no passado e `confirmar_geracao_retroativa: false` →
  `422 confirmacao_necessaria` com `previa` (`FR-027`), quando a contagem passa de
  `configuracoes.recorrencia_aviso_ocorrencias`.
- Ocorrências entre `data_inicio` e hoje nascem `efetivado` (`RN-05a`), mesmo com
  `efetivar_automaticamente: false` — o passado já aconteceu.
- `frequencia: "mensal"` com `dia_vencimento: 31` em fevereiro cai no **último dia do mês**
  (*edge case*).
- `data_fim` e `total_parcelas` são mutuamente exclusivos → `400 validacao`.

**Geração longa em lotes** (research.md D-02a): se a prévia indicar mais ocorrências do que
uma invocação consegue processar, a resposta `201` traz
`{ "geracao": { "concluida": false, "cursor": "…", "geradas": 200, "total": 640 } }` e o
cliente chama `POST /api/recorrencias/{id}/continuar-geracao` com o cursor até `concluida`.
O frontend mostra progresso (*edge case* "não trava a interface").

---

## 4. Parcelamento (`FR-028`)

### `POST /api/parcelamentos`

**Papel**: gestor, operador

```json
{
  "mundo": "digital", "tipo": "receita",
  "descricao": "Projeto site institucional", "valor_total": "12000.00",
  "total_parcelas": 3, "data_primeira_parcela": "2026-08-05", "intervalo": "mensal",
  "categoria_id": "…", "subcategoria_id": "…", "servico_id": "…",
  "efetivar_automaticamente": false
}
```

**201** cria 3 lançamentos vinculados com `parcela_numero`/`parcela_total`; a descrição
mostra a posição ("1/3"). Arredondamento: as primeiras parcelas levam o valor arredondado e
a **última absorve a diferença**, garantindo soma exata.

| Endpoint | Papel |
|---|---|
| `GET /api/parcelamentos/{id}` | gestor, operador |

---

## 5. Anexos (`FR-013`)

| Endpoint | Papel | O quê |
|---|---|---|
| `POST /api/lancamentos/{id}/anexos` | gestor, operador | `multipart/form-data`, múltiplos arquivos |
| `GET /api/anexos/{id}` | gestor, operador | `302` para URL assinada de curta validade |
| `DELETE /api/anexos/{id}` | gestor, operador | Remove registro e objeto do Storage |

Acima de `configuracoes.anexo_tamanho_max_mb` → `413 arquivo_grande` com o limite na
mensagem. MIME fora de `anexo_mime_permitidos` → `415 formato_nao_suportado`. Nunca falha em
silêncio (*edge case*).

O bucket é privado; não existe URL pública (data-model §3.12).

---

## 6. Importação e exportação (`FR-044`, `FR-045`)

| Endpoint | Papel | O quê |
|---|---|---|
| `POST /api/importacoes` | gestor, operador | Envia CSV/OFX. **Não grava.** Devolve `importacao_id`, colunas detectadas e prévia |
| `POST /api/importacoes/{id}/mapeamento` | gestor, operador | Coluna→campo + sugestão de categoria; devolve prévia validada |
| `POST /api/importacoes/{id}/confirmar` | gestor, operador | Grava. Em lotes com cursor, como as recorrências |
| `GET /api/lancamentos/exportacao?formato=csv&…` | gestor, operador | CSV da lista **com os filtros ativos** |

`mundo` é obrigatório no mapeamento — arquivo importado não traz mundo e `RN-15` não admite
nulo.

A importação **não** deduz mundo nem cria categorias novas: categoria não reconhecida é
apontada na prévia para o usuário escolher o destino.
