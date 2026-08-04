# Backend — Plataforma Financeira Synapse

FastAPI + SQLAlchemy 2 Core + asyncpg sobre o Postgres do Supabase. Publicado como
função Python na Vercel; o Next.js faz proxy de `/api/*` para cá (research.md D-02).

Contexto do projeto: [`CLAUDE.md`](../CLAUDE.md) ·
[constituição](../.specify/memory/constitution.md) ·
[plano](../specs/001-erp-financeiro-synapse/plan.md) ·
[contratos](../specs/001-erp-financeiro-synapse/contracts/)

## Como rodar

```powershell
cd backend
uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r pyproject.toml --extra dev
Copy-Item .env.exemplo .env      # preencher com os valores do Supabase
uvicorn app.main:app --reload --port 8000
```

> **Não existe `requirements.txt` neste projeto, e é de propósito.** As dependências
> vivem em [`pyproject.toml`](pyproject.toml), porque é de lá que a **Vercel** instala:
> havendo um `pyproject.toml`, ela ignora o `requirements.txt` por completo. Manter os
> dois seria manter duas listas da mesma coisa — e a que ficaria desatualizada é
> justamente a que roda em produção. Custou um deploy quebrado para descobrir; o
> histórico está no cabeçalho do `pyproject.toml`.
>
> `--extra dev` traz uvicorn, pytest, ruff e black. **A função da Vercel não os
> instala** — lá vai só o que está em `[project.dependencies]`.

