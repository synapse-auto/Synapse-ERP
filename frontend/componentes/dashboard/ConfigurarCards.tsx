"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Columns2, Eye, EyeOff, GripVertical, Square } from "lucide-react";
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
import { useSalvarPreferencias } from "@/lib/consultas";
import type { CardDisponivel, LarguraDoCard } from "@/lib/tipos";

/**
 * "Configurar cards" (T180, `FR-071`; arrastar e largura em T217).
 *
 * O catálogo inteiro — inclusive os ocultos — vem em `cards_disponiveis` na
 * mesma resposta do Dashboard, para esta tela não precisar de outra
 * requisição. **Nenhum rótulo é escrito aqui**: todos vêm de
 * `configuracoes.dashboard_cards_disponiveis`.
 *
 * A ordem salva é a posição na lista, e a escolha explícita do usuário vence
 * o `ordem_padrao` do catálogo em caso de empate — sem esse desempate, mover
 * um card para uma posição já ocupada não fazia nada visível.
 *
 * **Três formas de reordenar, de propósito.** Arrastar é o gesto natural com
 * mouse; as setas continuam porque arrastar não funciona no teclado nem em
 * leitor de tela, e sumir com elas trocaria conveniência por exclusão.
 *
 * **Largura** decide se o card ocupa a linha inteira ou metade dela — é o que
 * põe dois cards lado a lado. Card do grupo `numerico` não tem essa escolha:
 * eles vivem numa faixa própria de quatro colunas.
 */

const NOME_DO_GRUPO: Record<string, string> = {
  numerico: "Números",
  alerta: "Alertas",
  grafico: "Gráficos",
  especial: "Blocos especiais",
};

/**
 * Tira o item de `de` e o **insere** em `para`.
 *
 * Não é troca de posição: arrastar o primeiro para o quarto lugar tem de
 * empurrar os três do meio para cima, não trocar o primeiro com o quarto. As
 * setas ↑↓ usam a mesma função com `delta = ±1`, onde inserir e trocar dão no
 * mesmo — assim existe uma regra de reordenação só.
 */
