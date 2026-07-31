"use client";

import { useState } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/componentes/ui/alert-dialog";
import { Button } from "@/componentes/ui/button";
import type { EscopoSerie } from "@/lib/tipos";

/**
 * "Só este" / "Este e os futuros" (T171, `FR-034`, `RN-07`).
 *
 * É o comportamento do Google Agenda, escolhido de propósito em research.md
 * D-13: é o que a pessoa já conhece de outro sistema.
 *
 * Aparece ao salvar a edição de um lançamento que **veio de uma recorrência**.
 * O contrato exige `escopo_serie` nesse caso; sem ele o servidor responde
 * `422` pedindo a escolha — este diálogo existe para a pergunta chegar antes,
 * junto do contexto, e não como erro depois.
 *
 * `apenas_esta` altera só a ocorrência. `esta_e_futuras` substitui a regra e
 * regera as ocorrências de hoje em diante ainda **não efetivadas** — as
 * efetivadas nunca são tocadas, nem no futuro.
 */
export function DialogoSerie({
  aberto,
  rotuloDaSerie,
  aoEscolher,
  aoCancelar,
}: {
  aberto: boolean;
  rotuloDaSerie?: string | null;
  aoEscolher: (escopo: EscopoSerie) => void;
  aoCancelar: () => void;
}) {
  const [escolhido, setEscolhido] = useState<EscopoSerie>("apenas_esta");

  return (
    <AlertDialog open={aberto} onOpenChange={(v) => (!v ? aoCancelar() : undefined)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Este lançamento faz parte de uma série</AlertDialogTitle>
          <AlertDialogDescription>
            {rotuloDaSerie ? `${rotuloDaSerie}. ` : ""}O que você quer alterar?
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="flex flex-col gap-2">
          {(
            [
              {
                valor: "apenas_esta" as const,
                titulo: "Só este lançamento",
                texto: "As outras ocorrências da série ficam como estão.",
              },
              {
                valor: "esta_e_futuras" as const,
                titulo: "Este e os futuros",
                texto:
                  "A regra é substituída e as ocorrências de hoje em diante ainda não efetivadas são regeradas. Nada que já foi efetivado é tocado.",
              },
            ] satisfies { valor: EscopoSerie; titulo: string; texto: string }[]
          ).map((o) => (
            <label
              key={o.valor}
              className={`flex cursor-pointer gap-3 rounded-[12px] border px-4 py-3 transition-colors ${
                escolhido === o.valor
                  ? "border-[var(--brand)] bg-[var(--brand-tint)]"
                  : "border-linha-suave hover:bg-[var(--bg-subtle)]"
              }`}
            >
              <input
                type="radio"
                name="escopo-serie"
                checked={escolhido === o.valor}
                onChange={() => setEscolhido(o.valor)}
                className="mt-1 accent-[var(--brand)]"
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-[13px] font-semibold text-[var(--fg)]">{o.titulo}</span>
                <span className="text-[11.5px] leading-[1.5] text-suave">{o.texto}</span>
              </span>
            </label>
          ))}
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <Button onClick={() => aoEscolher(escolhido)}>Continuar</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/**
 * Confirmação de alteração histórica (data-model §5.8).
 *
 * Editar uma ocorrência passada já efetivada muda número de mês fechado. O
 * servidor responde `422` até `confirmar_alteracao_historica: true`, e a
 * frase mostrada é a dele.
 */
export function DialogoAlteracaoHistorica({
  mensagem,
  aoConfirmar,
  aoCancelar,
}: {
  mensagem: string | null;
  aoConfirmar: () => void;
  aoCancelar: () => void;
}) {
  return (
    <AlertDialog open={Boolean(mensagem)} onOpenChange={(v) => (!v ? aoCancelar() : undefined)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Isto altera um mês já fechado</AlertDialogTitle>
          <AlertDialogDescription>{mensagem}</AlertDialogDescription>
        </AlertDialogHeader>
        <p className="text-[11.5px] text-sutil">
          A mudança fica marcada como alteração histórica na linha do tempo, com seu nome e a
          data.
        </p>
        <AlertDialogFooter>
          <AlertDialogCancel>Voltar</AlertDialogCancel>
          <Button onClick={aoConfirmar}>Alterar assim mesmo</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
