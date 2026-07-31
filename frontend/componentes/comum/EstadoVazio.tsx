import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Estado vazio explicativo (*edge case* da spec, T205).
 *
 * A regra é que vazio **explica**, não some. "Nada previsto" é o texto do
 * mockup para uma lista sem itens; quando há um motivo (mundo sem
 * movimentação, filtro estreito demais, histórico ainda não carregado), o
 * motivo vem em `descricao` e a ação de saída vem em `acao`.
 */
export function EstadoVazio({
  titulo = "Nada previsto",
  descricao,
  icone,
  acao,
  compacto = false,
  className,
}: {
  titulo?: string;
  descricao?: ReactNode;
  icone?: ReactNode;
  acao?: ReactNode;
  compacto?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compacto ? "gap-1.5 px-4 py-6" : "gap-2 px-6 py-12",
        className,
      )}
    >
      {icone ? (
        <span
          className="mb-1 flex size-10 items-center justify-center rounded-[12px] text-suave"
          style={{ background: "var(--bg-subtle)" }}
        >
          {icone}
        </span>
      ) : null}
      <p
        className={cn(
          "font-[family-name:var(--font-display)] font-bold tracking-[-0.01em] text-[var(--fg-muted)]",
          compacto ? "text-[12.5px]" : "text-[14px]",
        )}
      >
        {titulo}
      </p>
      {descricao ? (
        <p className={cn("max-w-[46ch] text-sutil", compacto ? "text-[11.5px]" : "text-[12.5px]")}>
          {descricao}
        </p>
      ) : null}
      {acao ? <div className="mt-2">{acao}</div> : null}
    </div>
  );
}
