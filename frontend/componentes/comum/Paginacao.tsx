"use client";

import { cn } from "@/lib/utils";
import { inteiro } from "@/lib/formato";
import type { PaginacaoApi } from "@/lib/tipos";

/**
 * Rodapé de paginação do mockup: "Mostrando X de Y", botões de 30px com raio
 * 8px e a página atual em roxo cheio. As reticências aparecem quando há
 * páginas escondidas — nunca se desenham oito botões de página.
 */
export function Paginacao({
  paginacao,
  aoIr,
  substantivo = "lançamentos",
  className,
}: {
  paginacao: PaginacaoApi | undefined;
  aoIr: (pagina: number) => void;
  substantivo?: string;
  className?: string;
}) {
  if (!paginacao || paginacao.total === 0) return null;

  const { pagina, total, total_paginas: paginas, por_pagina } = paginacao;
  const mostrando = Math.min(por_pagina, total - (pagina - 1) * por_pagina);

  const numeros: (number | "…")[] = [];
  for (let p = 1; p <= paginas; p++) {
    if (p === 1 || p === paginas || Math.abs(p - pagina) <= 1) numeros.push(p);
    else if (numeros[numeros.length - 1] !== "…") numeros.push("…");
  }

  const base =
    "h-[30px] min-w-[30px] rounded-[8px] border border-linha-controle bg-superficie-cartao px-[9px] text-[12.5px] transition-colors";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-4 bg-[var(--superficie-lateral)] px-4 py-[13px]",
        className,
      )}
    >
      <span className="text-[12.5px] text-sutil">
        Mostrando <strong className="font-semibold text-[var(--ink-700)] dark:text-[var(--fg)]">{inteiro(mostrando)}</strong>{" "}
        de {inteiro(total)} {substantivo}
      </span>

      {paginas > 1 ? (
        <nav aria-label="Paginação" className="flex items-center gap-[5px]">
          <button
            type="button"
            disabled={pagina <= 1}
            onClick={() => aoIr(pagina - 1)}
            className={cn(base, "text-suave disabled:opacity-45")}
          >
            Anterior
          </button>
          {numeros.map((n, i) =>
            n === "…" ? (
              <span key={`e${i}`} className="px-[3px] text-[var(--ink-300)]">
                …
              </span>
            ) : (
              <button
                key={n}
                type="button"
                aria-current={n === pagina ? "page" : undefined}
                onClick={() => aoIr(n)}
                className={cn(
                  base,
                  n === pagina
                    ? "border-0 bg-[var(--brand)] font-[family-name:var(--font-display)] font-bold text-[var(--fg-onbrand)]"
                    : "text-[var(--ink-600)] hover:bg-[var(--bg-subtle)] dark:text-[var(--fg)]",
                )}
              >
                {n}
              </button>
            ),
          )}
          <button
            type="button"
            disabled={pagina >= paginas}
            onClick={() => aoIr(pagina + 1)}
            className={cn(base, "text-[var(--ink-600)] disabled:opacity-45 dark:text-[var(--fg)]")}
          >
            Próxima
          </button>
        </nav>
      ) : null}
    </div>
  );
}
