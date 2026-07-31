"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, mensagemDoErro, novaChaveIdempotencia, type Consulta } from "@/lib/api";
import { useInvalidarFinanceiro } from "@/lib/consultas";
import type { AcaoEmMassa, Lancamento, ParteSplit, RespostaLote, StatusLancamento } from "@/lib/tipos";

/**
 * As escritas de lançamento, num lugar só.
 *
 * Toda uma delas invalida o cache financeiro inteiro: criar um lançamento
 * muda saldo, Dashboard, Extrato, categorias e relatórios ao mesmo tempo, e
 * invalidar só a lista deixaria o resto da tela mostrando o número velho.
 *
 * O texto de sucesso é nosso (é interface). O texto de **erro** é sempre o do
 * backend (`RNF-02`) — `mensagemDoErro` devolve `erro.mensagem` como veio.
 */

function aviseOErro(e: unknown) {
  const texto = mensagemDoErro(e);
  if (texto) toast.error(texto);
}

export function useEfetivar() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (id: string) => api.post<Lancamento>(`/api/lancamentos/${id}/efetivar`),
    onSuccess: () => {
      invalidar();
      toast.success("Lançamento efetivado.");
    },
    onError: aviseOErro,
  });
}

export function useCancelar() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (id: string) => api.post<Lancamento>(`/api/lancamentos/${id}/cancelar`),
    onSuccess: () => {
      invalidar();
      toast.success("Lançamento cancelado. O histórico foi preservado.");
    },
    onError: aviseOErro,
  });
}

export function useDuplicar() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (id: string) => api.post<Lancamento>(`/api/lancamentos/${id}/duplicar`),
    onSuccess: () => {
      invalidar();
      toast.success("Cópia criada com a data de hoje.");
    },
    onError: aviseOErro,
  });
}

export function useExcluir() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/lancamentos/${id}`),
    onSuccess: () => {
      invalidar();
      toast.success("Lançamento movido para a lixeira.", {
        description: "Dá para restaurar enquanto estiver dentro do prazo de retenção.",
      });
    },
    onError: aviseOErro,
  });
}

export function useRestaurar() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (id: string) => api.post<Lancamento>(`/api/lixeira/${id}/restaurar`),
    onSuccess: () => {
      invalidar();
      toast.success("Lançamento restaurado.");
    },
    onError: aviseOErro,
  });
}

export function useDividir() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: ({ id, partes }: { id: string; partes: ParteSplit[] }) =>
      api.post<Lancamento[]>(`/api/lancamentos/${id}/dividir`, { corpo: { partes } }),
    onSuccess: () => {
      invalidar();
      toast.success("Lançamento dividido. O original saiu dos totais.");
    },
    // Sem `onError` global: o diálogo de split mostra a diferença que falta em
    // `campos.partes`, que é mais útil ali do que num aviso passageiro.
  });
}

export function useCriarLancamento() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      api.post<Lancamento>("/api/lancamentos", {
        corpo,
        chaveIdempotencia: novaChaveIdempotencia(),
      }),
    onSuccess: () => invalidar(),
  });
}

export function useEditarLancamento() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: Record<string, unknown> }) =>
      api.put<Lancamento>(`/api/lancamentos/${id}`, { corpo }),
    onSuccess: () => invalidar(),
  });
}

export function useCriarEmLote() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (lancamentos: Record<string, unknown>[]) =>
      api.post<RespostaLote>("/api/lancamentos/lote", {
        corpo: { lancamentos },
        chaveIdempotencia: novaChaveIdempotencia(),
      }),
    onSuccess: () => invalidar(),
  });
}

export function useAcaoEmMassa() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: ({
      ids,
      acao,
      parametros,
    }: {
      ids: string[];
      acao: AcaoEmMassa;
      parametros?: Record<string, unknown>;
    }) =>
      api.post<{ acao: AcaoEmMassa; afetados: number }>("/api/lancamentos/acoes-em-massa", {
        corpo: { lancamento_ids: ids, acao, parametros: parametros ?? {} },
      }),
    onSuccess: (r) => {
      invalidar();
      toast.success(`${r.afetados} ${r.afetados === 1 ? "lançamento alterado" : "lançamentos alterados"}.`);
    },
    onError: aviseOErro,
  });
}

export function useCriarParcelamento() {
  const invalidar = useInvalidarFinanceiro();
  return useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      api.post<{ id: string }>("/api/parcelamentos", {
        corpo,
        chaveIdempotencia: novaChaveIdempotencia(),
      }),
    onSuccess: () => invalidar(),
  });
}

/** Baixa o CSV da lista respeitando exatamente os filtros ativos (`FR-045`). */
export function montarUrlExportacao(consulta: Consulta): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(consulta)) {
    if (v === null || v === undefined || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.append(k, String(v));
  }
  p.set("formato", "csv");
  return `/api/lancamentos/exportacao?${p.toString()}`;
}

/**
 * Status em que o lançamento aceita confirmação de um clique (`FR-030`).
 *
 * Isto **não** é a regra de negócio reimplementada: a regra é do backend, que
 * responde `409` quando não cabe. É só quando vale a pena **oferecer** o
 * botão, decidido a partir do `status` que o próprio servidor mandou. No
 * painel de detalhe quem manda é `acoes_disponiveis` (`FR-042`).
 */
export function aceitaEfetivacaoRapida(status: StatusLancamento): boolean {
  return status === "pendente" || status === "atrasado" || status === "programado";
}
