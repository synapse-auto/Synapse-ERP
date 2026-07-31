import { cn } from "@/lib/utils";
import type { StatusLancamento } from "@/lib/tipos";

/**
 * Pílula de status do lançamento — `ST` do mockup.
 *
 * O **rótulo** está aqui, e não vindo do banco, porque `status_lancamento` é
 * um enum do próprio esquema (migração `001`): são cinco valores fixos do
 * modelo, não parâmetro de negócio. `RNF-02` trata de limites, prazos e
 * rótulos configuráveis — esses vêm de `configuracoes`.
 */
const ROTULOS: Record<StatusLancamento, string> = {
  efetivado: "Efetivado",
  programado: "Programado",
  pendente: "Pendente",
  atrasado: "Atrasado",
  cancelado: "Cancelado",
};

export function rotuloDoStatus(status: StatusLancamento): string {
  return ROTULOS[status] ?? status;
}

export function BadgeStatus({
  status,
  className,
  compacto = false,
}: {
  status: StatusLancamento;
  className?: string;
  compacto?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-[6px] rounded-full font-[family-name:var(--font-display)] font-bold whitespace-nowrap",
        compacto ? "px-[7px] py-[2px] text-[10.5px]" : "px-[9px] py-[3px] text-[11.5px]",
        className,
      )}
      style={{
        background: `var(--st-${status}-bg)`,
        color: `var(--st-${status}-fg)`,
      }}
    >
      <span
        aria-hidden
        className="size-[6px] shrink-0 rounded-full"
        style={{ background: `var(--st-${status}-dot)` }}
      />
      {rotuloDoStatus(status)}
    </span>
  );
}
