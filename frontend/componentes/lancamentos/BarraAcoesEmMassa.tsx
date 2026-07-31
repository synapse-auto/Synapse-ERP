"use client";

import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/componentes/ui/popover";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/componentes/ui/alert-dialog";
import { rotuloDoStatus } from "@/componentes/comum/BadgeStatus";
import { useCategorias, useTags } from "@/lib/consultas";
import { useAcaoEmMassa } from "./acoes";

/**
 * Barra de ações em massa (T167, `FR-040`).
 *
 * As cinco ações do contrato: excluir, mudar categoria, mudar status,
 * adicionar e remover tags. **Tudo ou nada** — um id inexistente recusa a
 * chamada inteira, e o teto é de 500 ids; os dois são do servidor, e o aviso
 * de erro que aparece é o dele.
 *
 * `mudar_status` só oferece `efetivado` e `cancelado`: as outras transições
 * do ciclo são da rotina diária, na data, e não são ação de usuário
 * (`RN-03`).
 */
export function BarraAcoesEmMassa({
  ids,
  aoLimpar,
  aoExportar,
}: {
  ids: string[];
  aoLimpar: () => void;
  aoExportar: () => void;
}) {
  const { data: categorias } = useCategorias();
  const { data: tags } = useTags();
  const acao = useAcaoEmMassa();
  const [confirmarExclusao, setConfirmarExclusao] = useState(false);

  if (ids.length === 0) return null;

  const botao = cn(
    "flex h-[29px] items-center gap-1.5 rounded-[8px] border border-[var(--purple-200)] bg-superficie-cartao px-[11px]",
    "font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--lateral-ativo-fg)]",
    "transition-colors hover:bg-[var(--brand-tint)]",
  );

  function executar(
    tipo: Parameters<typeof acao.mutate>[0]["acao"],
    parametros?: Record<string, unknown>,
  ) {
    if (ids.length > 500) {
      toast.error("Máximo de 500 lançamentos por ação em massa. Estreite a seleção.");
      return;
    }
    acao.mutate({ ids, acao: tipo, parametros }, { onSuccess: aoLimpar });
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2.5 border-b border-[var(--purple-200)] bg-[var(--linha-selecionada)] px-4 py-[10px]">
        <span className="font-[family-name:var(--font-display)] text-[12.5px] font-bold text-[var(--lateral-ativo-fg)]">
          {ids.length} selecionados
        </span>
        <span aria-hidden className="h-[18px] w-px bg-[var(--purple-200)]" />

        <Popover>
          <PopoverTrigger className={botao}>Mudar categoria</PopoverTrigger>
          <PopoverContent align="start" className="w-[260px] p-2">
            <div className="flex max-h-[260px] flex-col gap-1 overflow-y-auto">
              {(categorias?.itens ?? []).map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => executar("mudar_categoria", { categoria_id: c.id })}
                  className="flex items-center gap-2 rounded-[8px] px-2 py-1.5 text-left text-[12.5px] hover:bg-[var(--bg-subtle)]"
                >
                  <span
                    aria-hidden
                    className="size-[7px] rounded-[2px]"
                    style={{ background: c.cor ?? "var(--fg-subtle)" }}
                  />
                  {c.nome}
                  {c.especial ? (
                    <span className="ml-auto text-[10px] text-sutil">exige subcategoria</span>
                  ) : null}
                </button>
              ))}
            </div>
          </PopoverContent>
        </Popover>

        <Popover>
          <PopoverTrigger className={botao}>Mudar status</PopoverTrigger>
          <PopoverContent align="start" className="w-[280px] p-2">
            <div className="flex flex-col gap-1">
              {(["efetivado", "cancelado"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => executar("mudar_status", { status: s })}
                  className="rounded-[8px] px-2 py-1.5 text-left text-[12.5px] hover:bg-[var(--bg-subtle)]"
                >
                  {rotuloDoStatus(s)}
                </button>
              ))}
            </div>
            <p className="mt-2 border-t border-linha-suave px-2 pt-2 text-[11px] text-sutil">
              Programado, pendente e atrasado são resolvidos pela rotina diária na data — não são
              escolha de usuário.
            </p>
          </PopoverContent>
        </Popover>

        <Popover>
          <PopoverTrigger className={botao}>Tags</PopoverTrigger>
          <PopoverContent align="start" className="w-[260px] p-2">
            <div className="flex max-h-[240px] flex-col gap-1 overflow-y-auto">
              {(tags?.itens ?? []).map((t) => (
                <div key={t.id} className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => executar("adicionar_tags", { tag_ids: [t.id] })}
                    className="flex-1 rounded-[8px] px-2 py-1.5 text-left text-[12.5px] hover:bg-[var(--bg-subtle)]"
                  >
                    {t.nome}
                  </button>
                  <button
                    type="button"
                    title="Remover esta tag dos selecionados"
                    onClick={() => executar("remover_tags", { tag_ids: [t.id] })}
                    className="rounded-[7px] px-2 py-1 text-[11px] text-sutil hover:bg-[var(--bg-subtle)]"
                  >
                    tirar
                  </button>
                </div>
              ))}
            </div>
          </PopoverContent>
        </Popover>

        <button type="button" className={botao} onClick={aoExportar}>
          Exportar
        </button>

        <button
          type="button"
          className={cn(botao, "border-[#F3CFCF] text-[var(--despesa-fg)] hover:bg-[var(--despesa-bg)]")}
          onClick={() => setConfirmarExclusao(true)}
        >
          Excluir
        </button>

        <div className="flex-1" />
        <button type="button" onClick={aoLimpar} className="text-[12px] text-suave hover:text-[var(--fg)]">
          cancelar seleção
        </button>
      </div>

      <AlertDialog open={confirmarExclusao} onOpenChange={setConfirmarExclusao}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir {ids.length} lançamentos?</AlertDialogTitle>
            <AlertDialogDescription>
              Todos vão para a lixeira de uma vez. Se algum não puder ser excluído, nenhum é —
              a operação é tudo ou nada.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Voltar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => executar("excluir")}
              className="bg-[var(--danger-500)] text-white hover:bg-[var(--danger-500)]/90"
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
