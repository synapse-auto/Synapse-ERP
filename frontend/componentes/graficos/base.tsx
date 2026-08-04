"use client";

import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { dinheiro, dinheiroCurto, mesCurto } from "@/lib/formato";

/**
 * Peças comuns dos gráficos (T177).
 *
 * **Cores em `var(...)`, não em hexa.** O SVG aceita `fill="var(--x)"`, então
 * o gráfico troca de tema junto com o resto da interface sem nenhum
 * `useTheme` e sem redesenhar — que é o que `SC-009` cobra e o que costuma
 * faltar em gráfico.
 */

export const COR = {
  receita: "var(--success-500)",
  despesa: "var(--danger-500)",
  marca: "var(--brand)",
  eixo: "var(--fg-subtle)",
  grade: "var(--linha-suave)",
  saldo: "var(--purple-500)",
} as const;

/** Projeção é o mesmo desenho, mais claro e semitransparente (`FR-059`). */
export const OPACIDADE_PROJETADA = 0.42;

export function eixoMes(v: string): string {
  return mesCurto(v);
}

export function eixoDinheiro(v: number): string {
  return dinheiroCurto(v).replace("R$ ", "");
}

/** Caixa de dica com a mesma superfície e sombra dos popovers da interface. */
export function CaixaDeDica({
  titulo,
  linhas,
  rodape,
}: {
  titulo: string;
  linhas: { rotulo: string; valor: string; cor?: string }[];
  rodape?: ReactNode;
}) {
  return (
    <div className="min-w-[168px] rounded-[8px] border border-linha-chrome bg-superficie-cartao px-3 py-2 shadow-[var(--shadow-md)]">
      <p className="mb-1.5 font-[family-name:var(--font-display)] text-[12px] font-bold text-forte">
        {titulo}
      </p>
      <ul className="flex flex-col gap-1">
        {linhas.map((l) => (
          <li key={l.rotulo} className="flex items-center justify-between gap-4 text-[12px]">
            <span className="flex items-center gap-1.5 text-suave">
              {l.cor ? (
                <span
                  aria-hidden
                  className="size-[7px] rounded-[2px]"
                  style={{ background: l.cor }}
                />
              ) : null}
              {l.rotulo}
            </span>
            <span className="numerico font-semibold text-[var(--fg)]">{l.valor}</span>
          </li>
        ))}
      </ul>
      {rodape ? <p className="mt-1.5 text-[11px] text-sutil">{rodape}</p> : null}
    </div>
  );
}

/** Legenda em linha, do jeito do mockup: pontinho + rótulo, 11.5px. */
export function Legenda({
  itens,
  className,
}: {
  itens: { rotulo: string; cor: string; tracejado?: boolean }[];
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-4", className)}>
      {itens.map((i) => (
        <span key={i.rotulo} className="flex items-center gap-1.5 text-[12px] text-suave">
          {i.tracejado ? (
            <span
              aria-hidden
              className="h-0 w-4 border-t-[1.5px] border-dashed"
              style={{ borderColor: i.cor }}
            />
          ) : (
            <span aria-hidden className="size-[7px] rounded-full" style={{ background: i.cor }} />
          )}
          {i.rotulo}
        </span>
      ))}
    </div>
  );
}

export function formatarMoedaDica(v: unknown): string {
  return dinheiro(typeof v === "number" ? v : String(v ?? ""));
}

/**
 * `true` quando o sistema pede menos movimento (T215).
 *
 * A regra de `prefers-reduced-motion` do `globals.css` desliga transição e
 * animação **de CSS**. O Recharts anima em JavaScript, redesenhando o SVG
 * quadro a quadro — CSS nenhum alcança isso. Por isso o hook: cada série
 * recebe `isAnimationActive={!semMovimento}` e o gráfico nasce pronto para
 * quem marcou "reduzir movimento" no sistema.
 */
export function useMovimentoReduzido(): boolean {
  const [reduzido, setReduzido] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const consulta = window.matchMedia("(prefers-reduced-motion: reduce)");
    const aplicar = () => setReduzido(consulta.matches);
    aplicar();
    consulta.addEventListener("change", aplicar);
    return () => consulta.removeEventListener("change", aplicar);
  }, []);

  return reduzido;
}
