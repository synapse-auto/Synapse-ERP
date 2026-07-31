"use client";

import { useState, type ReactNode } from "react";
import { Ban, CheckCircle2, Copy, Pencil, Scissors, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/componentes/ui/dropdown-menu";
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
import { DialogoSplit } from "./DialogoSplit";
import { aceitaEfetivacaoRapida, useCancelar, useDuplicar, useEfetivar, useExcluir } from "./acoes";
import { dinheiro } from "@/lib/formato";
import type { Lancamento } from "@/lib/tipos";

/**
 * Menu de ações da linha (`FR-042`, `FR-030`).
 *
 * "Confirmar" só aparece quando o `status` que veio do servidor admite —
 * ver a nota em `aceitaEfetivacaoRapida`. Excluir passa por confirmação
 * porque é a única ação da lista que muda o saldo sem a pessoa ver o valor.
 */
export function MenuDoLancamento({
  lancamento,
  aoEditar,
  children,
}: {
  lancamento: Lancamento;
  aoEditar: () => void;
  children: ReactNode;
}) {
  const [confirmarExclusao, setConfirmarExclusao] = useState(false);
  const [splitAberto, setSplitAberto] = useState(false);

  const efetivar = useEfetivar();
  const cancelar = useCancelar();
  const duplicar = useDuplicar();
  const excluir = useExcluir();

  const podeEfetivar = aceitaEfetivacaoRapida(lancamento.status);
  const podeCancelar = lancamento.status !== "cancelado";
  const ehParteDeSplit = lancamento.origem.tipo === "split";

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-[228px]">
          {podeEfetivar ? (
            <>
              <DropdownMenuItem onSelect={() => efetivar.mutate(lancamento.id)}>
                <CheckCircle2 size={15} />
                {lancamento.tipo === "receita" ? "Confirmar recebimento" : "Confirmar pagamento"}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          ) : null}

          <DropdownMenuItem onSelect={aoEditar}>
            <Pencil size={15} />
            Editar
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => duplicar.mutate(lancamento.id)}>
            <Copy size={15} />
            Duplicar
          </DropdownMenuItem>
          {!ehParteDeSplit ? (
            <DropdownMenuItem onSelect={() => setSplitAberto(true)}>
              <Scissors size={15} />
              Dividir em partes
            </DropdownMenuItem>
          ) : null}

          <DropdownMenuSeparator />
          {podeCancelar ? (
            <DropdownMenuItem onSelect={() => cancelar.mutate(lancamento.id)}>
              <Ban size={15} />
              Cancelar
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem variant="destructive" onSelect={() => setConfirmarExclusao(true)}>
            <Trash2 size={15} />
            Excluir
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirmarExclusao} onOpenChange={setConfirmarExclusao}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir este lançamento?</AlertDialogTitle>
            <AlertDialogDescription>
              {lancamento.descricao} — {dinheiro(lancamento.valor)}. Ele vai para a lixeira e
              some do saldo; dá para restaurar enquanto estiver dentro do prazo de retenção.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Voltar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => excluir.mutate(lancamento.id)}
              className="bg-[var(--danger-500)] text-white hover:bg-[var(--danger-500)]/90"
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <DialogoSplit
        lancamento={lancamento}
        aberto={splitAberto}
        aoFechar={() => setSplitAberto(false)}
      />
    </>
  );
}
