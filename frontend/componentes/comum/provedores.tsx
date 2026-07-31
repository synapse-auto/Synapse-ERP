"use client";

import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/componentes/ui/tooltip";
import { Toaster } from "@/componentes/ui/sonner";
import { ErroApi, registrarPerdaDeSessao } from "@/lib/api";

/**
 * Provedores da aplicação inteira (T145).
 *
 * `next-themes` marca **os dois** atributos: a classe `.dark` que o Tailwind e
 * o shadcn esperam, e o `data-theme` que research.md D-12 especifica. Manter
 * só um obrigaria metade do CSS a saber qual convenção vale.
 */
export function Provedores({ children }: { children: React.ReactNode }) {
  const [cliente] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Dado financeiro muda pouco dentro de uma sessão de trabalho, mas
            // a rotina diária pode alterá-lo por baixo (contracts/plataforma.md
            // §6, "chamada implícita"). 30 s é curto o bastante para a tela não
            // mentir e longo o bastante para trocar de aba não custar rede.
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            refetchOnWindowFocus: false,
            retry: (tentativas, erro) => {
              // 4xx é resposta, não falha: repetir não muda nada e atrasa a
              // mensagem que o backend já mandou pronta.
              if (erro instanceof ErroApi && erro.status >= 400 && erro.status < 500) return false;
              return tentativas < 2;
            },
          },
          mutations: { retry: false },
        },
      }),
  );

  useEffect(() => {
    // Um `401` em qualquer chamada joga para a tela de entrar, guardando de
    // onde veio para voltar depois do login.
    registrarPerdaDeSessao(() => {
      if (typeof window === "undefined") return;
      if (window.location.pathname.startsWith("/entrar")) return;
      const destino = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.assign(`/entrar?destino=${destino}`);
    });
    return () => registrarPerdaDeSessao(null);
  }, []);

  return (
    <QueryClientProvider client={cliente}>
      <ThemeProvider
        attribute={["class", "data-theme"]}
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <TooltipProvider delayDuration={220}>
          {children}
          <Toaster
            position="bottom-right"
            richColors
            closeButton
            toastOptions={{ style: { fontFamily: "var(--font-body)" } }}
          />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
