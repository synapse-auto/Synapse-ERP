"use client";

import { useMemo } from "react";
import {
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown, MoreHorizontal, Paperclip, Repeat } from "lucide-react";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/componentes/ui/checkbox";
import { BadgeStatus } from "@/componentes/comum/BadgeStatus";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { DataBR } from "@/componentes/comum/DataBR";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { MenuDoLancamento } from "./MenuDoLancamento";
import { useEstadoGlobal } from "@/lib/estado-global";
import { dinheiro } from "@/lib/formato";
import type { Lancamento } from "@/lib/tipos";
import type { FiltrosLancamento } from "./filtros";

/**
 * Tabela de lançamentos (T162, `FR-036`).
 *
 * O mockup não usa `<table>`: usa uma grade CSS de nove faixas
 * (`38px 92px minmax(220px,1fr) 190px 160px 128px 118px 128px 40px`) com
 * linhas de 54px. Mantemos a grade — é o que dá o alinhamento das colunas
 * mesmo com conteúdo de larguras diferentes — e usamos o TanStack Table para
 * o que ele resolve bem: seleção de linhas e estado de ordenação.
 *
 * **A ordenação é do servidor** (`manualSorting`). Ordenar a página atual no
 * navegador daria uma ordem que não é a ordem do filtro inteiro — 50 de 128
 * ordenados parecem certos e não são.
 */

/**
 * As nove faixas somam 1114px no mínimo. O `min-w` é o que faz a rolagem
 * horizontal acontecer **dentro** da tabela, e não na página inteira — sem ele
 * o celular arrasta a tela toda de lado (`SC-012`, `FR-111`).
 */
const GRADE =
  "grid min-w-[1114px] grid-cols-[38px_92px_minmax(220px,1fr)_190px_160px_128px_118px_128px_40px]";

type Coluna = FiltrosLancamento["ordenar"];

const CABECALHOS: { chave: Coluna | null; rotulo: string; alinharDireita?: boolean }[] = [
  { chave: "data", rotulo: "Data" },
  { chave: "descricao", rotulo: "Descrição" },
  { chave: "categoria", rotulo: "Categoria" },
  { chave: null, rotulo: "Serviço" },
  { chave: null, rotulo: "Tags" },
  { chave: "status", rotulo: "Status" },
  { chave: "valor", rotulo: "Valor", alinharDireita: true },
];

