/**
 * Atalhos de teclado (T151, `FR-110`, `RNF-10`).
 *
 * Os dois atalhos que o mockup mostra na própria interface — `⌘K` na busca e
 * `N` no botão de novo lançamento — são os que a pessoa descobre sem ler
 * documentação. Os outros seguem o que ela já conhece de outros sistemas:
 * `Esc` fecha, `G` seguido de letra navega, `/` foca a busca.
 *
 * Regra que este arquivo garante: **atalho de tecla única nunca dispara
 * enquanto se digita**. Sem isso, escrever "Nota fiscal" na descrição abriria
 * o formulário de novo lançamento no meio da frase.
 */

"use client";

import { useEffect, useRef } from "react";

export interface Atalho {
  /** Tecla como o `KeyboardEvent.key`, minúscula. `"k"`, `"escape"`, `"/"`. */
  tecla: string;
  /** `Ctrl` no Windows/Linux, `⌘` no Mac — tratados como o mesmo atalho. */
  comando?: boolean;
  shift?: boolean;
  /** Prefixo de sequência: `G` seguido da tecla, como no Gmail. */
  sequencia?: "g";
  descricao: string;
  /** Grupo mostrado na folha de atalhos. */
  grupo: "Navegação" | "Ações" | "Tela";
  aoDisparar: (evento: KeyboardEvent) => void;
  /** Deixa o atalho valer mesmo com o foco num campo. Só para `Esc` e `⌘K`. */
  valeDigitando?: boolean;
  desabilitado?: boolean;
}

const TEMPO_DA_SEQUENCIA = 1200;

function estaDigitando(alvo: EventTarget | null): boolean {
  if (!(alvo instanceof HTMLElement)) return false;
  const t = alvo.tagName;
  if (t === "INPUT" || t === "TEXTAREA" || t === "SELECT") return true;
  return alvo.isContentEditable;
}

/**
 * Registra atalhos enquanto o componente estiver montado.
 *
 * Recebe a lista por referência a cada render; guardamos numa `ref` para não
 * reassinar o `keydown` a cada renderização — reassinar perderia a sequência
 * do `G` no meio.
 */
export function useAtalhos(atalhos: Atalho[]): void {
  const ref = useRef(atalhos);
  ref.current = atalhos;

  useEffect(() => {
    let prefixo: string | null = null;
    let tempo: ReturnType<typeof setTimeout> | null = null;

    function limparPrefixo() {
      prefixo = null;
      if (tempo) clearTimeout(tempo);
      tempo = null;
    }

    function aoTeclar(e: KeyboardEvent) {
      const tecla = e.key.toLowerCase();
      const comando = e.metaKey || e.ctrlKey;
      const digitando = estaDigitando(e.target);

      // Prefixo de sequência: "g" sozinho, fora de campo de texto.
      if (!comando && !digitando && tecla === "g" && !prefixo) {
        const temSequencia = ref.current.some((a) => a.sequencia === "g" && !a.desabilitado);
        if (temSequencia) {
          prefixo = "g";
          tempo = setTimeout(limparPrefixo, TEMPO_DA_SEQUENCIA);
          return;
        }
      }

      for (const a of ref.current) {
        if (a.desabilitado) continue;
        if (a.tecla !== tecla) continue;
        if (Boolean(a.comando) !== comando) continue;
        if (Boolean(a.shift) !== e.shiftKey) continue;

        if (a.sequencia) {
          if (prefixo !== a.sequencia) continue;
        } else if (prefixo) {
          continue;
        }

        // Tecla única sem modificador só vale fora de campo de texto.
        if (digitando && !a.valeDigitando && !comando) continue;

        e.preventDefault();
        limparPrefixo();
        a.aoDisparar(e);
        return;
      }

      if (prefixo && tecla !== "g") limparPrefixo();
    }

    window.addEventListener("keydown", aoTeclar);
    return () => {
      window.removeEventListener("keydown", aoTeclar);
      if (tempo) clearTimeout(tempo);
    };
  }, []);
}

/** `true` no Mac — muda `Ctrl` por `⌘` no rótulo mostrado. */
export function ehMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent);
}

/** Rótulo do atalho como se escreve na tela: `⌘K`, `Ctrl+K`, `G` `D`. */
export function rotuloDoAtalho(a: Pick<Atalho, "tecla" | "comando" | "shift" | "sequencia">): string {
  const partes: string[] = [];
  if (a.sequencia) partes.push(a.sequencia.toUpperCase());
  if (a.comando) partes.push(ehMac() ? "⌘" : "Ctrl");
  if (a.shift) partes.push("Shift");
  partes.push(a.tecla === "escape" ? "Esc" : a.tecla.toUpperCase());
  return a.comando && !a.sequencia && ehMac() ? partes.join("") : partes.join(a.sequencia ? " " : "+");
}

/**
 * Os atalhos de navegação, num só lugar para a folha de ajuda (`?`) e o
 * registro não divergirem.
 */
export const DESTINOS_DE_ATALHO: {
  tecla: string;
  /** `1`–`7`, na ordem do menu — é o atalho que a `RNF-10` nomeia. */
  numero: string;
  rota: string;
  rotulo: string;
}[] = [
  { tecla: "d", numero: "1", rota: "/", rotulo: "Dashboard" },
  { tecla: "l", numero: "2", rota: "/lancamentos", rotulo: "Lançamentos" },
  { tecla: "e", numero: "3", rota: "/extrato", rotulo: "Extrato" },
  { tecla: "c", numero: "4", rota: "/categorias", rotulo: "Categorias" },
  { tecla: "i", numero: "5", rota: "/clientes", rotulo: "Clientes" },
  { tecla: "f", numero: "6", rota: "/funcionarios", rotulo: "Funcionários" },
  { tecla: "r", numero: "7", rota: "/relatorios", rotulo: "Relatórios" },
];
