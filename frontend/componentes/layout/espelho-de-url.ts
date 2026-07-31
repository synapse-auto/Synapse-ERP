"use client";

import { useEffect, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEstadoGlobal } from "@/lib/estado-global";

/**
 * Espelha mundo e período na URL (`FR-001`).
 *
 * Duas direções, uma vez cada:
 *
 * - **URL → loja**, só na primeira montagem. Quem abre um link compartilhado
 *   vê o que o link diz, e não o que o `localStorage` lembrava.
 * - **Loja → URL**, a cada mudança, com `replace`. É `replace` e não `push`
 *   de propósito: trocar de mundo cinco vezes não deve encher o histórico de
 *   volta com cinco passos.
 */
export function useEspelharEscopoNaUrl(): void {
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();

  const mundo = useEstadoGlobal((e) => e.mundo);
  const periodo = useEstadoGlobal((e) => e.periodo);
  const dataInicio = useEstadoGlobal((e) => e.dataInicio);
  const dataFim = useEstadoGlobal((e) => e.dataFim);
  const hidratado = useEstadoGlobal((e) => e.hidratado);
  const hidratarDaUrl = useEstadoGlobal((e) => e.hidratarDaUrl);

  const jaLeu = useRef(false);

  useEffect(() => {
    if (jaLeu.current) return;
    jaLeu.current = true;
    hidratarDaUrl(new URLSearchParams(params.toString()));
  }, [params, hidratarDaUrl]);

  useEffect(() => {
    if (!hidratado) return;
    const atual = new URLSearchParams(params.toString());
    const alvo = new URLSearchParams(params.toString());

    alvo.set("mundo", mundo);
    alvo.set("periodo", periodo);
    if (periodo === "personalizado") {
      if (dataInicio) alvo.set("data_inicio", dataInicio);
      else alvo.delete("data_inicio");
      if (dataFim) alvo.set("data_fim", dataFim);
      else alvo.delete("data_fim");
    } else {
      alvo.delete("data_inicio");
      alvo.delete("data_fim");
    }

    if (alvo.toString() === atual.toString()) return;
    router.replace(`${caminho}?${alvo.toString()}`, { scroll: false });
  }, [mundo, periodo, dataInicio, dataFim, hidratado, caminho, params, router]);
}
