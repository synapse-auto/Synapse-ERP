import { cn } from "@/lib/utils";
import { percentual } from "@/lib/formato";
import type { Comparativo } from "@/lib/tipos";

/**
 * Pílula de comparação com o período anterior (`FR-055`).
 *
 * Três detalhes que o contrato obriga e que é fácil errar:
 *
 * 1. **`variacao_percentual: null` não é zero.** O backend manda `null`
 *    quando o período anterior é zero — "não dá para calcular" é diferente de
 *    "não mudou" (contracts/consultas.md §1). Aqui vira "novo", não "0,0%".
 * 2. **A direção vem do servidor**, em `direcao`. A tela não deduz pelo
 *    sinal: em despesa, cair é bom, e quem sabe disso é o backend.
 * 3. **`inverso`** existe para os poucos casos em que o componente é usado
 *    sem `direcao` — despesa, onde alta é ruim.
 */
export function Delta({
  comparativo,
  inverso = false,
  className,
  sufixo,
}: {
  comparativo: Comparativo | null | undefined;
  inverso?: boolean;
  className?: string;
  sufixo?: string;
}) {
  const bruto = comparativo?.variacao_percentual;

  if (bruto === null || bruto === undefined) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full px-[7px] py-[2px]",
          "font-[family-name:var(--font-display)] text-[12px] font-bold whitespace-nowrap",
          "bg-[var(--bg-muted)] text-[var(--fg-muted)]",
          className,
        )}
        title="Não há período anterior para comparar."
      >
        novo
      </span>
    );
  }

  const n = Number(bruto);
  const direcao = comparativo?.direcao ?? (n > 0 ? "alta" : n < 0 ? "baixa" : "estavel");
  const seta = direcao === "estavel" ? "=" : direcao === "alta" ? "▲" : "▼";

  // Sem `direcao` do servidor, "bom" é subir — a não ser em despesa.
  const bom =
    direcao === "estavel" ? true : inverso ? direcao === "baixa" : direcao === "alta";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-[7px] py-[2px]",
        "font-[family-name:var(--font-display)] text-[12px] font-bold whitespace-nowrap",
        className,
      )}
      style={{
        background: bom ? "var(--receita-bg)" : "var(--despesa-bg)",
        color: bom ? "var(--receita-fg)" : "var(--despesa-fg)",
      }}
    >
      <span aria-hidden>{seta}</span>
      {percentual(Math.abs(n))}
      {sufixo ? ` ${sufixo}` : null}
    </span>
  );
}
