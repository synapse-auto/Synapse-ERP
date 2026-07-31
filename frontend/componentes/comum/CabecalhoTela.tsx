import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Cabeçalho de tela do mockup: sobrancelha roxa em caixa alta, título de
 * 27px/800 e uma linha de apoio. As ações ficam à direita, alinhadas pela
 * base do título.
 */
export function CabecalhoTela({
  sobrancelha,
  titulo,
  apoio,
  acoes,
  className,
}: {
  sobrancelha?: string;
  titulo: string;
  apoio?: ReactNode;
  acoes?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-6", className)}>
      <div className="min-w-0">
        {sobrancelha ? (
          <div className="mb-[5px] font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.1em] text-[var(--brand)] uppercase">
            {sobrancelha}
          </div>
        ) : null}
        <h1 className="text-[27px] leading-[1.1] font-extrabold tracking-[-0.03em] text-forte">
          {titulo}
        </h1>
        {apoio ? <p className="mt-[5px] text-[13.5px] text-suave">{apoio}</p> : null}
      </div>
      {acoes ? <div className="flex flex-wrap items-center gap-2">{acoes}</div> : null}
    </div>
  );
}

/**
 * Botão de chrome — o secundário do mockup: 34px, borda `#E3DEEE`, raio 9px,
 * Plus Jakarta 12.5px/600, hover com borda lilás.
 */
export function BotaoChrome({
  children,
  className,
  ...resto
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        "flex h-[34px] items-center gap-[7px] rounded-[9px] px-[13px] whitespace-nowrap",
        "border border-linha-controle bg-superficie-cartao text-[var(--ink-600)] dark:text-[var(--fg)]",
        "font-[family-name:var(--font-display)] text-[12.5px] font-semibold",
        "transition-colors hover:border-[var(--purple-300)] hover:bg-[var(--bg-subtle)]",
        "disabled:cursor-not-allowed disabled:opacity-45",
        className,
      )}
      {...resto}
    >
      {children}
    </button>
  );
}

/** O quadro branco que envolve tabela e filtros — borda, raio 14, sem padding. */
export function Quadro({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[14px] border border-linha-chrome bg-superficie-cartao",
        "shadow-[var(--sombra-cartao)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
