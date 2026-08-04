import { cn } from "@/lib/utils";
import type { Mundo, MundoFiltro } from "@/lib/tipos";

/**
 * Marcador de mundo — `MW` do mockup.
 *
 * Existe para o modo "Ambos": quando os dois mundos aparecem na mesma lista,
 * **cada item precisa dizer de qual mundo é** (`FR-003`, `SC-005`). No modo
 * filtrado ele é redundante e a tela normalmente o esconde.
 */
export const ROTULO_MUNDO: Record<MundoFiltro, string> = {
  digital: "Digital",
  infra: "Infra",
  ambos: "Ambos",
};

export const NOME_COMPLETO_MUNDO: Record<MundoFiltro, string> = {
  digital: "Synapse Digital",
  infra: "Synapse Infra",
  ambos: "Digital + Infra",
};

export function BadgeMundo({
  mundo,
  className,
  comPonto = false,
}: {
  mundo: Mundo;
  className?: string;
  comPonto?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-[5px] rounded-[6px] px-[6px] py-[1.5px]",
        "font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[-0.01em] whitespace-nowrap",
        className,
      )}
      style={{
        background: `var(--mundo-${mundo}-bg)`,
        color: `var(--mundo-${mundo}-fg)`,
      }}
      title={NOME_COMPLETO_MUNDO[mundo]}
    >
      {comPonto ? (
        <span
          aria-hidden
          className="size-[6px] shrink-0 rounded-[2px]"
          style={{ background: `var(--mundo-${mundo})` }}
        />
      ) : null}
      {ROTULO_MUNDO[mundo]}
    </span>
  );
}

/** Só o ponto colorido — usado no seletor do cabeçalho e nas legendas. */
export function PontoMundo({ mundo, className }: { mundo: MundoFiltro; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block size-[8px] shrink-0 rounded-[2.5px]", className)}
      style={{ background: `var(--mundo-${mundo})` }}
    />
  );
}