- `http://localhost:8000/api/saude` → `{"status":"ok","banco":"ok","versao":"…"}`
- `http://localhost:8000/api/docs` → a documentação que o Princípio IV exige
- `http://localhost:8000/` → redireciona para `/api/docs` (ver
  [Por que a raiz redireciona](#por-que-a-raiz-redireciona))

> ⚠️ **Não crie o `.env` com `Set-Content` nem com `>` no PowerShell.** O Windows
> PowerShell escreve UTF-8 **com BOM**, e o BOM cola na primeira linha do arquivo: a
> primeira variável passa a se chamar `﻿DATABASE_URL` e o app sobe reclamando que
> `database_url` está faltando — mesmo com a linha visivelmente ali. Custou uma
> depuração real durante o B0.
>
> `Copy-Item .env.exemplo .env` é seguro (copia byte a byte, e o exemplo não tem BOM).
> Se precisar gerar por script:
>
> ```powershell
> [System.IO.File]::WriteAllText("$PWD\.env", $conteudo, (New-Object System.Text.UTF8Encoding($false)))
> ```

```powershell
pytest                       # unidade + contrato + integração
pytest -m "not integracao"   # sem precisar de Postgres
pytest -m lento              # só os de desempenho — ver o aviso abaixo
ruff check . ; black --check .
```

> Os testes marcados **`lento`** estão fora da execução padrão (`addopts` no
> `pyproject.toml`). Eles inserem 5.000 linhas e cronometram a resposta — rodados contra o
> Supabase remoto a partir de uma estação de trabalho, medem a latência da internet, não a
> da aplicação: 14s num Dashboard que o backend implantado devolve em 1,7s. Rode-os de
> onde a medida signifique alguma coisa.

## Onde as coisas moram

| Pasta | Responsabilidade |
|---|---|
| `app/dominio/` | **Todas** as `RN-xx`, um módulo por regra. Nenhuma regra fora daqui |
| `app/comum/` | Erro, paginação, período, idempotência, auditoria |
| `app/seguranca/` | `auth.py` valida o token; `rbac.py` decide o papel |
| `app/<dominio>/` | `rotas.py` → `servico.py` → `repositorio.py`, nessa ordem de dependência |
| `migracoes/` | SQL versionado, `001`…`014` (data-model §7) |
| `api/index.py` | Só reexporta o app para a Vercel |

Camada de tela **nunca** fala com o banco, e `repositorio.py` **nunca** contém regra de
negócio (Princípio IV).

## Decisões que surpreendem quem lê o código pela primeira vez

**O backend mantém um pool pequeno, e isso mudou em 2026-08-04.** Antes era `NullPool`
— uma conexão nova por requisição, deixando todo o pooling para o Supabase, pelo medo
de função serverless congelada com conexão pendurada. Medido contra o banco real, o
medo custava caro: **2812 ms por consulta com `NullPool` contra 1328 ms com pool
reaproveitado**, porque conexão nova paga handshake TLS, autenticação no pooler e a
introspecção de tipos do asyncpg (cara aqui, porque o schema usa enums próprios). O
medo original é endereçado por `pool_pre_ping` e `pool_recycle`, não ignorado.
`DB_POOL_TAMANHO=0` volta ao arranjo antigo sem tocar em código. Ver o cabeçalho de
[`app/db.py`](app/db.py).

**Prepared statement desligado, e não dá para religar.** No pooler em modo *transaction*
a conexão troca entre requisições e o statement preparado não existe na nova.
`DATABASE_URL` tem que apontar para a **porta 6543**, não a 5432. Tentado de novo em
2026-08-04 agora que há pool: valeria mais 440 ms por consulta e o pooler responde
`InvalidSQLStatementNameError` sob concorrência. Fica desligado. O preço é replanejar
toda consulta (`Planning 1.45 ms` contra `Execution 0.18 ms` no `EXPLAIN` do Dashboard),
e é por isso que o caminho escolhido foi **reduzir o número de consultas**, não acelerar
cada uma.

**Leitura também abre transação, e cortar isso quebra.** O `BEGIN`/`COMMIT` de todo
`GET` parece desperdício — são duas viagens de rede a mais. Tentado em 2026-08-04:
entregar leitura em `AUTOCOMMIT` produz `InvalidSQLStatementNameError` **intermitente**,
com nome de statement único (ou seja, não é colisão). No pooler em modo *transaction*, é
a transação aberta que obriga o pooler a manter o cliente na mesma conexão de servidor
entre o `Parse` e o `Bind` do asyncpg. Sem ela, as duas etapas podem cair em conexões
diferentes. Revertido, e escrito por extenso na nota 4 de [`app/db.py`](app/db.py) —
é o tipo de erro que passa em teste e falha em produção.

**O Dashboard faz três consultas, não vinte.** [`app/dashboard/repositorio.py`](app/dashboard/repositorio.py)
expõe `numeros`, `series` e `blocos`; cada uma junta o que antes eram funções separadas
chamadas em série pela rota. Medido: **9,2x mais rápido, com 101 valores conferidos um a
um contra a implementação anterior e nenhuma divergência**.

**`not exists` dentro de `filter (where …)` não vira anti-join.** O planejador o executa
por linha e **não reaproveita entre agregados** — o `EXPLAIN` mostrava `SubPlan 1`,
`SubPlan 3` e `SubPlan 5`, três planos idênticos para a mesma pergunta. Por isso o
recorte do pai de split (`RN-11`) virou junção lateral em `dashboard/repositorio.py` e
`lancamentos/repositorio.py`. Onde a condição cai no `WHERE` — é o caso de
`relatorios/repositorio.py` — ela continua `not exists`, porque ali o anti-join acontece.

**Só ES256 é aceito no token.** O projeto usa chave assimétrica (JWKS) — conferido em
2026-07-30, fecha o "a verificar" de research.md D-03. Não há segredo de JWT em
ambiente: o que se busca é chave pública. Nenhum caminho HS256 foi escrito.

**Token válido não basta.** O papel mora em `usuarios`, não no token. Sem linha ativa
lá, a resposta é `401` — é o que impede que alguém que se cadastre sozinho no Auth
entre no sistema.

**RLS está ligada sem nenhuma política, e é assim de propósito.** Ver
[`migracoes/006_rls.sql`](migracoes/006_rls.sql). O linter do Supabase aponta
`rls_enabled_no_policy` nas **20** tabelas (19 do desenho + `importacoes`, da migração
`011`); é o resultado esperado, conferido pela última vez em 2026-07-31. Nenhum ERROR nem
WARN. Quem "consertar" isso adicionando política estará abrindo as finanças da empresa
para a chave que vive no navegador.

**A ordem das rotas em `app/lancamentos/rotas.py` é significativa.** `/lote`,
`/acoes-em-massa` e `/exportacao` são declaradas **antes** de `/{lancamento_id}`. O FastAPI
casa a rota na ordem de registro: invertendo, `GET /api/lancamentos/exportacao` tentaria ler
"exportacao" como UUID e responderia `400`. O `/api/docs` continuaria listando as duas rotas
normalmente, então o bug só apareceria em produção — por isso há teste de contrato para essa
ordem.

**O Storage é chamado por HTTP direto, sem a `supabase-py`.** São três operações (subir,
assinar, apagar) e a biblioteca arrasta `storage3`, `gotrue` e `postgrest` junto — peso que
o pacote da função não comporta. Ver o cabeçalho de
[`app/anexos/armazenamento.py`](app/anexos/armazenamento.py).

**O CSV da exportação é o único lugar da API em formato brasileiro.** `;` como separador,
`1.234,50`, `dd/mm/aaaa` e BOM UTF-8. O resto da API transporta ISO e decimal em string
(contracts/README.md); aquele arquivo é aberto no Excel por uma pessoa, então vale `RNF-03`.

**No SQL escreve-se `%` uma vez só, nunca `%%`.** O `%` do `pg_trgm` é o operador de
similaridade das buscas por texto. A dobra é o escape de percent do paramstyle `pyformat`;
o dialeto **asyncpg** usa parâmetro numerado (`$1`) e não desescapa nada, então `%%` chega
literal ao Postgres e vira `operator does not exist: text %% unknown`. Custou um `500` em
`/api/busca`, `/api/lancamentos?busca=` e `/api/clientes?busca=` (corrigido em 2026-08-02).

**Campo de enum no modelo de entrada é `Literal`, nunca `str`.** Com `str` o valor
atravessa o Pydantic intacto e só morre no `cast(:x as meu_enum)` do Postgres, como
`InvalidTextRepresentationError` — que sai `500 erro_interno` onde contracts/README.md
manda `400 validacao` com o nome do campo. Era o caso de `tipo_cobranca` em
`app/clientes/rotas.py` (corrigido em 2026-08-02) e de `tipo_contratacao` em
`app/funcionarios/rotas.py`, que escapou da primeira varredura e caiu na auditoria de
requisitos de 2026-08-03. Vale para todo enum do banco: `tipo_cobranca`,
`tipo_contratacao`, `status`, `papel`. **`mundo` é a exceção que confirma a regra**: fica
`str` no modelo porque quem valida é `mod_mundo.exige`, o dono de `RN-15` — e ele já
responde `400` com a mensagem certa.

**Rota com `response_class=Response` tem que devolver `JSONResponse`, não `dict`.** Os
quatro relatórios declaram isso para poderem responder CSV e PDF, e a declaração torna o
`Response` cru — que só aceita `bytes`/`str` — a classe padrão de **todo** retorno da
função. Devolver o `dict` do formato `json` fazia o Starlette chamar `.encode()` nele:
`AttributeError: 'dict' object has no attribute 'encode'`, `500` em toda a tela de
Relatórios. O helper `_json()` de [`app/relatorios/rotas.py`](app/relatorios/rotas.py)
existe para que a próxima rota de formato duplo não repita o erro.

**Cliente retroativo não tem código de geração próprio — e isso foi o ponto (2026-08-04).**
"Carregar o histórico de um cliente que já era cliente há 18 meses" parece pedir um caminho
novo de gravação: gerar N datas, montar N lançamentos, inseri-los. Não pede. A recorrência
já fazia tudo — `RN-05a` faz ocorrência passada nascer `efetivado`, o *clamp* do dia 31
existe, `insert … select from unnest` grava o lote numa ida ao banco e o índice único
`(recorrencia_id, data)` cuida da idempotência. **A única coisa que faltava era
`data_inicio` deixar de ser fixo em `date.today()`** no cadastro de cliente.

O que foi escrito de fato: [`app/dominio/cliente_retroativo.py`](app/dominio/cliente_retroativo.py),
que decide **qual mês é aceitável** (não futuro, não além de
`configuracoes.cliente_retroativo_meses_maximo`, só em cobrança recorrente, mês corrente =
nada de retroativo). Medido:
[`tests/integracao/test_cliente_retroativo.py`](tests/integracao/test_cliente_retroativo.py)
conta os `execute` da conexão e prova que 36 meses custam **as mesmas 13 idas ao banco** que
6 — o teste falha se algum dia alguém trocar isso por um laço de `insert`.

O `POST /api/clientes` passou a aceitar `Idempotency-Key` na mesma leva. Sem ela, a
repetição que a Vercel faz depois de um timeout criaria um **segundo cliente** com o
histórico inteiro de novo: o `on conflict` da ocorrência não pega esse caso, porque a
recorrência seria outra, e o caixa contaria o passado duas vezes.

**"Cliente desde" é derivado, não coluna.** `least(criado_em, receita efetivada mais
antiga)`, calculado no `select` que a lista e o perfil já faziam — zero ida ao banco a mais,
que é o que custa caro aqui. Gravar criaria uma segunda verdade para manter em dia toda vez
que um lançamento antigo fosse editado, cancelado ou restaurado da lixeira. Mesmo raciocínio
de `RN-10` (data-model §3.4).

## Por que `vercel.json` não tem `rewrites`

Tentador escrever `{"source": "/(.*)", "destination": "/api/index"}` para mandar tudo
para a função. **Não faça isso.** O build avisa:

> WARNING! Internal rewrites in backend framework projects now route requests using the
> rewritten destination path.

Ou seja: a Vercel entrega ao app o caminho **já reescrito**. Pedindo `/api/saude`, o
FastAPI recebe `/api/index` — que não existe — e devolve 404 em **toda** rota. O sintoma
engana, porque o app está vivo e respondendo; só nunca casa nenhuma rota.

Com o preset **FastAPI** (Settings → General → Framework), a Vercel já roteia todos os
caminhos para o app. O `vercel.json` só declara o cron.

## Por que a raiz redireciona

`GET /` e `GET /api` respondem **307** para `/api/docs` ([`app/main.py`](app/main.py)).

Todo endpoint deste serviço mora sob `/api/...`, então a raiz não casava rota nenhuma e caía
no handler de 404:

```json
{"erro":{"codigo":"nao_encontrado","mensagem":"Endereço não encontrado.","requisito":null,"campos":null}}
```

Quem abre a URL do deploy no navegador — o primeiro reflexo de qualquer um — lia isso como
"o backend está quebrado". É o contrário: **essa mensagem é nossa**, logo o app está de pé e
respondendo. Vercel com rota inexistente devolve HTML `404: NOT_FOUND`, não JSON. Esse é o
teste rápido para separar os dois casos:

| O que aparece | O que significa |
|---|---|
| JSON com `"codigo":"nao_encontrado"` | App vivo, caminho sem rota |
| HTML `404: NOT_FOUND` | A requisição nem chegou na função — roteamento da Vercel |
| `FUNCTION_INVOCATION_FAILED` | O módulo estourou no import (ver cabeçalho do `pyproject.toml`) |

O redirecionamento **não entra no OpenAPI** (`include_in_schema=False`): é atalho de
navegação, não endpoint de negócio, e `contracts/plataforma.md` não o declara como rota —
listá-lo em `/api/docs` criaria a divergência que `T208` trata como bug. Está registrado em
prosa no §7 daquele contrato, e há teste de regressão para as duas coisas
(`test_raiz_leva_para_a_documentacao`, `test_raiz_nao_entra_no_contrato_publicado`).

## ⚠️ Divergências entre o contrato e a plataforma

Declaradas em voz alta porque a constituição não aceita resolver conflito em silêncio.

### 1. ✅ Resolvida em B2/T084 — o Vercel Cron não chama `POST` com `X-Segredo-Rotina`

`contracts/plataforma.md §6` especifica
`POST /api/rotinas/diaria` protegido pelo cabeçalho `X-Segredo-Rotina`. A plataforma
não permite isso: o Vercel Cron invoca o caminho com **`GET`** e **não envia cabeçalho
personalizado** — ele envia `Authorization: Bearer $CRON_SECRET` quando a variável
`CRON_SECRET` existe no projeto.

**Implementado como planejado**, em `app/rotinas/rotas.py`:

- `POST /api/rotinas/diaria` + `X-Segredo-Rotina` — como o contrato diz, para disparo
  manual.
- `GET /api/rotinas/diaria` — para o cron, validando `Authorization: Bearer <segredo>`.
- Os dois passam pela mesma dependência `exige_segredo_da_rotina` e conferem o **mesmo**
  segredo, com `hmac.compare_digest` (tempo constante). Na Vercel, `CRON_SECRET` e
  `SEGREDO_ROTINA` recebem o mesmo valor.

`contracts/plataforma.md §6` registra o `GET` e o motivo. Há teste de contrato exigindo
que ele apareça no `/api/docs` — endpoint que existe e não está documentado é o tipo de
divergência que T208 trata como bug.

### 2. ✅ Resolvida em 2026-07-31 — idempotência agora sobrevive à instância

Ficou aberta bem mais tempo do que devia. [`app/comum/idempotencia.py`](app/comum/idempotencia.py)
guardava a chave **em memória do processo**, o que cobria clique duplo na mesma instância
quente e nada mais — enquanto o caso que o mecanismo existe para cobrir é a repetição que
a Vercel faz após timeout de rede, que normalmente cai em instância nova, com memória
vazia. Dois lançamentos iguais, valor contado em dobro no saldo.

O fechamento estava planejado para `T056` e não aconteceu; a auditoria de fim do Boss 2
o encontrou ainda aberto.

**Implementado**: tabela `chaves_idempotencia` na migração **`012`** (a `009` já tinha
sido usada por `anexo_url_assinada_segundos`), com PK `(usuario_id, rota, chave)` — a
mesma tripla que o módulo já usava. A escrita acontece na **mesma transação** da operação,
então operação desfeita desfaz a chave junto. A PK também é a trava do caso concorrente:
duas invocações simultâneas fazem a segunda falhar no `insert` em vez de duplicar a linha.

A rotina diária apaga as chaves vencidas — é estado temporário, como `importacoes`, e são
as duas únicas tabelas do sistema em que apagar linha é o certo.

## Variáveis de ambiente

Lista completa e comentada em [`.env.exemplo`](.env.exemplo). Nenhum `os.environ` solto
no código: quem precisa importa `app.config.obter_configuracao` (Princípio VII).
