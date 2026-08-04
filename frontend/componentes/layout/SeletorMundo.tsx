"use client";

import { cn } from "@/lib/utils";
import { MUNDOS, useEstadoGlobal } from "@/lib/estado-global";
import { PontoMundo } from "@/componentes/comum/BadgeMundo";
import { useEspelharEscopoNaUrl } from "./espelho-de-url";

/**
 * Seletor de mundo — Digital / Infra / Ambos (T157, `FR-001`).
 *
 * É o controle mais importante do cabeçalho: ele decide o que existe em
 * todas as telas ao mesmo tempo. Medidas do mockup: trilho `#F4F1FA` com
 * borda `#EDEAF2`, raio 9px e 3px de recheio; botão de 6px/12px com raio 7px,
 * Plus Jakarta 12.5px 700; ponto de 8px com raio 2.5px na cor do mundo.
 *
 * A escolha vai para a URL e para o `localStorage` — copiar o link leva o
 * mundo junto, e reabrir o sistema volta onde parou.
 */
export function SeletorMundo({ className }: { className?: string }) {
  const mundo = useEstadoGlobal((e) => e.mundo);
  const definirMundo = useEstadoGlobal((e) => e.definirMundo);
  useEspelharEscopoNaUrl();

  return (
    <div className={cn("flex items-center gap-2 pl-[2px]", className)}>
      <span className="font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.07em] text-[var(--ink-300)] uppercase dark:text-[var(--fg-subtle)]">
        Mundo
      </span>
      <div
        role="radiogroup"
        aria-label="Mundo"
        className="flex items-center gap-[2px] rounded-[6px] border border-linha-suave bg-segmento p-[3px]"
      >
        {MUNDOS.map((m) => {
          const ativo = mundo === m.valor;
          return (
            <button
              key={m.valor}
              type="button"
              role="radio"
              aria-checked={ativo}
              onClick={() => definirMundo(m.valor)}
              className={cn(
                "flex items-center gap-[7px] rounded-[6px] px-3 py-[6px] whitespace-nowrap",
                "font-[family-name:var(--font-display)] text-[13px] font-bold tracking-[-0.01em]",
                "transition-colors duration-[var(--dur-fast)] ease-[var(--ease-out)]",
                ativo
                  ? "bg-superficie-cartao text-[var(--ink-700)] shadow-[0_1px_2px_rgba(30,22,51,0.08)] dark:text-[var(--fg-strong)]"
                  : "text-suave hover:text-[var(--fg)]",
              )}
            >
              <PontoMundo mundo={m.valor} />
              {m.rotulo}
            </button>
          );
        })}
      </div>
    </div>
  );
}
