"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Eye, EyeOff } from "lucide-react";
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
import { useSalvarPreferencias } from "@/lib/consultas";
import type { CardDisponivel } from "@/lib/tipos";

/**
 * "Configurar cards" (T180, `FR-071`).
 *
 * O catálogo inteiro — inclusive os ocultos — vem em `cards_disponiveis` na
 * mesma resposta do Dashboard, para esta tela não precisar de outra
 * requisição. **Nenhum rótulo é escrito aqui**: todos vêm de
 * `configuracoes.dashboard_cards_disponiveis`.
 *
 * A ordem salva é a posição na lista, e a escolha explícita do usuário vence
 * o `ordem_padrao` do catálogo em caso de empate — sem esse desempate, mover
 * um card para uma posição já ocupada não fazia nada visível.
 */

const NOME_DO_GRUPO: Record<string, string> = {
  numerico: "Números",
  alerta: "Alertas",
  grafico: "Gráficos",
  especial: "Blocos especiais",
};

export function ConfigurarCards({
  catalogo,
  aberto,
  aoFechar,
}: {
  catalogo: CardDisponivel[];
  aberto: boolean;
  aoFechar: () => void;
}) {
  const salvar = useSalvarPreferencias();
  const [lista, setLista] = useState<CardDisponivel[]>([]);

  useEffect(() => {
    if (!aberto) return;
    setLista([...catalogo].sort((a, b) => a.ordem - b.ordem));
  }, [aberto, catalogo]);

  function mover(i: number, delta: number) {
    const j = i + delta;
    if (j < 0 || j >= lista.length) return;
    const nova = [...lista];
    [nova[i], nova[j]] = [nova[j], nova[i]];
    setLista(nova);
  }

  function alternar(id: string) {
    setLista((a) => a.map((c) => (c.id === id ? { ...c, visivel: !(c.visivel ?? true) } : c)));
  }

  function aplicar() {
    salvar.mutate(
      {
        dashboard_cards: lista.map((c, i) => ({
          id: c.id,
          visivel: c.visivel ?? true,
          ordem: i,
        })),
      },
      {
        onSuccess: () => {
          toast.success("Arranjo dos cards salvo.");
          aoFechar();
        },
        onError: () => toast.error("Não foi possível salvar o arranjo."),
      },
    );
  }

  return (
    <Dialog open={aberto} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="max-h-[86dvh] overflow-y-auto sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Configurar cards</DialogTitle>
          <DialogDescription>
            Mostre, esconda e reordene. A escolha vale só para você.
          </DialogDescription>
        </DialogHeader>

        <ul className="flex flex-col gap-1">
          {lista.map((c, i) => {
            const visivel = c.visivel ?? true;
            const grupoMudou = i === 0 || lista[i - 1].grupo !== c.grupo;
            return (
              <li key={c.id} className="flex flex-col">
                {grupoMudou ? (
                  <span className="rotulo-seccao mt-3 mb-1 first:mt-0">
                    {NOME_DO_GRUPO[c.grupo] ?? c.grupo}
                  </span>
                ) : null}
                <div className="flex items-center gap-2 rounded-[10px] border border-linha-suave px-3 py-2">
                  <span
                    className={`min-w-0 flex-1 truncate text-[13px] ${
                      visivel ? "text-[var(--fg)]" : "text-sutil line-through"
                    }`}
                  >
                    {c.rotulo}
                  </span>
                  <button
                    type="button"
                    aria-label={visivel ? `Ocultar ${c.rotulo}` : `Mostrar ${c.rotulo}`}
                    onClick={() => alternar(c.id)}
                    className="rounded-[7px] p-1.5 text-suave transition-colors hover:bg-[var(--bg-subtle)]"
                  >
                    {visivel ? <Eye size={15} /> : <EyeOff size={15} />}
                  </button>
                  <button
                    type="button"
                    aria-label={`Subir ${c.rotulo}`}
                    disabled={i === 0}
                    onClick={() => mover(i, -1)}
                    className="rounded-[7px] p-1.5 text-suave transition-colors hover:bg-[var(--bg-subtle)] disabled:opacity-30"
                  >
                    <ChevronUp size={15} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Descer ${c.rotulo}`}
                    disabled={i === lista.length - 1}
                    onClick={() => mover(i, 1)}
                    className="rounded-[7px] p-1.5 text-suave transition-colors hover:bg-[var(--bg-subtle)] disabled:opacity-30"
                  >
                    <ChevronDown size={15} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button disabled={salvar.isPending} onClick={aplicar}>
            Salvar arranjo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
