"use client";

/**
 * Consultas ao backend, num lugar só.
 *
 * Cada hook é um wrapper fino sobre o TanStack Query. Duas regras:
 *
 * 1. **Nenhuma regra de negócio aqui.** O que se decide neste arquivo é
 *    cache, chave e parâmetro. Quem decide `atrasado`, `inadimplente`,
 *    semáforo ou rótulo de card é o backend (Princípio III).
 * 2. **Escopo na chave.** Toda leitura de dado financeiro leva mundo e
 *    período na `queryKey`, senão trocar de mundo mostraria o mundo anterior
 *    por um instante — o que `SC-005` proíbe.
 */

import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import type { UseQueryOptions } from "@tanstack/react-query";
import { api, type Consulta } from "./api";
import { chaveDeEscopo, parametrosDeEscopo, useEstadoGlobal } from "./estado-global";
import type {
  Categoria,
  CentroCusto,
  Cliente,
  ClientePerfil,
  Configuracoes,
  Dashboard,
  Dre,
  EstadoRotina,
  Extrato,
  Funcionario,
  FuncionarioPerfil,
  Lancamento,
  LancamentoDetalhe,
  ListaLancamentos,
  ListaNotificacoes,
  MatrizMensal,
  PaginaDe,
  Parcelamento,
  Recorrencia,
  RelatorioClientes,
  RelatorioVariacao,
  ResultadoBusca,
  Saldo,
  Servico,
  Sessao,
  Tag,
  Usuario,
} from "./tipos";

/* ------------------------------------------------------------------ */
/* Escopo (mundo + período) — a mesma régua para todas as consultas    */
/* ------------------------------------------------------------------ */

export function useEscopo() {
  const mundo = useEstadoGlobal((e) => e.mundo);
  const periodo = useEstadoGlobal((e) => e.periodo);
  const dataInicio = useEstadoGlobal((e) => e.dataInicio);
  const dataFim = useEstadoGlobal((e) => e.dataFim);
  const estado = { mundo, periodo, dataInicio, dataFim };
  return {
    ...estado,
    parametros: parametrosDeEscopo(estado),
    chave: chaveDeEscopo(estado),
  };
}

/* ------------------------------------------------------------------ */
/* Chaves de cache                                                     */
/* ------------------------------------------------------------------ */

export const chaves = {
  sessao: ["sessao"] as const,
  saldo: (escopo: unknown) => ["saldo", escopo] as const,
  dashboard: (escopo: unknown, cards?: string[]) => ["dashboard", escopo, cards ?? null] as const,
  extrato: (escopo: unknown, agrupamento: string) => ["extrato", escopo, agrupamento] as const,
  lancamentos: (escopo: unknown, filtros: unknown) => ["lancamentos", escopo, filtros] as const,
  lancamento: (id: string) => ["lancamento", id] as const,
  lixeira: ["lixeira"] as const,
  categorias: (escopo: unknown, incluirArquivadas: boolean) =>
    ["categorias", escopo, incluirArquivadas] as const,
  tags: ["tags"] as const,
  servicos: (mundo: string) => ["servicos", mundo] as const,
  centrosCusto: (mundo: string) => ["centros-custo", mundo] as const,
  clientes: (escopo: unknown, filtros: unknown) => ["clientes", escopo, filtros] as const,
  cliente: (id: string, escopo: unknown) => ["cliente", id, escopo] as const,
  funcionarios: (escopo: unknown, incluirArquivados: boolean) =>
    ["funcionarios", escopo, incluirArquivados] as const,
  funcionario: (id: string, escopo: unknown) => ["funcionario", id, escopo] as const,
  recorrencias: (escopo: unknown) => ["recorrencias", escopo] as const,
  recorrencia: (id: string) => ["recorrencia", id] as const,
  parcelamento: (id: string) => ["parcelamento", id] as const,
  notificacoes: (apenasNaoLidas: boolean) => ["notificacoes", apenasNaoLidas] as const,
  configuracoes: ["configuracoes"] as const,
  usuarios: ["usuarios"] as const,
  auditoria: (filtros: unknown) => ["auditoria", filtros] as const,
  busca: (termo: string, mundo: string) => ["busca", termo, mundo] as const,
  dre: (escopo: unknown) => ["dre", escopo] as const,
  relatorioClientes: (escopo: unknown) => ["relatorio-clientes", escopo] as const,
  variacaoCategorias: (escopo: unknown) => ["variacao-categorias", escopo] as const,
  matrizMensal: (escopo: unknown) => ["matriz-mensal", escopo] as const,
  estadoRotina: ["estado-rotina"] as const,
};

/**
 * Invalida tudo que depende de lançamento. Chamado depois de criar, editar,
 * efetivar, excluir, dividir, importar — qualquer escrita muda saldo,
 * Dashboard, Extrato e relatórios ao mesmo tempo.
 */
