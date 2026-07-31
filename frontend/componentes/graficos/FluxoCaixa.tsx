"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CaixaDeDica, COR, eixoDinheiro, eixoMes, Legenda, OPACIDADE_PROJETADA } from "./base";
import { dinheiro, mesCurto } from "@/lib/formato";
import type { PontoFluxo } from "@/lib/tipos";

/**
 * Fluxo de caixa mensal (`FR-059`).
 *
 * Barras de receita e despesa por mês e uma linha tracejada de resultado.
 * **Os meses projetados são desenhados distintos** — mesma cor, mais clara e
 * semitransparente, com uma faixa e o rótulo "projeção" por cima. É `RN-05`
 * na tela: previsto não pode passar por realizado.
 */
export function FluxoCaixa({ dados }: { dados: PontoFluxo[] }) {
  const pontos = dados.map((d) => ({
    mes: d.mes,
    receitas: Number(d.receitas),
    despesas: Number(d.despesas),
    resultado: Number(d.resultado),
    projetado: d.projetado,
  }));

  const primeiroProjetado = pontos.findIndex((p) => p.projetado);

  return (
    <div className="flex flex-col gap-3">
      <Legenda
        className="justify-end"
        itens={[
          { rotulo: "Receitas", cor: COR.receita },
          { rotulo: "Despesas", cor: COR.despesa },
          { rotulo: "Resultado", cor: COR.marca, tracejado: true },
        ]}
      />
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={pontos} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <CartesianGrid stroke={COR.grade} vertical={false} />

          {primeiroProjetado >= 0 ? (
            <ReferenceArea
              x1={pontos[primeiroProjetado].mes}
              x2={pontos[pontos.length - 1].mes}
              fill="var(--brand-tint)"
              fillOpacity={0.7}
              label={{
                value: "PROJEÇÃO",
                position: "insideTop",
                fill: "var(--brand-hover)",
                fontSize: 10,
                letterSpacing: "0.1em",
              }}
            />
          ) : null}

          <XAxis
            dataKey="mes"
            tickFormatter={eixoMes}
            tickLine={false}
            axisLine={false}
            tick={{ fill: COR.eixo, fontSize: 11 }}
          />
          <YAxis
            tickFormatter={eixoDinheiro}
            tickLine={false}
            axisLine={false}
            width={52}
            tick={{ fill: COR.eixo, fontSize: 11 }}
          />

          <Tooltip
            cursor={{ fill: "var(--bg-subtle)" }}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as (typeof pontos)[number];
              return (
                <CaixaDeDica
                  titulo={mesCurto(String(label))}
                  linhas={[
                    { rotulo: "Receitas", valor: dinheiro(p.receitas), cor: COR.receita },
                    { rotulo: "Despesas", valor: dinheiro(p.despesas), cor: COR.despesa },
                    { rotulo: "Resultado", valor: dinheiro(p.resultado), cor: COR.marca },
                  ]}
                  rodape={p.projetado ? "Mês projetado — ainda não aconteceu." : undefined}
                />
              );
            }}
          />

          <Bar dataKey="receitas" radius={[3, 3, 0, 0]} maxBarSize={18}>
            {pontos.map((p, i) => (
              <Cell
                key={i}
                fill={COR.receita}
                fillOpacity={p.projetado ? OPACIDADE_PROJETADA : 1}
              />
            ))}
          </Bar>
          <Bar dataKey="despesas" radius={[3, 3, 0, 0]} maxBarSize={18}>
            {pontos.map((p, i) => (
              <Cell
                key={i}
                fill={COR.despesa}
                fillOpacity={p.projetado ? OPACIDADE_PROJETADA : 1}
              />
            ))}
          </Bar>
          <Line
            type="monotone"
            dataKey="resultado"
            stroke={COR.marca}
            strokeWidth={1.6}
            strokeDasharray="4 4"
            dot={{ r: 2.4, fill: COR.marca, strokeWidth: 0 }}
            activeDot={{ r: 4 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Comparativo mês atual × anterior (`FR-061`) — o mesmo desenho, dois meses. */
export function ComparativoMensal({
  atual,
  anterior,
}: {
  atual: Record<string, string>;
  anterior: Record<string, string>;
}) {
  const chaves = Array.from(new Set([...Object.keys(atual), ...Object.keys(anterior)]));
  const dados = chaves.map((k) => ({
    rotulo: k.replace(/_/g, " "),
    anterior: Number(anterior[k] ?? 0),
    atual: Number(atual[k] ?? 0),
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid stroke={COR.grade} vertical={false} />
        <XAxis dataKey="rotulo" tickLine={false} axisLine={false} tick={{ fill: COR.eixo, fontSize: 11 }} />
        <YAxis
          tickFormatter={eixoDinheiro}
          tickLine={false}
          axisLine={false}
          width={52}
          tick={{ fill: COR.eixo, fontSize: 11 }}
        />
        <Tooltip
          cursor={{ fill: "var(--bg-subtle)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <CaixaDeDica
                titulo={String(label)}
                linhas={payload.map((p) => ({
                  rotulo: p.dataKey === "atual" ? "Período atual" : "Período anterior",
                  valor: dinheiro(Number(p.value)),
                  cor: String(p.color),
                }))}
              />
            ) : null
          }
        />
        <Bar dataKey="anterior" fill="var(--ink-200)" radius={[3, 3, 0, 0]} maxBarSize={26} />
        <Bar dataKey="atual" fill={COR.marca} radius={[3, 3, 0, 0]} maxBarSize={26} />
      </BarChart>
    </ResponsiveContainer>
  );
}