export function moverNaLista<T>(lista: T[], de: number, para: number): T[] {
  if (de === para || de < 0 || para < 0 || de >= lista.length || para >= lista.length) return lista;
  const nova = [...lista];
  const [item] = nova.splice(de, 1);
  nova.splice(para, 0, item);
  return nova;
}

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
  const [arrastando, setArrastando] = useState<number | null>(null);
  const [alvo, setAlvo] = useState<number | null>(null);
  const origem = useRef<number | null>(null);

  useEffect(() => {
    if (!aberto) return;
    setLista([...catalogo].sort((a, b) => a.ordem - b.ordem));
    setArrastando(null);
    setAlvo(null);
  }, [aberto, catalogo]);

  function mover(i: number, delta: number) {
    setLista((a) => moverNaLista(a, i, i + delta));
  }

  function alternar(id: string) {
    setLista((a) => a.map((c) => (c.id === id ? { ...c, visivel: !(c.visivel ?? true) } : c)));
  }

  function alternarLargura(id: string) {
    setLista((a) =>
      a.map((c) =>
        c.id === id
          ? { ...c, largura: (c.largura === "inteira" ? "metade" : "inteira") as LarguraDoCard }
          : c,
      ),
    );
  }

  function aplicar() {
    salvar.mutate(
      {
        dashboard_cards: lista.map((c, i) => ({
          id: c.id,
          visivel: c.visivel ?? true,
          ordem: i,
          // `numerico` tem grade própria; mandar largura para ele seria gravar
          // uma escolha que a tela nunca lê.
          ...(c.grupo !== "numerico" && c.largura ? { largura: c.largura } : {}),
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
      <DialogContent className="max-h-[86dvh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Configurar cards</DialogTitle>
          <DialogDescription>
            Arraste para reordenar, escolha a largura e esconda o que não usa. A escolha vale
            só para você.
          </DialogDescription>
        </DialogHeader>

        <ul className="flex flex-col gap-1">
          {lista.map((c, i) => {
            const visivel = c.visivel ?? true;
            const grupoMudou = i === 0 || lista[i - 1].grupo !== c.grupo;
            const temLargura = c.grupo !== "numerico";
            const metade = c.largura !== "inteira";
            return (
              <li key={c.id} className="flex flex-col">
                {grupoMudou ? (
                  <span className="rotulo-seccao mt-3 mb-1 first:mt-0">
                    {NOME_DO_GRUPO[c.grupo] ?? c.grupo}
                  </span>
                ) : null}

                <div
                  draggable
                  onDragStart={(e) => {
                    origem.current = i;
                    setArrastando(i);
                    e.dataTransfer.effectAllowed = "move";
                    // O Firefox só inicia o arraste se algo for escrito aqui.
                    e.dataTransfer.setData("text/plain", c.id);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    if (alvo !== i) setAlvo(i);
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    const de = origem.current;
                    if (de !== null) setLista((a) => moverNaLista(a, de, i));
                    origem.current = null;
                    setArrastando(null);
                    setAlvo(null);
                  }}
                  onDragEnd={() => {
                    origem.current = null;
                    setArrastando(null);
                    setAlvo(null);
                  }}
                  className={cn(
                    "flex items-center gap-2 rounded-[8px] border px-2 py-2 select-none",
                    "transition-colors duration-[var(--dur-fast)]",
                    arrastando === i
                      ? "border-[var(--purple-300)] bg-[var(--brand-tint)] opacity-60"
                      : alvo === i && arrastando !== null
                        ? "border-[var(--brand)] bg-[var(--brand-tint)]"
                        : "border-linha-suave hover:border-[var(--purple-200)]",
                  )}
                >
                  <span
                    aria-hidden="true"
                    title="Arraste para reordenar"
                    className="flex flex-none cursor-grab items-center text-[var(--ink-300)] active:cursor-grabbing"
                  >
                    <GripVertical size={15} />
                  </span>

                  <span
                    className={cn(
                      "min-w-0 flex-1 truncate text-[13px]",
                      visivel ? "text-[var(--fg)]" : "text-sutil line-through",
                    )}
                  >
                    {c.rotulo}
                  </span>

                  {temLargura ? (
                    <button
                      type="button"
                      aria-pressed={!metade}
                      aria-label={
                        metade
                          ? `${c.rotulo} ocupa metade da linha. Passar para largura inteira`
                          : `${c.rotulo} ocupa a linha inteira. Passar para metade`
                      }
                      title={metade ? "Metade — divide a linha" : "Inteira — atravessa a linha"}
                      onClick={() => alternarLargura(c.id)}
                      className={cn(
                        "flex flex-none items-center gap-1.5 rounded-[6px] border px-2 py-1 text-[11px] font-medium",
                        "transition-colors duration-[var(--dur-fast)]",
                        metade
                          ? "border-[var(--purple-200)] bg-[var(--brand-tint)] text-[var(--lateral-ativo-fg)]"
                          : "border-linha-controle text-suave hover:bg-[var(--bg-subtle)]",
                      )}
                    >
                      {metade ? <Columns2 size={13} /> : <Square size={13} />}
                      {metade ? "Metade" : "Inteira"}
                    </button>
                  ) : null}

                  <button
                    type="button"
                    aria-pressed={visivel}
                    aria-label={visivel ? `Ocultar ${c.rotulo}` : `Mostrar ${c.rotulo}`}
                    title={visivel ? "Ocultar do painel" : "Mostrar no painel"}
                    onClick={() => alternar(c.id)}
                    className="flex-none rounded-[6px] p-1.5 text-suave transition-colors hover:bg-[var(--bg-subtle)]"
                  >
                    {visivel ? <Eye size={15} /> : <EyeOff size={15} />}
                  </button>

                  {/* As setas ficam: arrastar não existe no teclado. */}
                  <button
                    type="button"
                    aria-label={`Subir ${c.rotulo}`}
                    disabled={i === 0}
                    onClick={() => mover(i, -1)}
                    className="flex-none rounded-[6px] p-1.5 text-suave transition-colors hover:bg-[var(--bg-subtle)] disabled:opacity-30"
                  >
                    <ChevronUp size={15} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Descer ${c.rotulo}`}
                    disabled={i === lista.length - 1}
                    onClick={() => mover(i, 1)}
                    className="flex-none rounded-[6px] p-1.5 text-suave transition-colors hover:bg-[var(--bg-subtle)] disabled:opacity-30"
                  >
                    <ChevronDown size={15} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>

        <p className="text-[12px] text-sutil">
          <strong className="font-semibold text-suave">Metade</strong> divide a linha — dois
          cards seguidos em metade ficam lado a lado.{" "}
          <strong className="font-semibold text-suave">Inteira</strong> atravessa. Os cards de
          número têm faixa própria de quatro colunas e não usam largura.
        </p>

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button disabled={salvar.isPending} aria-busy={salvar.isPending} onClick={aplicar}>
            {salvar.isPending ? "Salvando…" : "Salvar arranjo"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