export function useInvalidarFinanceiro() {
  const cliente = useQueryClient();
  return () => {
    for (const raiz of [
      "saldo",
      "dashboard",
      "extrato",
      "lancamentos",
      "lancamento",
      "lixeira",
      "categorias",
      "clientes",
      "cliente",
      "funcionarios",
      "funcionario",
      "recorrencias",
      "recorrencia",
      "parcelamento",
      "dre",
      "relatorio-clientes",
      "variacao-categorias",
      "matriz-mensal",
      "notificacoes",
    ]) {
      cliente.invalidateQueries({ queryKey: [raiz] });
    }
  };
}

/* ------------------------------------------------------------------ */
/* Plataforma                                                          */
/* ------------------------------------------------------------------ */

export function useSessao(opcoes?: Partial<UseQueryOptions<Sessao>>) {
  return useQuery<Sessao>({
    queryKey: chaves.sessao,
    queryFn: () => api.get<Sessao>("/api/sessao"),
    staleTime: 5 * 60_000,
    ...opcoes,
  });
}

export function useSalvarPreferencias() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (corpo: {
      tema?: string;
      dashboard_cards?: { id: string; visivel: boolean; ordem: number }[];
    }) => api.post<unknown>("/api/sessao/preferencias", { corpo }),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: chaves.sessao });
      cliente.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useSaldo() {
  const escopo = useEscopo();
  return useQuery<Saldo>({
    queryKey: chaves.saldo(escopo.chave),
    queryFn: () => api.get<Saldo>("/api/saldo", { consulta: { mundo: escopo.mundo } }),
  });
}

export function useNotificacoes(apenasNaoLidas = false) {
  return useQuery<ListaNotificacoes>({
    queryKey: chaves.notificacoes(apenasNaoLidas),
    queryFn: () =>
      api.get<ListaNotificacoes>("/api/notificacoes", {
        consulta: { apenas_nao_lidas: apenasNaoLidas || undefined, por_pagina: 30 },
      }),
    staleTime: 60_000,
  });
}

export function useConfiguracoes() {
  return useQuery<Configuracoes>({
    queryKey: chaves.configuracoes,
    queryFn: () => api.get<Configuracoes>("/api/configuracoes"),
    staleTime: 10 * 60_000,
  });
}

export function useUsuarios(habilitado = true) {
  return useQuery<PaginaDe<Usuario> | { itens: Usuario[] }>({
    queryKey: chaves.usuarios,
    queryFn: () => api.get("/api/usuarios"),
    enabled: habilitado,
  });
}

export function useEstadoRotina(habilitado = true) {
  return useQuery<EstadoRotina>({
    queryKey: chaves.estadoRotina,
    queryFn: () => api.get<EstadoRotina>("/api/rotinas/estado"),
    enabled: habilitado,
  });
}

export function useBusca(termo: string) {
  const { mundo } = useEscopo();
  const limpo = termo.trim();
  return useQuery<ResultadoBusca>({
    queryKey: chaves.busca(limpo, mundo),
    // Abaixo de 2 caracteres o backend devolve listas vazias em vez de varrer
    // a tabela; nem chamamos.
    enabled: limpo.length >= 2,
    queryFn: () => api.get<ResultadoBusca>("/api/busca", { consulta: { q: limpo, mundo, limite: 8 } }),
    placeholderData: keepPreviousData,
  });
}

/* ------------------------------------------------------------------ */
/* Consultas de leitura                                                */
/* ------------------------------------------------------------------ */

