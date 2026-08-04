import { cn } from "@/lib/utils";
import { instante } from "@/lib/formato";
import type { AcaoAuditoria, EventoAuditoria } from "@/lib/tipos";

/**
 * Linha do tempo de auditoria (T200, `FR-103`, `SC-014`) — quem, o quê e
 * quando, com o que mudou.
 *
 * `alteracao_historica: true` marca a edição de uma ocorrência passada já
 * efetivada (data-model §5.8). É destacada porque é o tipo de mudança que
 * altera número de mês fechado.
 */

const ROTULO: Record<AcaoAuditoria, string> = {
  criacao: "criou",
  edicao: "editou",
  exclusao: "excluiu",
  restauracao: "restaurou",
};

const COR: Record<AcaoAuditoria, string> = {
  criacao: "var(--brand)",
  edicao: "var(--info-500)",
  exclusao: "var(--danger-500)",
  restauracao: "var(--success-500)",
};

function comoTexto(v: unknown): string {
  if (v === null || v === undefined || v === "") return "vazio";
  if (typeof v === "boolean") return v ? "sim" : "não";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function LinhaDoTempo({
  eventos,
  className,
}: {
  eventos: EventoAuditoria[];
  className?: string;
}) {
  return (
    <ol className={cn("flex flex-col", className)}>
      {eventos.map((e, i) => (
        <li key={e.id ?? i} className="relative flex gap-3 pb-4 last:pb-0">
          {i < eventos.length - 1 ? (
            <span aria-hidden className="absolute top-4 bottom-0 left-[5px] w-px bg-linha-suave" />
          ) : null}
          <span
            aria-hidden
            className="relative mt-[5px] size-[11px] flex-none rounded-full border-2 border-superficie-cartao"
            style={{ background: COR[e.acao] }}
          />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <span className="text-[13px] text-[var(--fg)]">
              <strong className="font-semibold">{e.usuario?.nome ?? "Sistema"}</strong>{" "}
              {ROTULO[e.acao]}
              {e.alteracao_historica ? (
                <span
                  className="ml-2 rounded-full px-2 py-[1px] text-[10px] font-bold"
                  style={{
                    background: "var(--st-pendente-bg)",
                    color: "var(--st-pendente-fg)",
                  }}
                >
                  alteração histórica
                </span>
              ) : null}
            </span>
            <span className="text-[11px] text-sutil">{instante(e.criado_em)}</span>

            {e.alteracoes && Object.keys(e.alteracoes).length > 0 ? (
              <ul className="mt-1 flex flex-col gap-0.5 rounded-[6px] bg-[var(--bg-subtle)] px-2.5 py-2">
                {Object.entries(e.alteracoes).map(([campo, mudanca]) => (
                  <li key={campo} className="text-[12px] text-suave">
                    <span className="text-sutil">{campo}:</span>{" "}
                    <span className="line-through opacity-70">{comoTexto(mudanca.de)}</span>{" "}
                    <span aria-hidden>→</span>{" "}
                    <span className="font-medium text-[var(--fg)]">{comoTexto(mudanca.para)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
