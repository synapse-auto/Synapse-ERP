"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/componentes/ui/popover";
import { Input } from "@/componentes/ui/input";
import { Button } from "@/componentes/ui/button";
import { api, mensagemDoErro } from "@/lib/api";
import { chaves, useTags } from "@/lib/consultas";
import type { Tag } from "@/lib/tipos";

/**
 * Escolha de tags, com criação no próprio fluxo.
 *
 * Operador **pode criar** tag (`RN-14`, contracts/cadastros.md §7) — são
 * livres, e criá-las enquanto se lança é o uso esperado. Renomear e excluir
 * é que são de gestor, e ficam na tela de Configurações.
 */
export function SeletorTags({
  selecionadas,
  aoMudar,
}: {
  selecionadas: string[];
  aoMudar: (ids: string[]) => void;
}) {
  const { data } = useTags();
  const cliente = useQueryClient();
  const [nova, setNova] = useState("");

  const criar = useMutation({
    mutationFn: (nome: string) => api.post<Tag>("/api/tags", { corpo: { nome, cor: null } }),
    onSuccess: (tag) => {
      cliente.invalidateQueries({ queryKey: chaves.tags });
      aoMudar([...selecionadas, tag.id]);
      setNova("");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const todas = data?.itens ?? [];
  const escolhidas = todas.filter((t) => selecionadas.includes(t.id));

  function alternar(id: string) {
    aoMudar(selecionadas.includes(id) ? selecionadas.filter((x) => x !== id) : [...selecionadas, id]);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {escolhidas.map((t) => (
        <span
          key={t.id}
          className="inline-flex items-center gap-1.5 rounded-full bg-segmento py-1 pr-1.5 pl-2.5 font-[family-name:var(--font-display)] text-[11px] font-semibold"
          style={{ color: t.cor ?? "var(--fg-muted)" }}
        >
          {t.nome}
          <button type="button" onClick={() => alternar(t.id)} aria-label={`Remover ${t.nome}`}>
            <X size={12} strokeWidth={2.4} />
          </button>
        </span>
      ))}

      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="flex h-7 items-center gap-1 rounded-full border border-dashed border-linha-controle px-2.5 text-[12px] text-suave transition-colors hover:border-[var(--purple-400)] hover:text-[var(--lateral-ativo-fg)]"
          >
            <Plus size={12} />
            Tag
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[280px]">
          <div className="flex flex-col gap-3">
            <div className="flex max-h-[180px] flex-col gap-1 overflow-y-auto">
              {todas.length === 0 ? (
                <p className="text-[12px] text-sutil">Nenhuma tag ainda.</p>
              ) : (
                todas.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => alternar(t.id)}
                    className={cn(
                      "flex items-center gap-2 rounded-[6px] px-2 py-1.5 text-left text-[13px] transition-colors",
                      selecionadas.includes(t.id)
                        ? "bg-[var(--brand-tint-2)] text-[var(--lateral-ativo-fg)]"
                        : "hover:bg-[var(--bg-subtle)]",
                    )}
                  >
                    <span
                      aria-hidden
                      className="size-[7px] rounded-[2px]"
                      style={{ background: t.cor ?? "var(--fg-subtle)" }}
                    />
                    {t.nome}
                  </button>
                ))
              )}
            </div>

            <div className="flex items-center gap-2 border-t border-linha-suave pt-3">
              <Input
                value={nova}
                onChange={(e) => setNova(e.target.value)}
                placeholder="nova tag"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && nova.trim()) {
                    e.preventDefault();
                    criar.mutate(nova.trim());
                  }
                }}
              />
              <Button
                type="button"
                size="sm"
                disabled={!nova.trim() || criar.isPending}
                onClick={() => criar.mutate(nova.trim())}
              >
                Criar
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
