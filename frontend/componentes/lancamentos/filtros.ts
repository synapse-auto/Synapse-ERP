import type { Consulta } from "@/lib/api";
import type { Mundo, StatusLancamento, TipoLancamento } from "@/lib/tipos";

/**
 * Os filtros combináveis de `FR-037`.
 *
 * Todos moram num objeto só para "limpar todos" ser uma linha e para o
 * contador de marcadores ativos não depender de lembrar quantos campos
 * existem — foi assim que o mockup desenhou a barra.
 */
export interface FiltrosLancamento {
  busca: string;
  tipo: TipoLancamento | "";
  status: StatusLancamento[];
  categoria_id: string[];
  subcategoria_id: string[];
  servico_id: string[];
  centro_custo_id: string[];
  tag_id: string[];
  valor_min: string;
  valor_max: string;
  /** Restringe a um mundo **dentro** do modo "Ambos" (mockup: `fMundo`). */
  mundoDaLista: Mundo | "";
  ordenar: "data" | "valor" | "descricao" | "categoria" | "status";
  direcao: "asc" | "desc";
  pagina: number;
  por_pagina: number;
}

export const FILTROS_VAZIOS: FiltrosLancamento = {
  busca: "",
  tipo: "",
  status: [],
  categoria_id: [],
  subcategoria_id: [],
  servico_id: [],
  centro_custo_id: [],
  tag_id: [],
  valor_min: "",
  valor_max: "",
  mundoDaLista: "",
  ordenar: "data",
  direcao: "desc",
  pagina: 1,
  por_pagina: 50,
};

/** Traduz para a query da API. Campos vazios somem (o cliente `api` já poda). */
export function paraConsulta(f: FiltrosLancamento): Consulta {
  return {
    busca: f.busca.trim() || undefined,
    tipo: f.tipo || undefined,
    status: f.status.length ? f.status : undefined,
    categoria_id: f.categoria_id.length ? f.categoria_id : undefined,
    subcategoria_id: f.subcategoria_id.length ? f.subcategoria_id : undefined,
    servico_id: f.servico_id.length ? f.servico_id : undefined,
    centro_custo_id: f.centro_custo_id.length ? f.centro_custo_id : undefined,
    tag_id: f.tag_id.length ? f.tag_id : undefined,
    valor_min: f.valor_min || undefined,
    valor_max: f.valor_max || undefined,
    // Sobrepõe o mundo global — só existe quando o global está em "ambos".
    mundo: f.mundoDaLista || undefined,
    ordenar: f.ordenar,
    direcao: f.direcao,
    pagina: f.pagina,
    por_pagina: f.por_pagina,
  };
}

/**
 * Aplica um `filtro_drilldown` vindo do Dashboard (`FR-058`).
 * O corpo já vem pronto do servidor — aqui só se acomoda no formato local,
 * sem inventar filtro nenhum.
 */
export function deDrilldown(
  drilldown: Record<string, unknown> | null | undefined,
): Partial<FiltrosLancamento> {
  if (!drilldown) return {};
  const saida: Partial<FiltrosLancamento> = {};
  const lista = (v: unknown): string[] =>
    Array.isArray(v) ? v.map(String) : v == null ? [] : [String(v)];

  if ("tipo" in drilldown && drilldown.tipo) saida.tipo = String(drilldown.tipo) as TipoLancamento;
  if ("status" in drilldown) saida.status = lista(drilldown.status) as StatusLancamento[];
  if ("categoria_id" in drilldown) saida.categoria_id = lista(drilldown.categoria_id);
  if ("subcategoria_id" in drilldown) saida.subcategoria_id = lista(drilldown.subcategoria_id);
  if ("servico_id" in drilldown) saida.servico_id = lista(drilldown.servico_id);
  if ("centro_custo_id" in drilldown) saida.centro_custo_id = lista(drilldown.centro_custo_id);
  if ("tag_id" in drilldown) saida.tag_id = lista(drilldown.tag_id);
  if ("busca" in drilldown && drilldown.busca) saida.busca = String(drilldown.busca);
  saida.pagina = 1;
  return saida;
}

/**
 * As chaves que a tela de Lançamentos manda para a URL. `mundo` **não** está
 * aqui: aquele é o mundo global do cabeçalho, escrito por `espelho-de-url.ts`.
 * O mundo desta lista viaja como `mundo_lista` para os dois não se atropelarem.
 */
const CHAVES_DE_URL = [
  "busca",
  "tipo",
  "status",
  "categoria_id",
  "subcategoria_id",
  "servico_id",
  "centro_custo_id",
  "tag_id",
  "valor_min",
  "valor_max",
  "mundo_lista",
  "ordenar",
  "direcao",
  "pagina",
] as const;

