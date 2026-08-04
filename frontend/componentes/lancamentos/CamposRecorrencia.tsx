"use client";

import { useEffect, useState } from "react";
import type { UseFormReturn } from "react-hook-form";
import { api } from "@/lib/api";
import { Input } from "@/componentes/ui/input";
import { Label } from "@/componentes/ui/label";
import { data as formatarData, dinheiro } from "@/lib/formato";
import type { RespostaPrevia } from "@/lib/tipos";
import type { ValoresLancamento } from "./FormLancamento";

/**
 * Campos de recorrência (T171, `FR-025`–`FR-027`).
 *
 * Enquanto se preenche, o formulário pede a **prévia** ao servidor
 * (`POST /api/recorrencias/previa`, que não grava nada) e mostra quantas
 * ocorrências vão nascer e em que intervalo. É o que evita a surpresa de
 * `FR-027`: começar em março do ano passado cria 17 lançamentos de uma vez,
 * e a pessoa precisa ver isso antes, não depois.
 *
 * A leitura da frequência ("Mensal, dia 10") **não é montada aqui**: quem
 * devolve o rótulo pronto é a API (`RNF-02`, contracts/lancamentos.md §3).
 * O que existe abaixo é o formulário, não o texto.
 */
export function CamposRecorrencia({ form }: { form: UseFormReturn<ValoresLancamento> }) {
  const { register, watch } = form;
  const [previa, setPrevia] = useState<RespostaPrevia | null>(null);
  const [buscando, setBuscando] = useState(false);

  const frequencia = watch("frequencia");
  const dia = watch("dia_vencimento");
  const inicio = watch("data");
  const fim = watch("data_fim");
  const valor = watch("valor");
  const intervaloDias = watch("intervalo_dias");

  useEffect(() => {
    if (!inicio) return;
    let vivo = true;
    const t = setTimeout(async () => {
      setBuscando(true);
      try {
        const r = await api.post<RespostaPrevia>("/api/recorrencias/previa", {
          corpo: {
            frequencia,
            intervalo_dias: frequencia === "dias" ? Number(intervaloDias || 0) : null,
            dia_vencimento: frequencia === "mensal" ? Number(dia || 1) : null,
            mes_vencimento: null,
            data_inicio: inicio,
            data_fim: fim || null,
            total_parcelas: null,
            valor: valor ? valor.replace(",", ".") : null,
          },
        });
        if (vivo) setPrevia(r);
      } catch {
        // Prévia é conforto, não requisito: se falhar, o formulário segue e
        // o `422` na hora de criar continua explicando o impacto.
        if (vivo) setPrevia(null);
      } finally {
        if (vivo) setBuscando(false);
      }
    }, 420);
    return () => {
      vivo = false;
      clearTimeout(t);
    };
  }, [frequencia, dia, inicio, fim, valor, intervaloDias]);

  return (
    <div className="flex flex-col gap-4 rounded-[10px] border border-linha-suave bg-[var(--bg-subtle)] p-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="frequencia">Frequência</Label>
          <select
            id="frequencia"
            {...register("frequencia")}
            className="h-9 rounded-[8px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
          >
            <option value="mensal">Mensal</option>
            <option value="semanal">Semanal</option>
            <option value="anual">Anual</option>
            <option value="dias">A cada N dias</option>
          </select>
        </div>

        {frequencia === "mensal" ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dia_vencimento">Dia do mês</Label>
            <Input id="dia_vencimento" type="number" min={1} max={31} {...register("dia_vencimento")} />
            {Number(dia) > 28 ? (
              <p className="text-[12px] text-sutil">
                Em meses mais curtos, cai no último dia do mês.
              </p>
            ) : null}
          </div>
        ) : null}

        {frequencia === "dias" ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="intervalo_dias">A cada quantos dias</Label>
            <Input id="intervalo_dias" type="number" min={1} {...register("intervalo_dias")} />
          </div>
        ) : null}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="data_fim">Termina em (opcional)</Label>
          <Input id="data_fim" type="date" {...register("data_fim")} />
        </div>
      </div>

      {previa ? (
        <div className="flex flex-col gap-1 rounded-[8px] bg-superficie-cartao px-3 py-2.5 text-[12px]">
          <span className="text-[var(--fg)]">
            Serão criadas{" "}
            <strong className="numerico">{previa.previa.total_ocorrencias}</strong> ocorrências
            entre {formatarData(previa.previa.primeira)} e {formatarData(previa.previa.ultima)}.
          </span>
          {previa.previa.retroativas_efetivadas > 0 ? (
            <span className="text-suave">
              <strong className="numerico">{previa.previa.retroativas_efetivadas}</strong> já
              nascem efetivadas — o passado já aconteceu
              {previa.previa.valor_total_retroativo
                ? ` e soma ${dinheiro(previa.previa.valor_total_retroativo)}`
                : ""}
              .
            </span>
          ) : null}
          <span className="text-sutil">
            Horizonte de geração até {formatarData(previa.horizonte)}. Acima de{" "}
            {previa.limiar_de_confirmacao} ocorrências, o sistema pede confirmação.
          </span>
        </div>
      ) : buscando ? (
        <div className="h-[52px] animate-pulse rounded-[8px] bg-superficie-cartao" />
      ) : null}
    </div>
  );
}
