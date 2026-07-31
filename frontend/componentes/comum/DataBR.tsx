import { cn } from "@/lib/utils";
import { data as formatarData, dataCurta, instante } from "@/lib/formato";

interface PropsData {
  /** ISO da API: `"2026-07-31"` ou instante com fuso. */
  valor: string | null | undefined;
  formato?: "completa" | "curta" | "instante" | "empilhada";
  className?: string;
  vazio?: string;
}

/**
 * Data em formato brasileiro (`RNF-03`). A API transporta ISO; a tela nunca
 * mostra ISO.
 *
 * `empilhada` é o formato da coluna Data do mockup: `31/07` grande e `2026`
 * pequeno embaixo, em fonte monoespaçada, para a coluna ficar estreita sem
 * perder o ano.
 */
export function DataBR({ valor, formato = "completa", className, vazio = "—" }: PropsData) {
  if (!valor) return <span className={cn("text-sutil", className)}>{vazio}</span>;

  if (formato === "empilhada") {
    const [ano, mes, dia] = valor.slice(0, 10).split("-");
    return (
      <time dateTime={valor.slice(0, 10)} className={cn("flex flex-col leading-[1.1]", className)}>
        <span className="font-mono text-[12.5px] font-medium text-[var(--fg)]">{`${dia}/${mes}`}</span>
        <span className="font-mono text-[9.5px] text-sutil">{ano}</span>
      </time>
    );
  }

  const texto =
    formato === "curta"
      ? dataCurta(valor, vazio)
      : formato === "instante"
        ? instante(valor, vazio)
        : formatarData(valor, vazio);

  return (
    <time dateTime={valor} className={cn("numerico", className)}>
      {texto}
    </time>
  );
}
