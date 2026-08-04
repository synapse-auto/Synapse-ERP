"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { CaixaDeDica, useMovimentoReduzido } from "./base";
import { dinheiro, percentual } from "@/lib/formato";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import type { FatiaCategoria } from "@/lib/tipos";

/**
 * Rosca de despesas por categoria (`FR-062`).
 *
 * **A cor de cada fatia vem do banco** (`categorias.cor`), não de uma paleta
 * do frontend: é a mesma cor que a categoria tem na lista, no filtro e no
 * DRE. Uma paleta local faria a mesma categoria mudar de cor de tela para
 * tela.
 *
 * Cada fatia e cada linha da legenda leva para a lista já filtrada, usando o
 * `filtro_drilldown` que o servidor montou (`FR-058`).
 */
export function DespesasCategoria({
  fatias,
  total,
  aoEscolher,
}: {
  fatias: FatiaCategoria[];
  total: string;
  aoEscolher: (fatia: FatiaCategoria) => void;
}) {
  const semMovimento = useMovimentoReduzido();

  if (fatias.length === 0) {
    return (
      <EstadoVazio
        titulo="Nenhuma despesa no período"
        descricao="Quando houver despesa efetivada, a divisão por categoria aparece aqui."
        compacto
      />
    );
  }

  const dados = fatias.map((f) => ({ ...f, v: Number(f.valor) }));

  return (
    <div className="grid items-center gap-6 sm:grid-cols-[168px_1fr]">
      <div className="relative">
        <ResponsiveContainer width="100%" height={168}>
          <PieChart>
            <Pie
              data={dados}
              dataKey="v"
              nameKey="nome"
              innerRadius={52}
              outerRadius={78}
              paddingAngle={1.5}
              stroke="var(--superficie-cartao)"
              strokeWidth={2}
              isAnimationActive={!semMovimento}
              onClick={(_, i) => aoEscolher(fatias[i])}
            >
              {dados.map((f) => (
                <Cell
                  key={f.categoria_id}
                  fill={f.cor ?? "var(--ink-300)"}
                  className="cursor-pointer"
                />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <CaixaDeDica
                    titulo={String(payload[0].payload.nome)}
                    linhas={[
                      {
                        rotulo: "Valor",
                        valor: dinheiro(payload[0].payload.valor),
                        cor: payload[0].payload.cor ?? undefined,
                      },
                      {
                        rotulo: "Participação",
                        valor: percentual(payload[0].payload.percentual),
                      },
                    ]}
                  />
                ) : null
              }
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="numerico font-[family-name:var(--font-display)] text-[13px] font-bold text-forte">
            {dinheiro(total)}
          </span>
          <span className="text-[10px] text-sutil">no período</span>
        </div>
      </div>

      <ul className="flex flex-col gap-1.5">
        {fatias.map((f) => (
          <li key={f.categoria_id}>
            <button
              type="button"
              onClick={() => aoEscolher(f)}
              aria-label={`Ver as despesas da categoria ${f.nome}`}
              className="flex w-full items-center gap-2 rounded-[6px] px-1.5 py-1 text-left transition-colors duration-[var(--dur-fast)] hover:bg-[var(--bg-subtle)]"
            >
              <span
                aria-hidden
                className="size-[8px] flex-none rounded-full"
                style={{ background: f.cor ?? "var(--ink-300)" }}
              />
              <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--fg)]">
                {f.nome}
              </span>
              <span className="numerico text-[13px] font-semibold text-suave">
                {percentual(f.percentual)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