export function useDashboard(cards?: string[]) {
  const escopo = useEscopo();
  return useQuery<Dashboard>({
    queryKey: chaves.dashboard(escopo.chave, cards),
    queryFn: () =>
      api.get<Dashboard>("/api/dashboard", {
        consulta: { ...escopo.parametros, cards },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useExtrato(agrupamento: "dia" | "semana" | "mes") {
  const escopo = useEscopo();
  return useQuery<Extrato>({
    queryKey: chaves.extrato(escopo.chave, agrupamento),
    queryFn: () =>
      api.get<Extrato>("/api/extrato", { consulta: { ...escopo.parametros, agrupamento } }),
    placeholderData: keepPreviousData,
  });
}

export function useLancamentos(filtros: Consulta) {
  const escopo = useEscopo();
  return useQuery<ListaLancamentos>({
    queryKey: chaves.lancamentos(escopo.chave, filtros),
    queryFn: () =>
      api.get<ListaLancamentos>("/api/lancamentos", {
        consulta: { ...escopo.parametros, ...filtros },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useLancamento(id: string | null) {
  return useQuery<LancamentoDetalhe>({
    queryKey: chaves.lancamento(id ?? ""),
    queryFn: () => api.get<LancamentoDetalhe>(`/api/lancamentos/${id}`),
    enabled: Boolean(id),
  });
}

export function useLixeira() {
  return useQuery<PaginaDe<Lancamento>>({
    queryKey: chaves.lixeira,
    queryFn: () => api.get<PaginaDe<Lancamento>>("/api/lixeira"),
  });
}

export function useCategorias(incluirArquivadas = false) {
  const escopo = useEscopo();
  return useQuery<{ itens: Categoria[] }>({
    queryKey: chaves.categorias(escopo.chave, incluirArquivadas),
    queryFn: () =>
      api.get<{ itens: Categoria[] }>("/api/categorias", {
        consulta: {
          ...escopo.parametros,
          incluir_arquivados: incluirArquivadas || undefined,
        },
      }),
    staleTime: 2 * 60_000,
  });
}

export function useTags() {
  return useQuery<{ itens: Tag[] }>({
    queryKey: chaves.tags,
    queryFn: () => api.get<{ itens: Tag[] }>("/api/tags"),
    staleTime: 10 * 60_000,
  });
}

export function useServicos(mundo?: string) {
  const escopo = useEscopo();
  const alvo = mundo ?? escopo.mundo;
  return useQuery<{ itens: Servico[] }>({
    queryKey: chaves.servicos(alvo),
    queryFn: () => api.get<{ itens: Servico[] }>("/api/servicos", { consulta: { mundo: alvo } }),
    staleTime: 10 * 60_000,
  });
}

export function useCentrosCusto(mundo?: string) {
  const escopo = useEscopo();
  const alvo = mundo ?? escopo.mundo;
  return useQuery<{ itens: CentroCusto[] }>({
    queryKey: chaves.centrosCusto(alvo),
    queryFn: () =>
      api.get<{ itens: CentroCusto[] }>("/api/centros-custo", { consulta: { mundo: alvo } }),
    staleTime: 10 * 60_000,
  });
}

export function useClientes(filtros: Consulta = {}) {
  const escopo = useEscopo();
  return useQuery<PaginaDe<Cliente>>({
    queryKey: chaves.clientes(escopo.chave, filtros),
    queryFn: () =>
      api.get<PaginaDe<Cliente>>("/api/clientes", { consulta: { ...escopo.parametros, ...filtros } }),
    placeholderData: keepPreviousData,
  });
}

export function useCliente(id: string) {
  const escopo = useEscopo();
  return useQuery<ClientePerfil>({
    queryKey: chaves.cliente(id, escopo.chave),
    queryFn: () => api.get<ClientePerfil>(`/api/clientes/${id}`, { consulta: escopo.parametros }),
    enabled: Boolean(id),
  });
}

export function useFuncionarios(incluirArquivados = false) {
  const escopo = useEscopo();
  return useQuery<PaginaDe<Funcionario>>({
    queryKey: chaves.funcionarios(escopo.chave, incluirArquivados),
    queryFn: () =>
      api.get<PaginaDe<Funcionario>>("/api/funcionarios", {
        consulta: { ...escopo.parametros, incluir_arquivados: incluirArquivados || undefined },
      }),
  });
}

export function useFuncionario(id: string) {
  const escopo = useEscopo();
  return useQuery<FuncionarioPerfil>({
    queryKey: chaves.funcionario(id, escopo.chave),
    queryFn: () =>
      api.get<FuncionarioPerfil>(`/api/funcionarios/${id}`, { consulta: escopo.parametros }),
    enabled: Boolean(id),
  });
}

export function useRecorrencias() {
  const escopo = useEscopo();
  return useQuery<PaginaDe<Recorrencia>>({
    queryKey: chaves.recorrencias(escopo.chave),
    queryFn: () =>
      api.get<PaginaDe<Recorrencia>>("/api/recorrencias", { consulta: { mundo: escopo.mundo } }),
  });
}

export function useParcelamento(id: string | null) {
  return useQuery<Parcelamento>({
    queryKey: chaves.parcelamento(id ?? ""),
    queryFn: () => api.get<Parcelamento>(`/api/parcelamentos/${id}`),
    enabled: Boolean(id),
  });
}

/* ------------------------------------------------------------------ */
/* Relatórios                                                          */
/* ------------------------------------------------------------------ */

export function useDre(habilitado = true) {
  const escopo = useEscopo();
  return useQuery<Dre>({
    queryKey: chaves.dre(escopo.chave),
    queryFn: () => api.get<Dre>("/api/relatorios/dre", { consulta: escopo.parametros }),
    enabled: habilitado,
    placeholderData: keepPreviousData,
  });
}

export function useRelatorioClientes(habilitado = true) {
  const escopo = useEscopo();
  return useQuery<RelatorioClientes>({
    queryKey: chaves.relatorioClientes(escopo.chave),
    queryFn: () =>
      api.get<RelatorioClientes>("/api/relatorios/clientes", { consulta: escopo.parametros }),
    enabled: habilitado,
    placeholderData: keepPreviousData,
  });
}

export function useVariacaoCategorias(habilitado = true) {
  const escopo = useEscopo();
  return useQuery<RelatorioVariacao>({
    queryKey: chaves.variacaoCategorias(escopo.chave),
    queryFn: () =>
      api.get<RelatorioVariacao>("/api/relatorios/variacao-categorias", {
        consulta: escopo.parametros,
      }),
    enabled: habilitado,
    placeholderData: keepPreviousData,
  });
}

export function useMatrizMensal(habilitado = true) {
  const escopo = useEscopo();
  return useQuery<MatrizMensal>({
    queryKey: chaves.matrizMensal(escopo.chave),
    queryFn: () =>
      api.get<MatrizMensal>("/api/relatorios/matriz-mensal", { consulta: escopo.parametros }),
    enabled: habilitado,
    placeholderData: keepPreviousData,
  });
}
