"use client";

import { useState } from "react";
import { ptBR } from "date-fns/locale";
import type { DateRange } from "react-day-picker";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/componentes/ui/popover";
import { Calendar } from "@/componentes/ui/calendar";
import { Button } from "@/componentes/ui/button";
import { useEstadoGlobal } from "@/lib/estado-global";
import { dataDaApi, intervalo, paraApi } from "@/lib/formato";
import type { AtalhoPeriodo } from "@/lib/tipos";

/**
 * Seletor de período (T158).
 *
 * **Quem resolve as datas é o servidor** (contracts/README.md §Período): aqui
 * só viaja a chave do atalho. É o que garante que o comparativo "vs. junho"
 * use exatamente a mesma régua que o total do período — se o frontend
 * calculasse "este mês" por conta, um fuso ou um dia 31 já bastaria para os
 * dois números discordarem.
 *
 * O trilho mostra os cinco atalhos do mockup. `Hoje` e `Esta semana` existem
 * no contrato e ficam dentro do painel de "Personalizado", que é onde quem
 * precisa deles vai procurar.
 */

const NO_TRILHO: { valor: AtalhoPeriodo; rotulo: string }[] = [
  { valor: "este_mes", rotulo: "Este mês" },
  { valor: "mes_passado", rotulo: "Mês passado" },
  { valor: "ultimos_3_meses", rotulo: "3 meses" },
  { valor: "este_ano", rotulo: "Este ano" },
];

const NO_PAINEL: { valor: AtalhoPeriodo; rotulo: string }[] = [
  { valor: "hoje", rotulo: "Hoje" },
  { valor: "esta_semana", rotulo: "Esta semana" },
];

export function SeletorPeriodo({ className }: { className?: string }) {
  const periodo = useEstadoGlobal((e) => e.periodo);
  const dataInicio = useEstadoGlobal((e) => e.dataInicio);
  const dataFim = useEstadoGlobal((e) => e.dataFim);
  const definirPeriodo = useEstadoGlobal((e) => e.definirPeriodo);
  const [aberto, setAberto] = useState(false);

  const faixa: DateRange | undefined = dataInicio
    ? { from: dataDaApi(dataInicio), to: dataFim ? dataDaApi(dataFim) : undefined }
    : undefined;

  const rotuloPersonalizado =
    periodo === "personalizado" && dataInicio && dataFim
      ? intervalo(dataInicio, dataFim)
      : periodo === "hoje"
        ? "Hoje"
        : periodo === "esta_semana"
          ? "Esta semana"
          : "Personalizado";

  const painelAtivo =
    periodo === "personalizado" || periodo === "hoje" || periodo === "esta_semana";

  const classeBotao = (ativo: boolean) =>
    cn(
      "rounded-[7px] px-[11px] py-[6px] whitespace-nowrap",
      "font-[family-name:var(--font-display)] text-[12.5px] font-semibold tracking-[-0.01em]",
      "transition-colors duration-[var(--dur-fast)] ease-[var(--ease-out)]",
      ativo
        ? "bg-superficie-cartao text-[var(--ink-700)] shadow-[0_1px_2px_rgba(30,22,51,0.08)] dark:text-[var(--fg-strong)]"
        : "text-suave hover:text-[var(--fg)]",
    );

  return (
    <div className={cn("flex items-center gap-2 pr-1", className)}>
      <span className="font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.07em] text-[var(--ink-300)] uppercase dark:text-[var(--fg-subtle)]">
        Período
      </span>
      <div
        role="radiogroup"
        aria-label="Período"
        className="flex items-center gap-[2px] rounded-[9px] border border-linha-suave bg-segmento p-[3px]"
      >
        {NO_TRILHO.map((p) => (
          <button
            key={p.valor}
            type="button"
            role="radio"
            aria-checked={periodo === p.valor}
            onClick={() => definirPeriodo(p.valor)}
            className={classeBotao(periodo === p.valor)}
          >
            {p.rotulo}
          </button>
        ))}

        <Popover open={aberto} onOpenChange={setAberto}>
          <PopoverTrigger asChild>
            <button
              type="button"
              role="radio"
              aria-checked={painelAtivo}
              className={classeBotao(painelAtivo)}
            >
              {rotuloPersonalizado}
            </button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-auto p-0">
            <div className="flex flex-col gap-1 border-b border-linha-suave p-2">
              {NO_PAINEL.map((p) => (
                <button
                  key={p.valor}
                  type="button"
                  onClick={() => {
                    definirPeriodo(p.valor);
                    setAberto(false);
                  }}
                  className={cn(
                    "rounded-[8px] px-2.5 py-1.5 text-left text-[12.5px] transition-colors",
                    periodo === p.valor
                      ? "bg-[var(--brand-tint-2)] font-semibold text-[var(--lateral-ativo-fg)]"
                      : "text-suave hover:bg-[var(--bg-subtle)]",
                  )}
                >
                  {p.rotulo}
                </button>
              ))}
            </div>

            <Calendar
              mode="range"
              locale={ptBR}
              numberOfMonths={2}
              defaultMonth={faixa?.from}
              selected={faixa}
              onSelect={(nova) => {
                if (!nova?.from) return;
                definirPeriodo(
                  "personalizado",
                  paraApi(nova.from),
                  nova.to ? paraApi(nova.to) : paraApi(nova.from),
                );
              }}
            />

            <div className="flex items-center justify-between gap-2 border-t border-linha-suave p-2">
              <span className="pl-1 text-[11.5px] text-sutil">
                {dataInicio && dataFim ? intervalo(dataInicio, dataFim) : "Escolha o intervalo"}
              </span>
              <Button
                size="sm"
                disabled={!dataInicio || !dataFim}
                onClick={() => setAberto(false)}
              >
                Aplicar
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}
