"use client";

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
import { data as formatarData, dinheiro, inteiro } from "@/lib/formato";
import type { PreviaRecorrencia } from "@/lib/tipos";

/**
 * Confirmação de geração retroativa (T172, `FR-027`).
 *
 * Aparece quando o backend responde `422 confirmacao_necessaria`. **A frase
 * principal é a do servidor** (`erro.mensagem`) — os números abaixo são a
 * mesma `previa` destrinchada, para a pessoa conferir sem ler uma frase
 * comprida.
 */
export function DialogoGeracaoRetroativa({
  dados,
  aoConfirmar,
  aoCancelar,
}: {
  dados: { previa: PreviaRecorrencia; mensagem: string } | null;
  aoConfirmar: () => void;
  aoCancelar: () => void;
}) {
  return (
    <AlertDialog open={Boolean(dados)} onOpenChange={(v) => (!v ? aoCancelar() : undefined)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Isto vai criar lançamentos no passado</AlertDialogTitle>
          <AlertDialogDescription>{dados?.mensagem}</AlertDialogDescription>
        </AlertDialogHeader>

        {dados ? (
          <dl className="grid grid-cols-2 gap-3 rounded-[10px] bg-[var(--bg-subtle)] p-4 text-[13px]">
            <div>
              <dt className="text-sutil">Ocorrências</dt>
              <dd className="numerico font-[family-name:var(--font-display)] text-[16px] font-bold text-forte">
                {inteiro(dados.previa.total_ocorrencias)}
              </dd>
            </div>
            <div>
              <dt className="text-sutil">Já efetivadas</dt>
              <dd className="numerico font-[family-name:var(--font-display)] text-[16px] font-bold text-forte">
                {inteiro(dados.previa.retroativas_efetivadas)}
              </dd>
            </div>
            <div>
              <dt className="text-sutil">Intervalo</dt>
              <dd className="numerico text-[var(--fg)]">
                {formatarData(dados.previa.primeira)} a {formatarData(dados.previa.ultima)}
              </dd>
            </div>
            {dados.previa.valor_total_retroativo ? (
              <div>
                <dt className="text-sutil">Soma retroativa</dt>
                <dd className="numerico text-[var(--fg)]">
                  {dinheiro(dados.previa.valor_total_retroativo)}
                </dd>
              </div>
            ) : null}
          </dl>
        ) : null}

        <p className="text-[12px] text-sutil">
          As ocorrências entre o início e hoje nascem efetivadas e entram no saldo na hora.
        </p>

        <AlertDialogFooter>
          <AlertDialogCancel>Voltar e revisar</AlertDialogCancel>
          <AlertDialogAction onClick={aoConfirmar}>Criar assim mesmo</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
