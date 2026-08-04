"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CaixaDeDica,
  COR,
  eixoDinheiro,
  eixoMes,
  OPACIDADE_PROJETADA,
  useMovimentoReduzido,
} from "./base";
import { dinheiro, mesCurto } from "@/lib/formato";
import type { PontoSaldo } from "@/lib/tipos";

/**
 * Evolução do saldo ao fim de cada mês (`FR-060`).
 *
 * **O trecho projetado sai tracejado, e isso é `RN-05` na tela**, não enfeite:
 * previsto não pode passar por realizado. São duas séries no mesmo eixo —
 * `saldo` (realizado) e `projecao` — porque uma linha só não muda de traço no
 * meio. A projeção começa no último ponto realizado, senão a linha nasce solta.
 * A faixa e o rótulo "PROJEÇÃO" repetem o desenho do fluxo de caixa.
 */
export function EvolucaoSaldo({ dados }: { dados: PontoSaldo[] }) {
  const semMovimento = useMovimentoReduzido();
  const primeiroProjetado = dados.findIndex((d) => d.projetado);
  const ultimoRealizado = primeiroProjetado < 0 ? dados.length - 1 : primeiroProjetado - 1;

  const pontos = dados.map((d, i) => ({
    mes: d.mes,
    // `null` corta a série: cada linha só existe no trecho que lhe pertence.
    saldo: d.projetado ? null : Number(d.saldo_final),
    projecao: d.projetado || i === ultimoRealizado ? Number(d.saldo_final) : null,
    valor: Number(d.saldo_final),
    projetado: d.projetado,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={pontos} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <defs>
          <linearGradient id="areaSaldo" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COR.saldo} stopOpacity={0.22} />
            <stop offset="100%" stopColor={COR.saldo} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={COR.grade} vertical={false} />

        {primeiroProjetado >= 0 ? (
          <ReferenceArea
            x1={dados[primeiroProjetado].mes}
            x2={dados[dados.length - 1].mes}
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
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as (typeof pontos)[number];
            return (
              <CaixaDeDica
                titulo={mesCurto(String(label))}
                linhas={[{ rotulo: "Saldo ao fim do mês", valor: dinheiro(p.valor), cor: COR.saldo }]}
                rodape={p.projetado ? "Projetado — depende do que ainda vai se efetivar." : undefined}
              />
            );
          }}
        />
        <Area
          type="monotone"
          dataKey="saldo"
          stroke={COR.saldo}
          strokeWidth={1.8}
          fill="url(#areaSaldo)"
          dot={{ r: 2.6, fill: "var(--superficie-cartao)", stroke: COR.saldo, strokeWidth: 1.6 }}
          activeDot={{ r: 4.5 }}
          isAnimationActive={!semMovimento}
        />
        <Area
          type="monotone"
          dataKey="projecao"
          stroke={COR.saldo}
          strokeWidth={1.8}
          strokeDasharray="4 4"
          fill="url(#areaSaldo)"
          fillOpacity={OPACIDADE_PROJETADA}
          dot={{ r: 2.6, fill: "var(--superficie-cartao)", stroke: COR.saldo, strokeWidth: 1.6 }}
          activeDot={{ r: 4.5 }}
          isAnimationActive={!semMovimento}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Sparkline dos cards numéricos (`FR-057`) — sem eixo, sem grade, sem dica. */
export function Sparkline({
  pontos,
  cor = COR.marca,
  comArea = false,
  altura = 34,
}: {
  pontos: { rotulo: string; valor: string }[];
  cor?: string;
  comArea?: boolean;
  altura?: number;
}) {
  if (pontos.length < 2) return null;
  const dados = pontos.map((p) => ({ x: p.rotulo, v: Number(p.valor) }));
  const id = `spark-${cor.replace(/[^a-z]/gi, "")}`;

  return (
    <ResponsiveContainer width="100%" height={altura}>
      <AreaChart data={dados} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        {comArea ? (
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={cor} stopOpacity={0.26} />
              <stop offset="100%" stopColor={cor} stopOpacity={0} />
            </linearGradient>
          </defs>
        ) : null}
        <Area
          type="monotone"
          dataKey="v"
          stroke={cor}
          strokeWidth={1.5}
          fill={comArea ? `url(#${id})` : "transparent"}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