export function TabelaLancamentos({
  itens,
  carregando,
  selecionadoId,
  marcados,
  aoMudarMarcados,
  aoAbrir,
  aoEditar,
  filtros,
  aoOrdenar,
  className,
}: {
  itens: Lancamento[];
  carregando?: boolean;
  selecionadoId: string | null;
  marcados: RowSelectionState;
  aoMudarMarcados: (v: RowSelectionState) => void;
  aoAbrir: (id: string) => void;
  aoEditar: (id: string) => void;
  filtros: FiltrosLancamento;
  aoOrdenar: (coluna: Coluna) => void;
  className?: string;
}) {
  const mundoGlobal = useEstadoGlobal((e) => e.mundo);
  const mostrarMundo = mundoGlobal === "ambos" && !filtros.mundoDaLista;

  const colunas = useMemo<ColumnDef<Lancamento>[]>(
    () => [{ id: "sel", accessorKey: "id" }],
    [],
  );

  const ordenacao: SortingState = [{ id: filtros.ordenar, desc: filtros.direcao === "desc" }];

  const tabela = useReactTable({
    data: itens,
    columns: colunas,
    state: { rowSelection: marcados, sorting: ordenacao },
    getRowId: (l) => l.id,
    enableRowSelection: true,
    manualSorting: true,
    manualPagination: true,
    onRowSelectionChange: (atualizador) =>
      aoMudarMarcados(typeof atualizador === "function" ? atualizador(marcados) : atualizador),
    getCoreRowModel: getCoreRowModel(),
  });

  const linhas = tabela.getRowModel().rows;
  const todosMarcados = linhas.length > 0 && linhas.every((l) => l.getIsSelected());
  const algunsMarcados = linhas.some((l) => l.getIsSelected()) && !todosMarcados;

  return (
    <div className={cn("overflow-x-auto [overscroll-behavior-x:contain]", className)}>
      {/* Cabeçalho da grade — 38px, fundo #FBFAFE */}
      <div
        className={cn(
          GRADE,
          "h-[38px] items-center border-b border-linha-suave bg-[var(--superficie-lateral)] px-4",
        )}
      >
        <span>
          <Checkbox
            aria-label="Marcar todos os lançamentos da página"
            checked={todosMarcados ? true : algunsMarcados ? "indeterminate" : false}
            onCheckedChange={(v) => tabela.toggleAllRowsSelected(Boolean(v))}
          />
        </span>
        {CABECALHOS.map((c) => {
          const ativa = c.chave && filtros.ordenar === c.chave;
          const Seta = !c.chave
            ? null
            : ativa
              ? filtros.direcao === "asc"
                ? ArrowUp
                : ArrowDown
              : ChevronsUpDown;
          return (
            <span
              key={c.rotulo}
              className={cn("min-w-0", c.alinharDireita && "text-right")}
            >
              {c.chave ? (
                <button
                  type="button"
                  onClick={() => aoOrdenar(c.chave as Coluna)}
                  className={cn(
                    "inline-flex items-center gap-1 font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.07em] uppercase transition-colors",
                    ativa ? "text-[var(--brand-hover)]" : "text-sutil hover:text-[var(--fg-muted)]",
                  )}
                >
                  {c.rotulo}
                  {Seta ? <Seta size={11} strokeWidth={2.4} className={ativa ? "" : "opacity-50"} /> : null}
                </button>
              ) : (
                <span className="font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.07em] text-sutil uppercase">
                  {c.rotulo}
                </span>
              )}
            </span>
          );
        })}
        <span />
      </div>

      {carregando && itens.length === 0 ? (
        <div className="flex flex-col">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={cn(GRADE, "min-h-[54px] items-center border-b border-[var(--linha-suave)] px-4")}>
              <span />
              <span className="h-3 w-12 animate-pulse rounded bg-[var(--bg-subtle)]" />
              <span className="mr-6 h-3 animate-pulse rounded bg-[var(--bg-subtle)]" />
              <span className="mr-4 h-3 animate-pulse rounded bg-[var(--bg-subtle)]" />
              <span className="mr-4 h-3 animate-pulse rounded bg-[var(--bg-subtle)]" />
              <span />
              <span className="h-4 w-20 animate-pulse rounded-full bg-[var(--bg-subtle)]" />
              <span className="h-3 animate-pulse rounded bg-[var(--bg-subtle)]" />
              <span />
            </div>
          ))}
        </div>
      ) : itens.length === 0 ? (
        <EstadoVazio
          titulo="Nenhum lançamento neste recorte"
          descricao="Nada bate com o mundo, o período e os filtros escolhidos. Tire um filtro ou amplie o período."
        />
      ) : (
        <div role="rowgroup">
          {linhas.map((linha) => {
            const l = linha.original;
            const selecionado = selecionadoId === l.id;
            const marcado = linha.getIsSelected();
            return (
              <div
                key={l.id}
                role="row"
                tabIndex={0}
                onClick={() => aoAbrir(l.id)}
                onDoubleClick={() => aoEditar(l.id)}
                aria-label={`Abrir ${l.descricao}`}
                onKeyDown={(e) => {
                  // `Espaço` também abre: é o que se espera de uma linha
                  // focável, e sem isso a página rola em vez de abrir.
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    aoAbrir(l.id);
                  }
                }}
                className={cn(
                  GRADE,
                  "min-h-[54px] cursor-pointer items-center border-b border-[var(--linha-suave)] px-4",
                  "transition-colors duration-[var(--dur-fast)] hover:bg-[var(--linha-hover)]",
                  // A linha é larga: o anel roxo padrão contornaria a tela toda.
                  // Aqui o foco é uma borda interna, que cabe na linha.
                  "focus-visible:bg-[var(--linha-selecionada)] focus-visible:shadow-[inset_0_0_0_2px_var(--brand)] focus-visible:outline-none",
                  selecionado
                    ? "bg-[var(--linha-selecionada)]"
                    : marcado
                      ? "bg-[var(--linha-marcada)]"
                      : "bg-superficie-cartao",
                  l.status === "cancelado" && "opacity-60",
                )}
              >
                <span onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    aria-label={`Marcar ${l.descricao}`}
                    checked={marcado}
                    onCheckedChange={(v) => linha.toggleSelected(Boolean(v))}
                  />
                </span>

                <DataBR valor={l.data} formato="empilhada" />

                <span className="flex min-w-0 items-center gap-2 pr-[18px]">
                  <span
                    className={cn(
                      "truncate text-[14px] font-medium text-[var(--fg)]",
                      l.status === "cancelado" && "line-through",
                    )}
                  >
                    {l.descricao}
                  </span>
                  {mostrarMundo ? <BadgeMundo mundo={l.mundo} className="flex-none" /> : null}
                  {l.origem.tipo === "recorrencia" ? (
                    <span
                      title={l.origem.rotulo ?? "Recorrente"}
                      className="flex flex-none text-[var(--purple-400)]"
                    >
                      <Repeat size={13} strokeWidth={2.2} />
                    </span>
                  ) : null}
                  {l.parcela_numero && l.parcela_total ? (
                    <span
                      title={l.origem.rotulo ?? "Parcelado"}
                      className="flex-none rounded-[4px] bg-[var(--st-pendente-bg)] px-[5px] py-[1px] font-[family-name:var(--font-display)] text-[10px] font-extrabold text-[var(--st-pendente-fg)]"
                    >
                      {l.parcela_numero}/{l.parcela_total}
                    </span>
                  ) : null}
                  {l.tem_anexos ? (
                    <span className="flex flex-none items-center gap-[2px] text-[11px] text-[var(--ink-300)]">
                      <Paperclip size={12} strokeWidth={2.2} />
                      {l.quantidade_anexos}
                    </span>
                  ) : null}
                  {l.moeda_origem !== "BRL" ? (
                    <span className="flex-none rounded-[4px] bg-[var(--receita-bg)] px-[5px] py-[1px] font-[family-name:var(--font-display)] text-[10px] font-extrabold tracking-[0.03em] text-[var(--receita-fg)]">
                      {l.moeda_origem}
                    </span>
                  ) : null}
                </span>

                <span className="flex min-w-0 items-center gap-[7px] pr-[14px]">
                  <span
                    aria-hidden
                    className="size-[7px] flex-none rounded-[2.5px]"
                    style={{ background: l.categoria.cor ?? "var(--fg-subtle)" }}
                  />
                  <span className="truncate text-[13px] text-[var(--ink-700)] dark:text-[var(--fg)]">
                    {l.categoria.nome}
                    {l.subcategoria ? (
                      <span className="text-sutil"> · {l.subcategoria.nome}</span>
                    ) : null}
                  </span>
                </span>

                <span className="truncate pr-3 text-[12px] text-suave">
                  {l.servico?.nome ?? "—"}
                </span>

                <span className="flex gap-1 overflow-hidden pr-[10px]">
                  {l.tags.map((t) => (
                    <span
                      key={t.id}
                      className="rounded-full bg-segmento px-[7px] py-[2px] font-[family-name:var(--font-display)] text-[10px] font-semibold whitespace-nowrap"
                      style={{ color: t.cor ?? "var(--fg-muted)" }}
                    >
                      {t.nome}
                    </span>
                  ))}
                </span>

                <span>
                  <BadgeStatus status={l.status} compacto />
                </span>

                <span
                  className="numerico text-right font-[family-name:var(--font-display)] text-[14px] font-bold whitespace-nowrap"
                  style={{
                    color:
                      l.status === "efetivado"
                        ? l.tipo === "receita"
                          ? "var(--receita-fg)"
                          : "var(--despesa-fg)"
                        : "var(--valor-previsto-fg)",
                  }}
                >
                  {l.tipo === "receita" ? "+ " : "− "}
                  {dinheiro(l.valor)}
                </span>

                <span className="flex justify-end" onClick={(e) => e.stopPropagation()}>
                  <MenuDoLancamento lancamento={l} aoEditar={() => aoEditar(l.id)}>
                    <button
                      type="button"
                      aria-label="Ações do lançamento"
                      className="flex size-[26px] items-center justify-center rounded-[6px] text-[var(--ink-300)] transition-colors hover:bg-[var(--bg-muted)] hover:text-[var(--ink-600)]"
                    >
                      <MoreHorizontal size={15} />
                    </button>
                  </MenuDoLancamento>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
