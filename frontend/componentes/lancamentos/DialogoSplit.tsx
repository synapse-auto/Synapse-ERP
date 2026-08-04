"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
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
import { Label } from "@/componentes/ui/label";
import { useCategorias } from "@/lib/consultas";
import { dinheiro } from "@/lib/formato";
import { ErroApi } from "@/lib/api";
import { useDividir } from "./acoes";
import type { Lancamento, ParteSplit } from "@/lib/tipos";

/**
 * Dividir um lançamento em partes (T166, `FR-019`, `FR-020`, `RN-11`).
 *
 * A tela mostra **quanto falta fechar** enquanto se digita. Isso é aritmética
 * de apresentação, não a regra: quem recusa é o backend, que compara em
 * `numeric` e devolve a diferença em `campos.partes`. Somar centavos em
 * ponto flutuante aqui e confiar nisso seria justamente o erro que `RN-11`
 * existe para pegar — por isso a conta local é feita em **centavos inteiros**
 * e serve só para acender ou apagar o aviso.
 */

function paraCentavos(texto: string): number | null {
  const limpo = texto.replace(/\s/g, "").replace(",", ".");
  if (!limpo) return null;
  const n = Number(limpo);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100);
}

interface LinhaParte {
  descricao: string;
  valor: string;
  categoria_id: string;
}

export function DialogoSplit({
  lancamento,
  aberto,
  aoFechar,
}: {
  lancamento: Lancamento;
  aberto: boolean;
  aoFechar: () => void;
}) {
  const { data: categorias } = useCategorias();
  const dividir = useDividir();
  const [partes, setPartes] = useState<LinhaParte[]>([]);
  const [erroDoServidor, setErroDoServidor] = useState<ErroApi | null>(null);

  useEffect(() => {
    if (!aberto) return;
    setErroDoServidor(null);
    setPartes([
      { descricao: "", valor: "", categoria_id: lancamento.categoria.id },
      { descricao: "", valor: "", categoria_id: lancamento.categoria.id },
    ]);
  }, [aberto, lancamento.categoria.id]);

  const totalPai = paraCentavos(lancamento.valor) ?? 0;
  const somaPartes = partes.reduce((acc, p) => acc + (paraCentavos(p.valor) ?? 0), 0);
  const diferenca = totalPai - somaPartes;
  const fecha = diferenca === 0 && partes.length >= 2;

  function atualizar(i: number, campo: keyof LinhaParte, valor: string) {
    setPartes((atual) => atual.map((p, j) => (j === i ? { ...p, [campo]: valor } : p)));
  }

  /** Joga o que falta na parte informada — é o atalho que a pessoa quer. */
  function completar(i: number) {
    const atual = paraCentavos(partes[i].valor) ?? 0;
    const alvo = (atual + diferenca) / 100;
    atualizar(i, "valor", alvo.toFixed(2));
  }

  async function salvar() {
    setErroDoServidor(null);
    const corpo: ParteSplit[] = partes.map((p) => ({
      descricao: p.descricao.trim() || lancamento.descricao,
      valor: ((paraCentavos(p.valor) ?? 0) / 100).toFixed(2),
      categoria_id: p.categoria_id,
      subcategoria_id: null,
      centro_custo_id: null,
    }));
    try {
      await dividir.mutateAsync({ id: lancamento.id, partes: corpo });
      aoFechar();
    } catch (e) {
      if (e instanceof ErroApi) setErroDoServidor(e);
    }
  }

  return (
    <Dialog open={aberto} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="sm:max-w-[620px]">
        <DialogHeader>
          <DialogTitle>Dividir em partes</DialogTitle>
          <DialogDescription>
            {lancamento.descricao} — {dinheiro(lancamento.valor)}. Depois de dividir, o
            lançamento original sai dos totais e só as partes contam.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          {partes.map((p, i) => (
            <div key={i} className="grid grid-cols-[1fr_150px_130px_32px] items-end gap-2">
              <div className="flex flex-col gap-1.5">
                {i === 0 ? <Label className="text-[12px]">Descrição</Label> : null}
                <Input
                  value={p.descricao}
                  placeholder={lancamento.descricao}
                  onChange={(e) => atualizar(i, "descricao", e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                {i === 0 ? <Label className="text-[12px]">Categoria</Label> : null}
                <select
                  value={p.categoria_id}
                  onChange={(e) => atualizar(i, "categoria_id", e.target.value)}
                  className="h-9 rounded-[8px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
                >
                  {(categorias?.itens ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                {i === 0 ? <Label className="text-[12px]">Valor</Label> : null}
                <Input
                  inputMode="decimal"
                  value={p.valor}
                  placeholder="0,00"
                  onChange={(e) => atualizar(i, "valor", e.target.value)}
                  onDoubleClick={() => completar(i)}
                  title="Duplo clique preenche com o que falta"
                  className="numerico text-right"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Remover parte"
                disabled={partes.length <= 2}
                onClick={() => setPartes((a) => a.filter((_, j) => j !== i))}
              >
                <Trash2 size={15} />
              </Button>
            </div>
          ))}

          <Button
            type="button"
            variant="outline"
            size="sm"
            className="self-start"
            onClick={() =>
              setPartes((a) => [
                ...a,
                { descricao: "", valor: "", categoria_id: lancamento.categoria.id },
              ])
            }
          >
            <Plus size={14} />
            Mais uma parte
          </Button>
        </div>

        <div
          className="flex items-center justify-between rounded-[8px] px-3 py-2.5 text-[13px]"
          style={{
            background: fecha ? "var(--receita-bg)" : "var(--st-pendente-bg)",
            color: fecha ? "var(--receita-fg)" : "var(--st-pendente-fg)",
          }}
        >
          <span>
            Soma das partes: <strong className="numerico">{dinheiro(somaPartes / 100)}</strong> de{" "}
            <strong className="numerico">{dinheiro(lancamento.valor)}</strong>
          </span>
          <strong className="numerico">
            {fecha
              ? "fecha exatamente"
              : diferenca > 0
                ? `faltam ${dinheiro(diferenca / 100)}`
                : `sobram ${dinheiro(-diferenca / 100)}`}
          </strong>
        </div>

        {erroDoServidor ? (
          <p
            role="alert"
            className="rounded-[8px] px-3 py-2 text-[13px]"
            style={{ background: "var(--st-atrasado-bg)", color: "var(--st-atrasado-fg)" }}
          >
            {erroDoServidor.message}
            {erroDoServidor.campos?.partes ? ` ${erroDoServidor.campos.partes}` : ""}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button disabled={!fecha || dividir.isPending} onClick={() => void salvar()}>
            Dividir em {partes.length} partes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
