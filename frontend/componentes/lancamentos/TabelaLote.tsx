"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/componentes/ui/dialog";
import { Button } from "@/componentes/ui/button";
import { Input } from "@/componentes/ui/input";
import { Seletor } from "@/componentes/comum/Seletor";
import { useCategorias, useConfiguracoes } from "@/lib/consultas";
import { useEstadoGlobal } from "@/lib/estado-global";
import { paraApi } from "@/lib/formato";
import { ErroApi } from "@/lib/api";
import { useCriarEmLote } from "./acoes";
import type { Mundo, RespostaLote } from "@/lib/tipos";

/**
 * Tabela editável para criar vários lançamentos de uma vez (T167, `FR-021`).
 *
 * **Tudo ou nada**: uma linha inválida recusa o lote inteiro. O backend
 * devolve **todas** as linhas com problema de uma vez, e a tabela marca todas
 * numa passada — em vez de a pessoa corrigir uma, reenviar e descobrir a
 * próxima. O texto de cada erro é o do servidor.
 *
 * Teto de 200 linhas por chamada, que é o que cabe na duração máxima da
 * função sem ser cortado no meio.
 */

const TETO = 200;

interface Linha {
  data: string;
  descricao: string;
  valor: string;
  tipo: "receita" | "despesa";
  categoria_id: string;
  mundo: Mundo;
}

function linhaVazia(mundo: Mundo): Linha {
  return {
    data: paraApi(new Date()),
    descricao: "",
    valor: "",
    tipo: "despesa",
    categoria_id: "",
    mundo,
  };
}

export function TabelaLote({ aberta, aoFechar }: { aberta: boolean; aoFechar: () => void }) {
  const mundoGlobal = useEstadoGlobal((e) => e.mundo);
  const mundoPadrao: Mundo = mundoGlobal === "ambos" ? "digital" : mundoGlobal;
  const { data: categorias } = useCategorias();
  const { data: configuracoes } = useConfiguracoes();
  const criar = useCriarEmLote();

  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [erros, setErros] = useState<RespostaLote["erros"]>([]);

  useEffect(() => {
    if (!aberta) return;
    setLinhas([linhaVazia(mundoPadrao), linhaVazia(mundoPadrao), linhaVazia(mundoPadrao)]);
    setErros([]);
  }, [aberta, mundoPadrao]);

  const efetivacaoPadrao = Boolean(
    (configuracoes?.efetivacao_automatica_padrao?.valor as boolean | undefined) ?? true,
  );

  function atualizar(i: number, campo: keyof Linha, valor: string) {
    setLinhas((a) => a.map((l, j) => (j === i ? { ...l, [campo]: valor } : l)));
  }

  const preenchidas = linhas.filter((l) => l.descricao.trim() && l.valor.trim());

  async function salvar() {
    setErros([]);
    if (preenchidas.length === 0) {
      toast.error("Preencha ao menos uma linha.");
      return;
    }
    if (preenchidas.length > TETO) {
      toast.error(`Máximo de ${TETO} lançamentos por lote. Divida em duas remessas.`);
      return;
    }
    try {
      const r = await criar.mutateAsync(
        preenchidas.map((l) => ({
          mundo: l.mundo,
          tipo: l.tipo,
          descricao: l.descricao.trim(),
          data: l.data,
          moeda: "BRL",
          valor: Number(l.valor.replace(",", ".")).toFixed(2),
          categoria_id: l.categoria_id,
          subcategoria_id: null,
          servico_id: null,
          centro_custo_id: null,
          tag_ids: [],
          observacoes: null,
          efetivar_automaticamente: efetivacaoPadrao,
        })),
      );
      toast.success(`${r.criados} lançamentos criados.`);
      aoFechar();
    } catch (e) {
      if (e instanceof ErroApi) {
        const corpo = (e as unknown as { erros?: RespostaLote["erros"] }).erros;
        if (corpo) setErros(corpo);
        toast.error(e.message);
      }
    }
  }

  const erroDaLinha = (i: number) => erros.find((x) => x.indice === i);

  return (
    <Dialog open={aberta} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-[900px]">
        <DialogHeader>
          <DialogTitle>Criar em lote</DialogTitle>
          <DialogDescription>
            Uma linha por lançamento. Se qualquer linha for recusada, nenhuma é gravada — meio
            lote gravado é pior que nenhum.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-1">
          <div className="grid grid-cols-[130px_1fr_110px_120px_180px_36px] gap-2 px-1 pb-1">
            {["Data", "Descrição", "Tipo", "Valor", "Categoria", ""].map((c) => (
              <span
                key={c}
                className="font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.07em] text-sutil uppercase"
              >
                {c}
              </span>
            ))}
          </div>

          {linhas.map((l, i) => {
            const erro = erroDaLinha(i);
            return (
              <div key={i} className="flex flex-col gap-1">
                <div
                  className={cn(
                    "grid grid-cols-[130px_1fr_110px_120px_180px_36px] items-center gap-2 rounded-[8px] p-1",
                    erro && "bg-[var(--st-atrasado-bg)]",
                  )}
                >
                  <Input type="date" value={l.data} onChange={(e) => atualizar(i, "data", e.target.value)} />
                  <Input
                    value={l.descricao}
                    placeholder="Descrição"
                    onChange={(e) => atualizar(i, "descricao", e.target.value)}
                  />
                  <Seletor
                    rotuloAcessivel={`Tipo da linha ${i + 1}`}
                    valor={l.tipo}
                    aoMudar={(v) => atualizar(i, "tipo", v)}
                    opcoes={[
                      { valor: "despesa", rotulo: "Despesa", cor: "var(--despesa-fg)" },
                      { valor: "receita", rotulo: "Receita", cor: "var(--receita-fg)" },
                    ]}
                  />
                  <Input
                    inputMode="decimal"
                    value={l.valor}
                    placeholder="0,00"
                    className="numerico text-right"
                    onChange={(e) => atualizar(i, "valor", e.target.value)}
                  />
                  <Seletor
                    rotuloAcessivel={`Categoria da linha ${i + 1}`}
                    valor={l.categoria_id}
                    aoMudar={(v) => atualizar(i, "categoria_id", v)}
                    placeholder="Categoria…"
                    opcoes={(categorias?.itens ?? [])
                      .filter((c) => c.tipo === "ambas" || c.tipo === l.tipo)
                      .map((c) => ({ valor: c.id, rotulo: c.nome, cor: c.cor }))}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="Remover linha"
                    disabled={linhas.length <= 1}
                    onClick={() => setLinhas((a) => a.filter((_, j) => j !== i))}
                  >
                    <Trash2 size={15} />
                  </Button>
                </div>
                {erro ? (
                  <p className="px-2 text-[12px] text-[var(--danger-500)]">
                    {erro.mensagem}
                    {erro.requisito ? ` (${erro.requisito})` : ""}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          disabled={linhas.length >= TETO}
          onClick={() => setLinhas((a) => [...a, linhaVazia(mundoPadrao)])}
        >
          <Plus size={14} />
          Mais uma linha
        </Button>

        <DialogFooter>
          <span className="mr-auto text-[12px] text-sutil">
            {preenchidas.length} de {TETO} linhas preenchidas
          </span>
          <Button variant="outline" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button disabled={criar.isPending || preenchidas.length === 0} onClick={() => void salvar()}>
            Criar {preenchidas.length || ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
