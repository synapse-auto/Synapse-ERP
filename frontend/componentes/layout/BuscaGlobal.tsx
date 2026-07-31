"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/componentes/ui/command";
import { IconeBusca } from "@/componentes/comum/icones";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { Moeda } from "@/componentes/comum/Moeda";
import { DataBR } from "@/componentes/comum/DataBR";
import { Tecla } from "./FolhaDeAtalhos";
import { useBusca } from "@/lib/consultas";
import { ehMac } from "@/lib/atalhos";
import { DESTINOS_DE_ATALHO } from "@/lib/atalhos";

/**
 * Busca global (T159, `FR-046`).
 *
 * Cobre lançamentos, clientes e categorias pelo `GET /api/busca`, que usa
 * `pg_trgm` — por isso encontra "Estrutural" digitando "estrutual".
 *
 * O termo é debounced em 220 ms (a duração base do design system) e o
 * backend recusa menos de 2 caracteres em vez de varrer a tabela, então
 * nem chamamos abaixo disso.
 */
export function BuscaGlobal({
  aberta,
  aoMudarAbertura,
}: {
  aberta: boolean;
  aoMudarAbertura: (v: boolean) => void;
}) {
  const router = useRouter();
  const [termo, setTermo] = useState("");
  const [adiado, setAdiado] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setAdiado(termo), 220);
    return () => clearTimeout(t);
  }, [termo]);

  const { data, isFetching } = useBusca(adiado);

  const vazio = useMemo(
    () =>
      !data ||
      (data.lancamentos.length === 0 &&
        data.clientes.length === 0 &&
        data.categorias.length === 0),
    [data],
  );

  function ir(rota: string) {
    aoMudarAbertura(false);
    setTermo("");
    router.push(rota);
  }

  return (
    <CommandDialog
      open={aberta}
      onOpenChange={aoMudarAbertura}
      title="Busca global"
      description="Busque lançamentos, clientes e categorias"
      className="top-[18%] translate-y-0"
    >
      {/* `shouldFilter={false}`: quem filtra é o Postgres, por similaridade
          (`pg_trgm`). Deixar o cmdk filtrar por cima esconderia justamente os
          resultados aproximados que a busca existe para achar. */}
      <Command shouldFilter={false}>
      <CommandInput
        placeholder="Buscar lançamento, cliente, categoria…"
        value={termo}
        onValueChange={setTermo}
      />
      <CommandList className="max-h-[420px]">
        {adiado.length < 2 ? (
          <CommandGroup heading="Ir para">
            {DESTINOS_DE_ATALHO.map((d) => (
              <CommandItem key={d.rota} value={d.rotulo} onSelect={() => ir(d.rota)}>
                {d.rotulo}
                <span className="ml-auto flex gap-1">
                  <Tecla>G</Tecla>
                  <Tecla>{d.tecla.toUpperCase()}</Tecla>
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {adiado.length >= 2 && vazio && !isFetching ? (
          <CommandEmpty>
            Nada encontrado para “{adiado}”. A busca cobre descrição de lançamento, nome de
            cliente e nome de categoria.
          </CommandEmpty>
        ) : null}

        {data && data.lancamentos.length > 0 ? (
          <CommandGroup heading="Lançamentos">
            {data.lancamentos.map((l) => (
              <CommandItem
                key={l.id}
                value={`lanc-${l.id}`}
                onSelect={() => ir(`/lancamentos?selecionado=${l.id}`)}
                className="gap-3"
              >
                <span className="min-w-0 flex-1 truncate">{l.descricao}</span>
                <BadgeMundo mundo={l.mundo} />
                <DataBR valor={l.data} formato="curta" className="text-[11.5px] text-sutil" />
                <Moeda valor={l.valor} className="text-[12.5px]" />
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {data && data.clientes.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Clientes">
              {data.clientes.map((c) => (
                <CommandItem
                  key={c.id}
                  value={`cli-${c.id}`}
                  onSelect={() => ir(`/clientes/${c.id}`)}
                  className="gap-3"
                >
                  <span className="min-w-0 flex-1 truncate">{c.nome}</span>
                  {c.empresa ? (
                    <span className="truncate text-[11.5px] text-sutil">{c.empresa}</span>
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}

        {data && data.categorias.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Categorias">
              {data.categorias.map((c) => (
                <CommandItem
                  key={c.id}
                  value={`cat-${c.id}`}
                  onSelect={() => ir(`/lancamentos?categoria_id=${c.id}`)}
                  className="gap-2"
                >
                  <span
                    aria-hidden
                    className="size-[7px] shrink-0 rounded-[2px]"
                    style={{ background: c.cor ?? "var(--fg-subtle)" }}
                  />
                  {c.nome}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}
      </CommandList>
      </Command>
    </CommandDialog>
  );
}

/** O botão de 300px do cabeçalho, com o `⌘K` desenhado, como no mockup. */
export function BotaoBusca({ aoAbrir, className }: { aoAbrir: () => void; className?: string }) {
  const [mac, setMac] = useState(false);
  useEffect(() => setMac(ehMac()), []);

  return (
    <button
      type="button"
      onClick={aoAbrir}
      className={cn(
        "flex h-9 w-[300px] items-center gap-[9px] rounded-[10px] border border-linha-controle",
        "bg-[var(--superficie-lateral)] pr-3 pl-[11px] text-left text-[13px] text-sutil",
        "transition-colors hover:border-[var(--purple-300)] hover:bg-superficie-cartao",
        className,
      )}
    >
      <IconeBusca className="flex-none" />
      <span className="flex-1 truncate">Buscar lançamento, cliente, categoria…</span>
      <span className="rounded-[5px] border border-linha-controle bg-superficie-cartao px-[5px] py-[1px] font-mono text-[10px] text-[var(--ink-300)]">
        {mac ? "⌘K" : "Ctrl K"}
      </span>
    </button>
  );
}
