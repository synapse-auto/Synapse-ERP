import { cn } from "@/lib/utils";
import { dinheiro, dinheiroCurto } from "@/lib/formato";
import type { MoedaCodigo, StatusLancamento, TipoLancamento } from "@/lib/tipos";

interface PropsMoeda {
  valor: string | number | null | undefined;
  /** Pinta de verde (receita) ou vermelho (despesa), como na tabela do mockup. */
  tipo?: TipoLancamento | null;
  /**
   * Lançamento não efetivado sai em cinza, mesmo sendo receita: só
   * `efetivado` conta no realizado (`RN-05`). É a diferença visual que o
   * mockup faz no Extrato entre linha real e linha prevista.
   */
  status?: StatusLancamento | null;
  /** Mostra `+`/`−` na frente, como na coluna Valor. */
  comSinal?: boolean;
  moeda?: MoedaCodigo;
  curto?: boolean;
  className?: string;
  vazio?: string;
}

/**
 * Um valor em dinheiro na tela. Sempre `R$ 1.234,56` e sempre com números
 * tabulares — coluna de dinheiro que não alinha é difícil de conferir.
 */
export function Moeda({
  valor,
  tipo = null,
  status = null,
  comSinal = false,
  moeda = "BRL",
  curto = false,
  className,
  vazio = "—",
}: PropsMoeda) {
  const previsto = status !== null && status !== "efetivado";
  const cor = previsto
    ? "text-[var(--valor-previsto-fg)]"
    : tipo === "receita"
      ? "text-[var(--receita-fg)]"
      : tipo === "despesa"
        ? "text-[var(--despesa-fg)]"
        : undefined;

  const texto = curto
    ? dinheiroCurto(valor)
    : dinheiro(valor, { moeda, sinal: false, vazio });

  const prefixo = comSinal && tipo ? (tipo === "receita" ? "+ " : "− ") : "";

  return (
    <span className={cn("numerico tabular-nums", cor, className)}>
      {texto === vazio ? vazio : `${prefixo}${texto}`}
    </span>
  );
}
