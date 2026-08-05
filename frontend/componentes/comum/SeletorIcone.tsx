"use client";

import { useMemo, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { Input } from "@/componentes/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/componentes/ui/popover";
import {
  QUANTIDADE_DE_ICONES,
  filtraIcones,
  iconeDoCatalogo,
} from "@/componentes/comum/catalogo-icones";
import { cn } from "@/lib/utils";

/**
 * Escolha do ícone da categoria (`FR-072`).
 *
 * Pesquisa antes de escrever (Princípio II) e por que a lista é curada: no
 * cabeçalho de `catalogo-icones.tsx`. Aqui só a casca — `Popover` + `Input` do
 * shadcn, os dois já no projeto.
 *
 * O valor que sai é **o nome Lucide** (`"air-vent"`), que é exatamente o que a
 * API espera em `icone` e o que a coluna guarda. O rótulo PT-BR é só para os
 * olhos e para a busca.
 *
 * A cor da categoria entra no botão e no ícone escolhido: o gestor decide cor e
 * ícone na mesma tela, e ver os dois juntos evita a combinação ilegível.
 */
export function SeletorIcone({
  valor,
  aoMudar,
  cor,
  id,
  desabilitado,
}: {
  valor: string;
  aoMudar: (nome: string) => void;
  /** Cor atual da categoria, para a prévia. */
  cor?: string | null;
  id?: string;
  desabilitado?: boolean;
}) {
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");

  const grupos = useMemo(() => filtraIcones(busca), [busca]);
  const escolhido = iconeDoCatalogo(valor);
  const Escolhido = escolhido.Componente;

  function escolher(nome: string) {
    aoMudar(nome);
    setAberto(false);
    setBusca("");
  }

  return (
    <Popover
      open={aberto}
      onOpenChange={(v) => {
        setAberto(v);
        if (!v) setBusca("");
      }}
    >
      <PopoverTrigger
        id={id}
        type="button"
        disabled={desabilitado}
        aria-label={`Ícone: ${escolhido.rotulo}. Clique para trocar.`}
        className={cn(
          "flex h-9 w-full items-center gap-2 rounded-[8px] border border-linha-controle bg-superficie-cartao px-2.5",
          "font-[family-name:var(--font-body)] text-[13px] text-[var(--fg)]",
          "transition-colors duration-[var(--dur-fast)]",
          "hover:border-[var(--purple-300)] hover:bg-[var(--bg-subtle)]",
          "data-[state=open]:border-[var(--purple-400)] data-[state=open]:bg-superficie-cartao",
          "disabled:cursor-not-allowed disabled:opacity-60",
        )}
      >
        <span
          aria-hidden
          className="flex size-6 flex-none items-center justify-center rounded-[6px]"
          style={{
            background: `color-mix(in srgb, ${cor || "var(--fg-subtle)"} 16%, transparent)`,
            color: cor || "var(--fg-muted)",
          }}
        >
          <Escolhido size={14} strokeWidth={1.9} />
        </span>
        <span className="min-w-0 flex-1 truncate text-left">{escolhido.rotulo}</span>
        <ChevronDown size={14} className="flex-none text-sutil" aria-hidden />
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={6}
        className={cn(
          "w-[320px] gap-2 rounded-[10px] border border-linha-controle bg-superficie-cartao p-2",
          "shadow-[var(--sombra-painel)] ring-0",
        )}
      >
        <div className="relative">
          <Search
            size={14}
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sutil"
          />
          {/* `autoFocus` porque o popover existe para escolher: quem abriu já pode
              digitar "solar" em vez de percorrer 135 ícones com a roda do mouse. */}
          <Input
            autoFocus
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            onKeyDown={(e) => {
              const primeiro = grupos[0]?.itens[0];
              if (e.key === "Enter" && primeiro) {
                e.preventDefault();
                escolher(primeiro.nome);
              }
            }}
            placeholder={`Buscar entre ${QUANTIDADE_DE_ICONES} ícones…`}
            aria-label="Buscar ícone"
            className="h-8 rounded-[6px] pl-8 text-[13px]"
          />
        </div>

        <div className="max-h-[248px] overflow-y-auto [overscroll-behavior:contain]">
          {grupos.length === 0 ? (
            <p className="px-1 py-6 text-center text-[12px] text-sutil">
              Nenhum ícone com “{busca}”.
            </p>
          ) : (
            grupos.map((grupo) => (
              <div key={grupo.rotulo} className="mb-1 last:mb-0">
                <p className="rotulo-seccao px-1 pt-2 pb-1">{grupo.rotulo}</p>
                <div className="grid grid-cols-8 gap-1">
                  {grupo.itens.map((item) => {
                    const Icone = item.Componente;
                    const ativo = item.nome === escolhido.nome;
                    return (
                      <button
                        key={item.nome}
                        type="button"
                        onClick={() => escolher(item.nome)}
                        title={`${item.rotulo} · ${item.nome}`}
                        aria-label={item.rotulo}
                        aria-pressed={ativo}
                        className={cn(
                          "flex size-[34px] items-center justify-center rounded-[6px] border",
                          "transition-colors duration-[var(--dur-fast)]",
                          ativo
                            ? "border-[var(--purple-400)] bg-[var(--brand-tint)] text-[var(--lateral-ativo-fg)]"
                            : "border-transparent text-suave hover:bg-[var(--bg-subtle)] hover:text-forte",
                        )}
                      >
                        <Icone size={17} strokeWidth={1.9} aria-hidden />
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
