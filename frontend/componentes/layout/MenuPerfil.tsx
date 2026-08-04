"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Keyboard, LogOut, Settings2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/componentes/ui/dropdown-menu";
import { AlternadorTema } from "./AlternadorTema";
import { FolhaDeAtalhos } from "./FolhaDeAtalhos";
import { useSessao } from "@/lib/consultas";
import { sair } from "@/lib/supabase";

/**
 * Menu do perfil, no rodapé da barra lateral — tema, atalhos e sair.
 * A escolha de tema fica aqui porque é preferência de pessoa, não de tela.
 */
export function MenuPerfil({ children }: { children: ReactNode }) {
  const { data: sessao } = useSessao();
  const cliente = useQueryClient();
  const router = useRouter();
  const [atalhosAbertos, setAtalhosAbertos] = useState(false);

  async function encerrar() {
    await sair();
    cliente.clear();
    router.replace("/entrar");
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-[248px]">
          <DropdownMenuLabel className="flex flex-col gap-0.5">
            <span className="text-[13px] font-semibold text-[var(--fg-strong)]">
              {sessao?.usuario.nome}
            </span>
            <span className="text-[12px] font-normal text-sutil">{sessao?.usuario.email}</span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          <div className="flex items-center justify-between px-2 py-1.5">
            <span className="text-[13px] text-suave">Tema</span>
            <AlternadorTema />
          </div>

          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setAtalhosAbertos(true)}>
            <Keyboard size={15} />
            Atalhos de teclado
          </DropdownMenuItem>
          {sessao?.permissoes.configuracoes ? (
            <DropdownMenuItem onSelect={() => router.push("/configuracoes")}>
              <Settings2 size={15} />
              Configurações
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => void encerrar()}>
            <LogOut size={15} />
            Sair
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <FolhaDeAtalhos aberta={atalhosAbertos} aoFechar={() => setAtalhosAbertos(false)} />
    </>
  );
}
