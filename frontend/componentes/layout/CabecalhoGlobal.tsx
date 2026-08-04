"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { SeletorMundo } from "./SeletorMundo";
import { SeletorPeriodo } from "./SeletorPeriodo";
import { SinoNotificacoes } from "./SinoNotificacoes";
import { BotaoBusca, BuscaGlobal } from "./BuscaGlobal";
import { FolhaDeAtalhos } from "./FolhaDeAtalhos";
import { IconeMais } from "@/componentes/comum/icones";
import { useEstadoUi } from "@/lib/estado-global";
import { DESTINOS_DE_ATALHO, useAtalhos } from "@/lib/atalhos";

/**
 * Cabeçalho global — 64px (T157).
 *
 * Ordem do mockup: busca (300px), seletor de mundo, divisor, espaço,
 * seletor de período, divisor, sino, "Novo lançamento".
 *
 * É também onde os atalhos globais vivem (`FR-110`), porque é o componente
 * que existe em toda tela de dentro da aplicação. `⌘K` e `Esc` valem mesmo
 * com o foco num campo; `N`, `/`, `?` e as sequências `G`+letra não disparam
 * enquanto se digita — senão escrever "Notion" abriria o formulário.
 */
export function CabecalhoGlobal({ className }: { className?: string }) {
  const router = useRouter();
  const buscaAberta = useEstadoUi((e) => e.buscaAberta);
  const definirBuscaAberta = useEstadoUi((e) => e.definirBuscaAberta);
  const abrirNovoLancamento = useEstadoUi((e) => e.abrirNovoLancamento);
  const [atalhosAbertos, setAtalhosAbertos] = useState(false);

  useAtalhos([
    {
      tecla: "k",
      comando: true,
      valeDigitando: true,
      grupo: "Ações",
      descricao: "Busca global",
      aoDisparar: () => definirBuscaAberta(true),
    },
    {
      tecla: "n",
      grupo: "Ações",
      descricao: "Novo lançamento",
      aoDisparar: () => abrirNovoLancamento(),
    },
    {
      tecla: "/",
      grupo: "Ações",
      descricao: "Focar a busca da tela",
      aoDisparar: () => {
        const campo = document.querySelector<HTMLInputElement>("[data-busca-da-tela]");
        if (campo) campo.focus();
        else definirBuscaAberta(true);
      },
    },
    {
      tecla: "?",
      shift: true,
      grupo: "Tela",
      descricao: "Folha de atalhos",
      aoDisparar: () => setAtalhosAbertos(true),
    },
    ...DESTINOS_DE_ATALHO.map((d) => ({
      tecla: d.tecla,
      sequencia: "g" as const,
      grupo: "Navegação" as const,
      descricao: `Ir para ${d.rotulo}`,
      aoDisparar: () => router.push(d.rota),
    })),
    // `1`–`7` na ordem do menu: é o atalho que a `RNF-10` nomeia por escrito.
    // As sequências `G`+letra continuam valendo — quem já decorou uma não perde
    // nada, e o número é o que está no documento-mestre.
    ...DESTINOS_DE_ATALHO.map((d) => ({
      tecla: d.numero,
      grupo: "Navegação" as const,
      descricao: `Ir para ${d.rotulo}`,
      aoDisparar: () => router.push(d.rota),
    })),
  ]);

  return (
    <>
      <header
        className={cn(
          "flex h-[var(--cabecalho-altura)] flex-none items-center gap-4 px-[26px]",
          "border-b border-linha-chrome bg-superficie-cartao",
          className,
        )}
      >
        <BotaoBusca aoAbrir={() => definirBuscaAberta(true)} className="hidden lg:flex" />

        <SeletorMundo className="hidden md:flex" />

        <div aria-hidden className="hidden h-[26px] w-px bg-linha-suave md:block" />

        <div className="flex-1" />

        <SeletorPeriodo className="hidden xl:flex" />

        <div aria-hidden className="hidden h-[26px] w-px bg-linha-suave xl:block" />

        <SinoNotificacoes />

        <button
          type="button"
          onClick={() => abrirNovoLancamento()}
          className={cn(
            "flex h-9 items-center gap-[7px] rounded-[10px] px-[15px]",
            "bg-[var(--brand)] text-[var(--fg-onbrand)] shadow-[var(--sombra-acao)]",
            "font-[family-name:var(--font-display)] text-[13.5px] font-bold tracking-[-0.01em]",
            "transition-colors hover:bg-[var(--brand-hover)]",
          )}
        >
          <IconeMais />
          <span className="hidden sm:inline">Novo lançamento</span>
          <span
            aria-hidden
            className="ml-[2px] hidden rounded-[4px] border border-white/35 px-1 font-mono text-[10px] opacity-65 sm:inline"
          >
            N
          </span>
        </button>
      </header>

      <BuscaGlobal aberta={buscaAberta} aoMudarAbertura={definirBuscaAberta} />
      <FolhaDeAtalhos aberta={atalhosAbertos} aoFechar={() => setAtalhosAbertos(false)} />
    </>
  );
}
