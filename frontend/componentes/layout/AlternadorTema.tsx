"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSalvarPreferencias, useSessao } from "@/lib/consultas";
import type { Tema } from "@/lib/tipos";

/**
 * Alternador claro / escuro / automático (T160, `FR-109`).
 *
 * A escolha é salva em `usuarios.preferencias` pelo backend
 * (`POST /api/sessao/preferencias`) — é por usuário, não por navegador
 * (contracts/plataforma.md §1). O `next-themes` continua guardando a cópia
 * local para o tema já estar certo no primeiro pixel, antes de a sessão
 * carregar; quando a sessão chega, o servidor manda.
 *
 * O vocabulário da API é PT-BR (`claro`/`escuro`/`auto`) e o do `next-themes`
 * é `light`/`dark`/`system`. A tradução mora só aqui.
 */

const PARA_NEXT: Record<Tema, string> = { claro: "light", escuro: "dark", auto: "system" };
const DA_NEXT: Record<string, Tema> = { light: "claro", dark: "escuro", system: "auto" };

const OPCOES: { valor: Tema; rotulo: string; Icone: typeof Sun }[] = [
  { valor: "claro", rotulo: "Claro", Icone: Sun },
  { valor: "escuro", rotulo: "Escuro", Icone: Moon },
  { valor: "auto", rotulo: "Automático", Icone: Monitor },
];

export function AlternadorTema({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const { data: sessao } = useSessao();
  const salvar = useSalvarPreferencias();
  const [montado, setMontado] = useState(false);

  useEffect(() => setMontado(true), []);

  // Quando a sessão chega, o que o servidor guardou vence a cópia local.
  useEffect(() => {
    const doServidor = sessao?.preferencias.tema;
    if (!doServidor) return;
    const alvo = PARA_NEXT[doServidor];
    if (alvo && alvo !== theme) setTheme(alvo);
    // `theme` de propósito fora das dependências: reagir a ele aqui faria a
    // escolha do servidor desfazer a escolha que a pessoa acabou de fazer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessao?.preferencias.tema]);

  const atual: Tema = montado ? (DA_NEXT[theme ?? "system"] ?? "auto") : "auto";

  function escolher(valor: Tema) {
    setTheme(PARA_NEXT[valor]);
    salvar.mutate({ tema: valor });
  }

  return (
    <div
      role="radiogroup"
      aria-label="Tema da interface"
      className={cn(
        "flex items-center gap-[2px] rounded-[6px] border border-linha-suave bg-segmento p-[3px]",
        className,
      )}
    >
      {OPCOES.map(({ valor, rotulo, Icone }) => {
        const ativo = atual === valor;
        return (
          <button
            key={valor}
            type="button"
            role="radio"
            aria-checked={ativo}
            aria-label={rotulo}
            title={rotulo}
            onClick={() => escolher(valor)}
            className={cn(
              "flex size-7 items-center justify-center rounded-[6px] transition-colors",
              ativo
                ? "bg-superficie-cartao text-[var(--brand-hover)] shadow-[var(--sombra-cartao)]"
                : "text-suave hover:text-[var(--fg)]",
            )}
          >
            <Icone size={14} strokeWidth={2} />
          </button>
        );
      })}
    </div>
  );
}
