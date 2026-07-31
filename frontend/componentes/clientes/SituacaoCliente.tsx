import { dinheiro } from "@/lib/formato";
import type { Cliente } from "@/lib/tipos";

/**
 * Situação do cliente (T190, `RN-10`, `FR-083`, `SC-006`).
 *
 * A situação é **derivada, nunca gravada**: sai de `dominio/inadimplencia.py`
 * no servidor, a mesma função que alimenta o Dashboard, o perfil e o alerta
 * da rotina — para os quatro nunca discordarem.
 *
 * `tolerancia_dias` vem junto para a tela **explicar o critério**, não só
 * mostrar o rótulo. E `dias_atraso` é `null`, não `0`, quando não há atraso.
 */
export function SituacaoCliente({ cliente }: { cliente: Cliente }) {
  const atrasado = cliente.situacao === "atrasado";

  return (
    <span
      className="flex w-[168px] flex-col gap-0.5 rounded-[9px] px-2.5 py-1.5"
      style={{
        background: atrasado ? "var(--st-atrasado-bg)" : "var(--st-efetivado-bg)",
        color: atrasado ? "var(--st-atrasado-fg)" : "var(--st-efetivado-fg)",
      }}
      title={
        cliente.tolerancia_dias != null
          ? `Tolerância configurada: ${cliente.tolerancia_dias} dias.`
          : undefined
      }
    >
      <span className="font-[family-name:var(--font-display)] text-[11.5px] font-bold">
        {atrasado ? `Atrasado há ${cliente.dias_atraso} dias` : "Em dia"}
      </span>
      {atrasado ? (
        <span className="numerico text-[11px]">
          {dinheiro(cliente.valor_atrasado)}
          {cliente.quantidade_em_atraso && cliente.quantidade_em_atraso > 1
            ? ` · ${cliente.quantidade_em_atraso} cobranças`
            : ""}
        </span>
      ) : cliente.tolerancia_dias != null ? (
        <span className="text-[10.5px] opacity-80">
          tolerância de {cliente.tolerancia_dias} dias
        </span>
      ) : null}
    </span>
  );
}
