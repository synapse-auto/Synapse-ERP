"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/componentes/ui/dialog";
import { DESTINOS_DE_ATALHO, ehMac } from "@/lib/atalhos";

/** Uma tecla desenhada como tecla — o mesmo `kbd` do mockup. */
export function Tecla({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex min-w-[20px] items-center justify-center rounded-[4px] border border-linha-controle bg-superficie-cartao px-[5px] py-[1px] font-mono text-[10px] text-[var(--fg-muted)]">
      {children}
    </kbd>
  );
}

/**
 * Folha de atalhos (`FR-110`). Abre com `?`.
 *
 * A lista de navegação vem de `DESTINOS_DE_ATALHO`, o mesmo array que o
 * registro usa — assim a ajuda não pode divergir do que o teclado faz.
 */
export function FolhaDeAtalhos({ aberta, aoFechar }: { aberta: boolean; aoFechar: () => void }) {
  const cmd = ehMac() ? "⌘" : "Ctrl";

  const acoes = [
    { teclas: ["N"], descricao: "Novo lançamento" },
    { teclas: [cmd, "K"], descricao: "Busca global" },
    { teclas: ["/"], descricao: "Focar a busca da tela" },
    { teclas: ["Esc"], descricao: "Fechar painel, modal ou seleção" },
    { teclas: ["?"], descricao: "Esta folha" },
  ];

  return (
    <Dialog open={aberta} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Atalhos de teclado</DialogTitle>
          <DialogDescription>
            Atalhos de tecla única não disparam enquanto você digita em um campo.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 sm:grid-cols-2">
          <section>
            <h3 className="rotulo-seccao mb-2">Ações</h3>
            <ul className="flex flex-col gap-1.5">
              {acoes.map((a) => (
                <li key={a.descricao} className="flex items-center justify-between gap-3">
                  <span className="text-[13px] text-suave">{a.descricao}</span>
                  <span className="flex gap-1">
                    {a.teclas.map((t) => (
                      <Tecla key={t}>{t}</Tecla>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="rotulo-seccao mb-2">Navegação</h3>
            <ul className="flex flex-col gap-1.5">
              {DESTINOS_DE_ATALHO.map((d) => (
                <li key={d.rota} className="flex items-center justify-between gap-3">
                  <span className="text-[13px] text-suave">{d.rotulo}</span>
                  <span className="flex items-center gap-1">
                    <Tecla>{d.numero}</Tecla>
                    <span className="text-[10px] text-sutil">ou</span>
                    <Tecla>G</Tecla>
                    <Tecla>{d.tecla.toUpperCase()}</Tecla>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
