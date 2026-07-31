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
  return saida;
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
