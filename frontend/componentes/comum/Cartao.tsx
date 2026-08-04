import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * A receita de cartão do design system, com as medidas do mockup:
 * fundo branco, borda 1px `#E9E5F3`, raio 14px, sombra `0 1px 3px`.
 *
 * O design system manda escolher **uma** entre borda+sombra sutil e sombra
 * forte sem borda — nunca as duas em peso. `destaque` é a segunda opção, com
 * o degradê lilás que o mockup usa no cartão principal do Dashboard.
 */
export function Cartao({
  children,
  className,
  destaque = false,
  padding = "normal",
  ...resto
}: {
  children: ReactNode;
  className?: string;
  destaque?: boolean;
  padding?: "normal" | "compacto" | "nenhum";
} & Omit<React.HTMLAttributes<HTMLDivElement>, "className" | "children">) {
  return (
    <div
      className={cn(
        "rounded-[12px]",
        padding === "normal" && "p-5",
        padding === "compacto" && "p-4",
        destaque
          ? "border border-[#DFD4FA] shadow-[var(--sombra-destaque)] dark:border-[var(--border-brand)]"
          : "border border-linha-chrome bg-superficie-cartao shadow-[var(--sombra-cartao)]",
        className,
      )}
      style={
        destaque
          ? { background: "linear-gradient(140deg, var(--brand-tint) 0%, var(--superficie-cartao) 55%)" }
          : undefined
      }
      {...resto}
    >
      {children}
    </div>
  );
}

/** Rótulo de cartão: 11px, 700, caixa alta, tracking .08em — como o mockup. */
export function RotuloCartao({
  children,
  cor = "sutil",
  className,
}: {
  children: ReactNode;
  cor?: "sutil" | "marca";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.08em] uppercase",
        cor === "marca" ? "text-[var(--brand-hover)]" : "text-sutil",
        className,
      )}
    >
      {children}
    </span>
  );
}
