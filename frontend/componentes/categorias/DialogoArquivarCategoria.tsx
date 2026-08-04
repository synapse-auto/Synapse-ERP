"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/componentes/ui/dialog";
import { Button } from "@/componentes/ui/button";
import { Label } from "@/componentes/ui/label";
import { api, ErroApi, mensagemDoErro } from "@/lib/api";
import { useInvalidarFinanceiro } from "@/lib/consultas";
import { dinheiro, inteiro } from "@/lib/formato";
import type { Categoria } from "@/lib/tipos";

/**
 * Arquivar categoria (`RN-06`, `FR-075`).
 *
 * O fluxo é de duas etapas, e é o servidor que decide se a segunda é
 * necessária: sem lançamentos, a primeira chamada já arquiva; com
 * lançamentos, ela responde `422 confirmacao_necessaria` com a prévia
 * (quantos e quanto), e aí a tela pergunta o destino.
 *
 * **Nunca deixa lançamento sem categoria** — as duas saídas são mover para
 * outra categoria ou manter o vínculo somente-leitura.
 */
export function DialogoArquivarCategoria({
  categoria,
  categorias,
  aoFechar,
}: {
  categoria: Categoria | null;
  categorias: Categoria[];
  aoFechar: () => void;
}) {
  const invalidar = useInvalidarFinanceiro();
  const [previa, setPrevia] = useState<{
    mensagem: string;
    quantidade: number;
    valor: string;
  } | null>(null);
  const [destino, setDestino] = useState("");
  const [somenteLeitura, setSomenteLeitura] = useState(false);

  useEffect(() => {
    if (!categoria) return;
    setPrevia(null);
    setDestino("");
    setSomenteLeitura(false);
  }, [categoria]);

  const arquivar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      api.post(`/api/categorias/${categoria!.id}/arquivar`, { corpo }),
    onSuccess: () => {
      invalidar();
      toast.success("Categoria arquivada.");
      aoFechar();
    },
    onError: (e) => {
      if (e instanceof ErroApi && e.pedeConfirmacao) {
        const p = (e.previa ?? {}) as { quantidade_lancamentos?: number; valor_total?: string };
        setPrevia({
          mensagem: e.message,
          quantidade: p.quantidade_lancamentos ?? 0,
          valor: p.valor_total ?? "0",
        });
        return;
      }
      toast.error(mensagemDoErro(e));
    },
  });

  const outras = categorias.filter((c) => c.id !== categoria?.id && !c.arquivada_em && !c.especial);
  const podeConfirmar = somenteLeitura || Boolean(destino);

  return (
    <Dialog open={Boolean(categoria)} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Arquivar {categoria?.nome}</DialogTitle>
          <DialogDescription>
            Categoria não é excluída — é arquivada. Ela some das listas novas e continua valendo
            para o histórico.
          </DialogDescription>
        </DialogHeader>

        {!previa ? (
          <p className="text-[13px] text-suave">
            Se houver lançamentos nesta categoria, o sistema vai perguntar o que fazer com eles
            antes de arquivar.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            <p
              className="rounded-[8px] px-3 py-2.5 text-[13px]"
              style={{ background: "var(--st-pendente-bg)", color: "var(--st-pendente-fg)" }}
            >
              {previa.mensagem}
            </p>

            <dl className="grid grid-cols-2 gap-3 rounded-[10px] bg-[var(--bg-subtle)] p-4 text-[13px]">
              <div>
                <dt className="text-sutil">Lançamentos</dt>
                <dd className="numerico font-[family-name:var(--font-display)] text-[16px] font-bold text-forte">
                  {inteiro(previa.quantidade)}
                </dd>
              </div>
              <div>
                <dt className="text-sutil">Movimentado</dt>
                <dd className="numerico font-[family-name:var(--font-display)] text-[16px] font-bold text-forte">
                  {dinheiro(previa.valor)}
                </dd>
              </div>
            </dl>

            <div className="flex flex-col gap-2">
              <Label htmlFor="destino">Mover os lançamentos para</Label>
              <select
                id="destino"
                value={destino}
                onChange={(e) => {
                  setDestino(e.target.value);
                  if (e.target.value) setSomenteLeitura(false);
                }}
                className="h-9 rounded-[8px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
              >
                <option value="">Escolha a categoria de destino…</option>
                {outras.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
            </div>

            <label className="flex cursor-pointer items-start gap-2 text-[13px]">
              <input
                type="radio"
                checked={somenteLeitura}
                onChange={() => {
                  setSomenteLeitura(true);
                  setDestino("");
                }}
                className="mt-1 accent-[var(--brand)]"
              />
              <span>
                <span className="font-semibold text-[var(--fg)]">
                  Ou manter o vínculo somente-leitura
                </span>
                <span className="block text-sutil">
                  Os lançamentos continuam nesta categoria e ela deixa de aceitar novos.
                </span>
              </span>
            </label>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button
            disabled={arquivar.isPending || (Boolean(previa) && !podeConfirmar)}
            onClick={() =>
              arquivar.mutate(
                previa
                  ? { destino_lancamentos: destino || null, manter_somente_leitura: somenteLeitura }
                  : { destino_lancamentos: null, manter_somente_leitura: false },
              )
            }
          >
            Arquivar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
