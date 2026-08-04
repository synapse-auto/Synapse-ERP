"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/componentes/ui/sheet";
import { BarraLateral } from "./BarraLateral";

/**
 * A mesma barra lateral, em gaveta, abaixo de `md` (`FR-111`, `SC-012`).
 * Fecha sozinha ao navegar — senão o menu ficaria por cima da tela que a
 * pessoa acabou de pedir.
 */
export function BarraLateralMovel() {
  const [aberta, setAberta] = useState(false);
  const caminho = usePathname();

  useEffect(() => setAberta(false), [caminho]);

  return (
    <Sheet open={aberta} onOpenChange={setAberta}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label="Abrir o menu de navegação"
          className="ml-3 flex size-9 flex-none items-center justify-center rounded-[8px] border border-linha-controle bg-superficie-cartao text-[var(--fg-muted)] transition-colors duration-[var(--dur-fast)] hover:bg-[var(--bg-subtle)] hover:text-[var(--ink-600)] md:hidden"
        >
          <Menu size={18} />
        </button>
      </SheetTrigger>
      <SheetContent side="left" className="w-[var(--barra-lateral-largura)] p-0">
        <SheetTitle className="sr-only">Navegação</SheetTitle>
        <BarraLateral className="w-full border-r-0" />
      </SheetContent>
    </Sheet>
  );
}
