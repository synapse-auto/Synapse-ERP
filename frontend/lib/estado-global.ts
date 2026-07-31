/**
 * Estado global de leitura: **mundo** e **período** (T150, `FR-001`).
 *
 * Os dois vivem em três lugares ao mesmo tempo, de propósito:
 *
 * - **na loja (zustand)** — é o que os componentes leem;
 * - **na URL** — para poder copiar o link e cair na mesma tela filtrada, e
 *   para o botão voltar do navegador fazer sentido;
 * - **no `localStorage`** — `FR-001` pede que a escolha sobreviva entre
 *   sessões; o mockup abre no mundo em que a pessoa estava.
 *
 * A ordem de precedência ao carregar é: URL > armazenado > padrão. Quem chega
 * por um link compartilhado vê o que o link diz, não o que a máquina lembrava.
 *
 * O mundo **não** é inferido no servidor (contracts/README.md §Mundo): o
 * cliente sempre manda. Este arquivo é a única fonte desse valor.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { AtalhoPeriodo, MundoFiltro } from "./tipos";

export const MUNDOS: { valor: MundoFiltro; rotulo: string; corVar: string }[] = [
  { valor: "digital", rotulo: "Digital", corVar: "var(--mundo-digital)" },
  { valor: "infra", rotulo: "Infra", corVar: "var(--mundo-infra)" },
  { valor: "ambos", rotulo: "Ambos", corVar: "var(--mundo-ambos)" },
];

/**
 * Os atalhos de período que o cabeçalho mostra. Quem resolve as datas é o
 * servidor (contracts/README.md §Período) — aqui só existe o rótulo e a
 * chave que vai na query, para o comparativo usar exatamente a mesma régua.
 */
export const PERIODOS: { valor: AtalhoPeriodo; rotulo: string; curto: string }[] = [
  { valor: "hoje", rotulo: "Hoje", curto: "Hoje" },
  { valor: "esta_semana", rotulo: "Esta semana", curto: "Semana" },
  { valor: "este_mes", rotulo: "Este mês", curto: "Mês" },
  { valor: "mes_passado", rotulo: "Mês passado", curto: "Anterior" },
  { valor: "ultimos_3_meses", rotulo: "Últimos 3 meses", curto: "3 meses" },
  { valor: "este_ano", rotulo: "Este ano", curto: "Ano" },
  { valor: "personalizado", rotulo: "Personalizado", curto: "Escolher" },
];

export interface EstadoGlobal {
  mundo: MundoFiltro;
  periodo: AtalhoPeriodo;
  /** Só usados quando `periodo === "personalizado"`. */
  dataInicio: string | null;
  dataFim: string | null;
  /** Marcado depois que a URL foi lida uma vez, para não sobrescrever o link. */
  hidratado: boolean;

  definirMundo: (mundo: MundoFiltro) => void;
  definirPeriodo: (periodo: AtalhoPeriodo, inicio?: string | null, fim?: string | null) => void;
  hidratarDaUrl: (params: URLSearchParams) => void;
}

const MUNDOS_VALIDOS = new Set<string>(MUNDOS.map((m) => m.valor));
const PERIODOS_VALIDOS = new Set<string>(PERIODOS.map((p) => p.valor));

export const useEstadoGlobal = create<EstadoGlobal>()(
  persist(
    (set) => ({
      mundo: "ambos",
      periodo: "este_mes",
      dataInicio: null,
      dataFim: null,
      hidratado: false,

      definirMundo: (mundo) => set({ mundo }),

      definirPeriodo: (periodo, inicio = null, fim = null) =>
        set(
          periodo === "personalizado"
            ? { periodo, dataInicio: inicio, dataFim: fim }
            : { periodo, dataInicio: null, dataFim: null },
        ),

      hidratarDaUrl: (params) =>
        set((estado) => {
          if (estado.hidratado) return estado;
          const mundo = params.get("mundo");
          const periodo = params.get("periodo");
          const inicio = params.get("data_inicio");
          const fim = params.get("data_fim");
          return {
            hidratado: true,
            mundo: mundo && MUNDOS_VALIDOS.has(mundo) ? (mundo as MundoFiltro) : estado.mundo,
            periodo:
              periodo && PERIODOS_VALIDOS.has(periodo) ? (periodo as AtalhoPeriodo) : estado.periodo,
            dataInicio: inicio ?? estado.dataInicio,
            dataFim: fim ?? estado.dataFim,
          };
        }),
    }),
    {
      name: "synapse-erp:escopo",
      storage: createJSONStorage(() => localStorage),
      // `hidratado` é de sessão: não sobrevive ao recarregar, senão a URL
      // deixaria de ser lida na próxima visita.
      partialize: (estado) => ({
        mundo: estado.mundo,
        periodo: estado.periodo,
        dataInicio: estado.dataInicio,
        dataFim: estado.dataFim,
      }),
    },
  ),
);

/**
 * Estado de interface que atravessa telas: o formulário de novo lançamento
 * (aberto pelo cabeçalho, pelo atalho `N` e por vários botões espalhados) e a
 * busca global. Não persiste — é estado de momento, não escolha do usuário.
 */
export interface EstadoUi {
  novoLancamentoAberto: boolean;
  /** Preenche o formulário quando ele abre a partir de um contexto. */
  rascunhoNovoLancamento: Record<string, unknown> | null;
  buscaAberta: boolean;
  abrirNovoLancamento: (rascunho?: Record<string, unknown> | null) => void;
  fecharNovoLancamento: () => void;
  definirBuscaAberta: (v: boolean) => void;
}

export const useEstadoUi = create<EstadoUi>()((set) => ({
  novoLancamentoAberto: false,
  rascunhoNovoLancamento: null,
  buscaAberta: false,
  abrirNovoLancamento: (rascunho = null) =>
    set({ novoLancamentoAberto: true, rascunhoNovoLancamento: rascunho }),
  fecharNovoLancamento: () =>
    set({ novoLancamentoAberto: false, rascunhoNovoLancamento: null }),
  definirBuscaAberta: (v) => set({ buscaAberta: v }),
}));

/** Parâmetros de mundo e período prontos para qualquer chamada de leitura. */
export function parametrosDeEscopo(estado: {
  mundo: MundoFiltro;
  periodo: AtalhoPeriodo;
  dataInicio: string | null;
  dataFim: string | null;
}): Record<string, string> {
  const p: Record<string, string> = { mundo: estado.mundo, periodo: estado.periodo };
  if (estado.periodo === "personalizado") {
    if (estado.dataInicio) p.data_inicio = estado.dataInicio;
    if (estado.dataFim) p.data_fim = estado.dataFim;
  }
  return p;
}

/**
 * Chave de cache do TanStack Query. Toda consulta de dado financeiro entra
 * com o escopo na chave: trocar de mundo tem que invalidar tudo, senão a tela
 * mostra o mundo errado por um instante — que é justamente o que `SC-005`
 * proíbe.
 */
export function chaveDeEscopo(estado: {
  mundo: MundoFiltro;
  periodo: AtalhoPeriodo;
  dataInicio: string | null;
  dataFim: string | null;
}): [MundoFiltro, AtalhoPeriodo, string | null, string | null] {
  return [estado.mundo, estado.periodo, estado.dataInicio, estado.dataFim];
}
