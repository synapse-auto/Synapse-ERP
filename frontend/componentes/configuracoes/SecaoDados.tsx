"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Quadro } from "@/componentes/comum/CabecalhoTela";
import { Button } from "@/componentes/ui/button";
import { baixarArquivo, mensagemDoErro } from "@/lib/api";
import { useEstadoRotina } from "@/lib/consultas";
import { instante } from "@/lib/formato";

/**
 * Dados e backup (T199, `FR-112`, `RNF-06`).
 *
 * Duas honestidades que precisam estar escritas na tela, não só no contrato:
 *
 * 1. **A exportação é síncrona.** O desenho original previa `GET
 *    /api/exportacoes/{id}` e gravação por lote com cursor; não foi o que se
 *    implementou. O `POST` monta o ZIP inteiro numa invocação e devolve na
 *    hora — o que cabe com folga no volume desta empresa. Por isso aqui não
 *    há barra de progresso nem link assinado ao final: seria interface para
 *    um fluxo que não existe.
 * 2. **Os arquivos anexados não vão no pacote.** Eles vivem no bucket
 *    privado; `anexos.csv` traz o caminho de cada um.
 */
export function SecaoDados() {
  const [baixando, setBaixando] = useState(false);
  const { data: rotina } = useEstadoRotina(true);

  async function exportar() {
    setBaixando(true);
    try {
      const hoje = new Date().toISOString().slice(0, 10);
      await baixarArquivo("/api/exportacoes/completa", `synapse-erp-${hoje}.zip`, { corpo: {} });
      toast.success("Exportação concluída.");
    } catch (e) {
      toast.error(mensagemDoErro(e));
    } finally {
      setBaixando(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Quadro>
        <div className="flex flex-col gap-1 border-b border-linha-suave px-4 py-3">
          <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
            Exportação completa
          </span>
          <span className="text-[12px] text-suave">
            Um ZIP com um CSV por tabela de negócio, em formato de dados (separador vírgula,
            decimal com ponto, datas ISO), mais um LEIA-ME com a contagem por tabela.
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-4">
          <ul className="flex flex-col gap-1 text-[12px] text-suave">
            <li>· Os arquivos anexados não vão no pacote — o CSV traz o caminho de cada um.</li>
            <li>· A tabela de importações fica de fora: é rascunho que expira em 24 horas.</li>
            <li>· O backup automático do banco é o backup gerenciado do Supabase.</li>
          </ul>
          <Button disabled={baixando} onClick={() => void exportar()}>
            {baixando ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            Baixar tudo
          </Button>
        </div>
      </Quadro>

      <Quadro>
        <div className="flex flex-col gap-1 border-b border-linha-suave px-4 py-3">
          <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
            Rotina automática
          </span>
          <span className="text-[12px] text-suave">
            Materializa recorrências, aplica o ciclo de status, reavalia inadimplência e gera os
            avisos. Roda uma vez por dia; um dia perdido é recuperado na execução seguinte.
          </span>
        </div>
        <dl className="grid gap-4 px-4 py-4 sm:grid-cols-2">
          <div>
            <dt className="text-[11.5px] text-sutil">Última execução</dt>
            <dd className="text-[13px] text-[var(--fg)]">
              {rotina?.ultima_execucao ? instante(rotina.ultima_execucao) : "nunca"}
            </dd>
          </div>
          <div>
            <dt className="text-[11.5px] text-sutil">Último dia processado</dt>
            <dd className="text-[13px] text-[var(--fg)]">
              {rotina?.ultima_data_processada ?? "—"}
            </dd>
          </div>
          {rotina?.ultimo_resultado ? (
            <div className="sm:col-span-2">
              <dt className="mb-1 text-[11.5px] text-sutil">Resultado</dt>
              <dd className="flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-suave">
                {Object.entries(rotina.ultimo_resultado).map(([k, v]) => (
                  <span key={k}>
                    {k.replace(/_/g, " ")}:{" "}
                    <strong className="numerico font-semibold text-[var(--fg)]">
                      {Array.isArray(v) ? v.length : String(v)}
                    </strong>
                  </span>
                ))}
              </dd>
            </div>
          ) : null}
        </dl>
      </Quadro>
    </div>
  );
}