/** Lê o `?...` da URL — é como o Dashboard entrega o drill-down para a tela. */
export function daUrl(params: URLSearchParams): Partial<FiltrosLancamento> {
  const saida: Partial<FiltrosLancamento> = {};
  const busca = params.get("busca");
  if (busca) saida.busca = busca;
  const tipo = params.get("tipo");
  if (tipo === "receita" || tipo === "despesa") saida.tipo = tipo;
  const status = params.getAll("status") as StatusLancamento[];
  if (status.length) saida.status = status;
  const cat = params.getAll("categoria_id");
  if (cat.length) saida.categoria_id = cat;
  const sub = params.getAll("subcategoria_id");
  if (sub.length) saida.subcategoria_id = sub;
  const svc = params.getAll("servico_id");
  if (svc.length) saida.servico_id = svc;
  const cc = params.getAll("centro_custo_id");
  if (cc.length) saida.centro_custo_id = cc;
  const tag = params.getAll("tag_id");
  if (tag.length) saida.tag_id = tag;

  // T214 — o resto da barra também vive na URL agora.
  const min = params.get("valor_min");
  if (min) saida.valor_min = min;
  const max = params.get("valor_max");
  if (max) saida.valor_max = max;
  const mundoLista = params.get("mundo_lista");
  if (mundoLista === "digital" || mundoLista === "infra") saida.mundoDaLista = mundoLista;
  const ordenar = params.get("ordenar");
  if (
    ordenar === "data" ||
    ordenar === "valor" ||
    ordenar === "descricao" ||
    ordenar === "categoria" ||
    ordenar === "status"
  )
    saida.ordenar = ordenar;
  const direcao = params.get("direcao");
  if (direcao === "asc" || direcao === "desc") saida.direcao = direcao;
  const pagina = Number(params.get("pagina"));
  if (Number.isInteger(pagina) && pagina > 1) saida.pagina = pagina;

  return saida;
}

/**
 * O caminho de volta: filtros → URL (T214, Web Interface Guidelines).
 *
 * Sem isso, filtrar e mandar o link para outra pessoa mandava a lista crua —
 * e recarregar a página perdia o recorte. Escreve **por cima** dos parâmetros
 * que já existem (mundo, período, `selecionado`), nunca apaga o que não é seu.
 *
 * Valor padrão não vai para a URL: `?ordenar=data&direcao=desc&pagina=1` é
 * ruído em cima de um endereço que a pessoa vai copiar.
 */
export function paraUrl(f: FiltrosLancamento, base: URLSearchParams): URLSearchParams {
  const alvo = new URLSearchParams(base.toString());
  for (const chave of CHAVES_DE_URL) alvo.delete(chave);

  if (f.busca.trim()) alvo.set("busca", f.busca.trim());
  if (f.tipo) alvo.set("tipo", f.tipo);
  for (const s of f.status) alvo.append("status", s);
  for (const id of f.categoria_id) alvo.append("categoria_id", id);
  for (const id of f.subcategoria_id) alvo.append("subcategoria_id", id);
  for (const id of f.servico_id) alvo.append("servico_id", id);
  for (const id of f.centro_custo_id) alvo.append("centro_custo_id", id);
  for (const id of f.tag_id) alvo.append("tag_id", id);
  if (f.valor_min) alvo.set("valor_min", f.valor_min);
  if (f.valor_max) alvo.set("valor_max", f.valor_max);
  if (f.mundoDaLista) alvo.set("mundo_lista", f.mundoDaLista);
  if (f.ordenar !== FILTROS_VAZIOS.ordenar) alvo.set("ordenar", f.ordenar);
  if (f.direcao !== FILTROS_VAZIOS.direcao) alvo.set("direcao", f.direcao);
  if (f.pagina > 1) alvo.set("pagina", String(f.pagina));

  return alvo;
}

/** Quantos marcadores estão ativos — o "limpar tudo" só aparece acima de zero. */
export function quantidadeAtiva(f: FiltrosLancamento): number {
  return (
    (f.busca.trim() ? 1 : 0) +
    (f.tipo ? 1 : 0) +
    f.status.length +
    f.categoria_id.length +
    f.subcategoria_id.length +
    f.servico_id.length +
    f.centro_custo_id.length +
    f.tag_id.length +
    (f.valor_min ? 1 : 0) +
    (f.valor_max ? 1 : 0) +
    (f.mundoDaLista ? 1 : 0)
  );
}
