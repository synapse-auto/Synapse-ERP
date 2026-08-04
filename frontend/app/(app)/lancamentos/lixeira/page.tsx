"use client";

import Link from "next/link";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { CabecalhoTela, BotaoChrome, Quadro } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { BadgeStatus } from "@/componentes/comum/BadgeStatus";
import { DataBR } from "@/componentes/comum/DataBR";
import { Paginacao } from "@/componentes/comum/Paginacao";
import { Button } from "@/componentes/ui/button";
import { useLixeira } from "@/lib/consultas";
import { useRestaurar } from "@/componentes/lancamentos/acoes";
import { dinheiro } from "@/lib/formato";

/**
 * Lixeira (T169, `FR-017`, `RN-08`).
 *
 * Soft delete: a linha nunca é apagada de verdade. `dias_restantes` vem do
 * servidor, calculado contra `configuracoes.lixeira_retencao_dias` — o prazo
 * é dado, não código.
 *
 * **Não existe exclusão definitiva pela API**: o histórico financeiro é
 * permanente. Por isso não há botão de "esvaziar lixeira", e não é
 * esquecimento.
 */
export default function PaginaLixeira() {
  const { data, isLoading } = useLixeira();
  const restaurar = useRestaurar();

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Lançamentos"
        titulo="Lixeira"
        apoio="Excluídos dentro do prazo de retenção. Depois do prazo, o registro continua no banco para a auditoria, mas não volta mais para a lista."
        acoes={
          <Link href="/lancamentos">
            <BotaoChrome>
              <ArrowLeft size={14} />
              Voltar aos lançamentos
            </BotaoChrome>
          </Link>
        }
      />

      <Quadro>
        {isLoading ? (
          <div className="flex flex-col gap-2 p-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-[8px] bg-[var(--bg-subtle)]" />
            ))}
          </div>
        ) : (data?.itens.length ?? 0) === 0 ? (
          <EstadoVazio
            titulo="Lixeira vazia"
            descricao="Nada foi excluído no período de retenção."
            icone={<RotateCcw size={18} />}
          />
        ) : (
          <>
            <div className="grid grid-cols-[92px_minmax(220px,1fr)_180px_120px_140px_120px] items-center border-b border-linha-suave bg-[var(--superficie-lateral)] px-4 py-2.5">
              {["Data", "Descrição", "Categoria", "Status", "Prazo", ""].map((c) => (
                <span
                  key={c}
                  className="font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.07em] text-sutil uppercase"
                >
                  {c}
                </span>
              ))}
            </div>

            {data!.itens.map((l) => (
              <div
                key={l.id}
                className="grid grid-cols-[92px_minmax(220px,1fr)_180px_120px_140px_120px] items-center border-b border-[var(--linha-suave)] px-4 py-2.5 last:border-b-0"
              >
                <DataBR valor={l.data} formato="empilhada" />
                <span className="flex min-w-0 items-center gap-2 pr-4">
                  <span className="truncate text-[13px] text-[var(--fg)]">{l.descricao}</span>
                  <BadgeMundo mundo={l.mundo} />
                </span>
                <span className="truncate pr-3 text-[13px] text-suave">{l.categoria.nome}</span>
                <span>
                  <BadgeStatus status={l.status} compacto />
                </span>
                <span className="text-[12px] text-suave">
                  {l.dias_restantes === undefined ? (
                    "—"
                  ) : l.dias_restantes <= 0 ? (
                    <span className="text-[var(--despesa-fg)]">fora do prazo</span>
                  ) : (
                    <>
                      restam{" "}
                      <strong className="numerico font-semibold text-[var(--fg)]">
                        {l.dias_restantes}
                      </strong>{" "}
                      {l.dias_restantes === 1 ? "dia" : "dias"}
                    </>
                  )}
                </span>
                <span className="flex items-center justify-end gap-3">
                  <span className="numerico text-[13px] font-semibold text-suave">
                    {dinheiro(l.valor)}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={restaurar.isPending}
                    onClick={() => restaurar.mutate(l.id)}
                  >
                    <RotateCcw size={13} />
                    Restaurar
                  </Button>
                </span>
              </div>
            ))}

            <Paginacao paginacao={data?.paginacao} aoIr={() => {}} substantivo="excluídos" />
          </>
        )}
      </Quadro>
    </div>
  );
}
