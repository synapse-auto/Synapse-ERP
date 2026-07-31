"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, SVGProps } from "react";
import { cn } from "@/lib/utils";
import { iniciais } from "@/lib/formato";
import { useSessao } from "@/lib/consultas";
import {
  IconeCategorias,
  IconeClientes,
  IconeConfiguracoes,
  IconeDashboard,
  IconeExtrato,
  IconeFuncionarios,
  IconeLancamentos,
  IconeRelatorios,
  MarcaSynapse,
} from "@/componentes/comum/icones";
import { MenuPerfil } from "./MenuPerfil";

/**
 * Barra lateral — 246px (T156, `FR-107`).
 *
 * Medidas lidas do `<aside>` de `Synapse ERP Financeiro.dc.html`: largura
 * 246px, cabeçalho de 64px alinhado ao cabeçalho global, itens de 9px/11px
 * com raio 9px, item ativo em `#EDE6FD`/`#4F3299`, dois grupos ("Menu" e
 * "Gestão") e o rodapé com Configurações e perfil — o padrão do claude.ai
 * que research.md D-13 registra como referência.
 *
 * As sete abas de `FR-107` são as sete entradas dos dois grupos.
 * Configurações fica no rodapé e **some para operador** — mas esconder o menu
 * não autoriza nada: quem garante é o `403` do backend (`SC-010`).
 */

interface Aba {
  rota: string;
  rotulo: string;
  Icone: ComponentType<SVGProps<SVGSVGElement> & { tamanho?: number }>;
}

const GRUPO_MENU: Aba[] = [
  { rota: "/", rotulo: "Dashboard", Icone: IconeDashboard },
  { rota: "/lancamentos", rotulo: "Lançamentos", Icone: IconeLancamentos },
  { rota: "/extrato", rotulo: "Extrato", Icone: IconeExtrato },
  { rota: "/categorias", rotulo: "Categorias", Icone: IconeCategorias },
];

const GRUPO_GESTAO: Aba[] = [
  { rota: "/clientes", rotulo: "Clientes", Icone: IconeClientes },
  { rota: "/funcionarios", rotulo: "Funcionários", Icone: IconeFuncionarios },
  { rota: "/relatorios", rotulo: "Relatórios", Icone: IconeRelatorios },
];

function ehAtiva(caminho: string, rota: string): boolean {
  if (rota === "/") return caminho === "/";
  return caminho === rota || caminho.startsWith(`${rota}/`);
}

function ItemDeMenu({ aba, ativa }: { aba: Aba; ativa: boolean }) {
  const { Icone } = aba;
  return (
    <Link
      href={aba.rota}
      aria-current={ativa ? "page" : undefined}
      className={cn(
        "flex w-full items-center gap-[10px] rounded-[9px] px-[11px] py-[9px] text-left",
        "font-[family-name:var(--font-display)] text-[13.5px] tracking-[-0.01em]",
        "transition-colors duration-[var(--dur-fast)] ease-[var(--ease-out)]",
        ativa
          ? "bg-lateral-ativo font-bold text-lateral-ativo-fg"
          : "font-medium text-[var(--ink-600)] hover:bg-lateral-hover hover:text-[var(--lateral-hover-fg)] dark:text-[var(--fg-muted)]",
      )}
    >
      <Icone tamanho={17} className={cn("shrink-0", !ativa && "opacity-75")} />
      {aba.rotulo}
    </Link>
  );
}

function RotuloGrupo({ children, primeiro = false }: { children: string; primeiro?: boolean }) {
  return (
    <div
      className={cn(
        "font-[family-name:var(--font-display)] text-[10px] font-bold tracking-[0.11em] uppercase",
        "px-[11px] pb-[7px] text-[var(--ink-300)] dark:text-[var(--fg-subtle)]",
        primeiro ? "pt-0" : "pt-[18px]",
      )}
    >
      {children}
    </div>
  );
}

export function BarraLateral({ className }: { className?: string }) {
  const caminho = usePathname();
  const { data: sessao } = useSessao();
  const podeVerConfiguracoes = sessao?.permissoes.configuracoes ?? false;

  return (
    <aside
      className={cn(
        "flex h-dvh w-[var(--barra-lateral-largura)] flex-none flex-col",
        "border-r border-linha-chrome bg-superficie-lateral",
        className,
      )}
    >
      <div className="flex h-[var(--cabecalho-altura)] flex-none items-center gap-[10px] border-b border-linha-suave px-[18px]">
        <MarcaSynapse tamanho={31} idGradiente="marca-lateral" className="block flex-none rounded-[7px]" />
        <div className="flex min-w-0 flex-col leading-[1.15]">
          <span className="font-[family-name:var(--font-display)] text-[14.5px] font-bold tracking-[-0.02em] text-forte">
            Synapse ERP
          </span>
          <span className="text-[10.5px] tracking-[0.03em] text-sutil">Financeiro</span>
        </div>
      </div>

      <nav
        aria-label="Navegação principal"
        className="flex flex-1 flex-col gap-[3px] overflow-y-auto px-3 pt-4 pb-2"
      >
        <RotuloGrupo primeiro>Menu</RotuloGrupo>
        {GRUPO_MENU.map((aba) => (
          <ItemDeMenu key={aba.rota} aba={aba} ativa={ehAtiva(caminho, aba.rota)} />
        ))}

        <RotuloGrupo>Gestão</RotuloGrupo>
        {GRUPO_GESTAO.map((aba) => (
          <ItemDeMenu key={aba.rota} aba={aba} ativa={ehAtiva(caminho, aba.rota)} />
        ))}
      </nav>

      <div className="flex flex-none flex-col gap-[3px] border-t border-linha-suave px-3 pt-[10px] pb-3">
        {podeVerConfiguracoes ? (
          <ItemDeMenu
            aba={{ rota: "/configuracoes", rotulo: "Configurações", Icone: IconeConfiguracoes }}
            ativa={ehAtiva(caminho, "/configuracoes")}
          />
        ) : null}

        <MenuPerfil>
          <button
            type="button"
            className="mt-[2px] flex w-full items-center gap-[10px] rounded-[9px] px-[9px] py-2 text-left transition-colors hover:bg-lateral-hover"
          >
            <span
              className="flex size-7 flex-none items-center justify-center rounded-[8px] font-[family-name:var(--font-display)] text-[11.5px] font-extrabold text-[#2E1A66]"
              style={{ background: "linear-gradient(135deg,#DCCFFB,#A78BFA)" }}
            >
              {iniciais(sessao?.usuario.nome)}
            </span>
            <span className="flex min-w-0 flex-col leading-[1.25]">
              <span className="truncate font-[family-name:var(--font-display)] text-[12.5px] font-semibold text-[var(--fg)]">
                {sessao?.usuario.nome ?? "Carregando…"}
              </span>
              <span className="text-[10.5px] text-sutil">
                {sessao?.usuario.papel === "gestor"
                  ? "Gestor"
                  : sessao?.usuario.papel === "operador"
                    ? "Operador"
                    : " "}
              </span>
            </span>
          </button>
        </MenuPerfil>
      </div>
    </aside>
  );
}
