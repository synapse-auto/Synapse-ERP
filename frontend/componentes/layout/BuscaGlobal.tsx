"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { IconeBusca } from "@/componentes/comum/icones";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { Moeda } from "@/componentes/comum/Moeda";
import { DataBR } from "@/componentes/comum/DataBR";
import { useBusca } from "@/lib/consultas";
import { useEstadoUi } from "@/lib/estado-global";
import { ehMac, DESTINOS_DE_ATALHO } from "@/lib/atalhos";

/**
 * Busca global (T159, `FR-046`; refeita em T213).
 *
 * **Não é mais uma janela.** Até o Boss 3 a busca era um `CommandDialog`: o
 * clique no campo escurecia a tela e abria um painel no meio dela. Virou o que
 * o dono do projeto pediu — um campo comum no cabeçalho que mostra o resultado
 * num dropdown embaixo enquanto se digita e leva direto para o registro.
 *
 * Padrão de acessibilidade: `combobox` + `listbox`. O foco **nunca sai do
 * campo**; `↑`/`↓` movem a opção ativa por `aria-activedescendant`, `Enter`
 * navega, `Esc` limpa (e, já vazio, tira o foco). Cada opção é um `<Link>` de
 * verdade, então `Ctrl`/`⌘`+clique e clique do meio abrem em outra aba e o
 * endereço aparece na barra de status do navegador antes do clique.
 *
 * Cobre lançamentos, clientes, **funcionários** (T212) e categorias pelo
 * `GET /api/busca`, que usa `pg_trgm` — por isso encontra "Estrutural"
 * digitando "estrutual".
 *
 * O termo é adiado em 220 ms (a duração base do design system) e o backend
 * recusa menos de 2 caracteres em vez de varrer a tabela, então nem chamamos
 * abaixo disso.
 */

const MINIMO = 2;

interface Item {
  chave: string;
  grupo: string;
  rota: string;
  /** Lido pelo leitor de tela ao chegar na opção. */
  rotulo: string;
  conteudo: ReactNode;
}

export function BuscaGlobal({ className }: { className?: string }) {
  const router = useRouter();
  const pedidoDeFoco = useEstadoUi((e) => e.pedidoDeFocoNaBusca);

  const [termo, setTermo] = useState("");
  const [adiado, setAdiado] = useState("");
  const [aberta, setAberta] = useState(false);
  const [ativo, setAtivo] = useState(0);
  const [mac, setMac] = useState(false);

  const campo = useRef<HTMLInputElement>(null);
  const painel = useRef<HTMLDivElement>(null);

  useEffect(() => setMac(ehMac()), []);

  useEffect(() => {
    const t = setTimeout(() => setAdiado(termo), 220);
    return () => clearTimeout(t);
  }, [termo]);

  // `⌘K` e `/` não abrem nada: focam o campo que já está na tela.
  useEffect(() => {
    if (pedidoDeFoco === 0) return;
    campo.current?.focus();
    campo.current?.select();
    setAberta(true);
  }, [pedidoDeFoco]);

  const { data, isFetching } = useBusca(adiado);

  const buscando = adiado.length >= MINIMO;

  const itens = useMemo<Item[]>(() => {
    // Campo vazio (ou quase): o dropdown vira o atalho de navegação. Continua
    // sendo busca — só que do nome da tela, que é o que a pessoa procura
    // quando ainda não digitou nada.
    if (!buscando) {
      const filtro = termo.trim().toLowerCase();
      return DESTINOS_DE_ATALHO.filter(
        (d) => filtro.length === 0 || d.rotulo.toLowerCase().includes(filtro),
      ).map((d) => ({
        chave: `ir-${d.rota}`,
        grupo: "Ir para",
        rota: d.rota,
        rotulo: `Ir para ${d.rotulo}`,
        conteudo: (
          <>
            <span className="min-w-0 flex-1 truncate">{d.rotulo}</span>
            <Tecla>{d.numero}</Tecla>
          </>
        ),
      }));
    }

    if (!data) return [];

    const lista: Item[] = [];

    for (const l of data.lancamentos) {
      lista.push({
        chave: `lanc-${l.id}`,
        grupo: "Lançamentos",
        rota: `/lancamentos?selecionado=${l.id}`,
        rotulo: `Lançamento ${l.descricao}`,
        conteudo: (
          <>
            <span className="min-w-0 flex-1 truncate">{l.descricao}</span>
            <BadgeMundo mundo={l.mundo} />
            <DataBR valor={l.data} formato="curta" className="text-[12px] text-sutil" />
            <Moeda valor={l.valor} className="text-[13px]" />
          </>
        ),
      });
    }

    for (const c of data.clientes) {
      lista.push({
        chave: `cli-${c.id}`,
        grupo: "Clientes",
        rota: `/clientes/${c.id}`,
        rotulo: `Cliente ${c.nome}`,
        conteudo: (
          <>
            <span className="min-w-0 flex-1 truncate">{c.nome}</span>
            {c.empresa ? (
              <span className="max-w-[45%] truncate text-[12px] text-sutil">{c.empresa}</span>
            ) : null}
          </>
        ),
      });
    }

    for (const f of data.funcionarios ?? []) {
      lista.push({
        chave: `fun-${f.id}`,
        grupo: "Funcionários",
        rota: `/funcionarios/${f.id}`,
        rotulo: `Funcionário ${f.nome}`,
        conteudo: (
          <>
            <span className="min-w-0 flex-1 truncate">{f.nome}</span>
            {f.funcao ? (
              <span className="max-w-[40%] truncate text-[12px] text-sutil">{f.funcao}</span>
            ) : null}
            <BadgeMundo mundo={f.mundo} />
          </>
        ),
      });
    }

    for (const c of data.categorias) {
      lista.push({
        chave: `cat-${c.id}`,
        grupo: "Categorias",
        // Categoria não tem tela própria: o destino útil é a lista já filtrada.
        rota: `/lancamentos?categoria_id=${c.id}`,
        rotulo: `Lançamentos da categoria ${c.nome}`,
        conteudo: (
          <>
            <span
              aria-hidden="true"
              className="size-[7px] shrink-0 rounded-[2px]"
              style={{ background: c.cor ?? "var(--fg-subtle)" }}
            />
            <span className="min-w-0 flex-1 truncate">{c.nome}</span>
            <span className="text-[12px] text-sutil">ver lançamentos</span>
          </>
        ),
      });
    }

    return lista;
  }, [buscando, data, termo]);

  // Resultado novo recoloca a seleção na primeira linha — senão a seta continua
  // apontando para um índice que já virou outro registro.
  useEffect(() => setAtivo(0), [adiado, itens.length]);

  const vazio = buscando && !isFetching && itens.length === 0;
  const mostrando = aberta && (itens.length > 0 || vazio || (buscando && isFetching));

  function irPara(item: Item | undefined) {
    if (!item) return;
    setAberta(false);
    setTermo("");
    setAdiado("");
    campo.current?.blur();
    router.push(item.rota);
  }

  function aoTeclar(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAberta(true);
      setAtivo((i) => (itens.length === 0 ? 0 : (i + 1) % itens.length));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((i) => (itens.length === 0 ? 0 : (i - 1 + itens.length) % itens.length));
      return;
    }
    if (e.key === "Home" && mostrando) {
      e.preventDefault();
      setAtivo(0);
      return;
    }
    if (e.key === "End" && mostrando) {
      e.preventDefault();
      setAtivo(Math.max(0, itens.length - 1));
      return;
    }
    if (e.key === "Enter") {
      if (!mostrando || itens.length === 0) return;
      e.preventDefault();
      irPara(itens[ativo]);
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      if (termo.length > 0) {
        setTermo("");
        setAdiado("");
        setAberta(false);
      } else {
        campo.current?.blur();
      }
    }
  }

  // A opção ativa acompanha a seta mesmo quando sai da área visível.
  useEffect(() => {
    if (!mostrando) return;
    painel.current
      ?.querySelector<HTMLElement>('[data-ativo="sim"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [ativo, mostrando]);

  let grupoAnterior = "";

  return (
    <div
      className={cn("relative", className)}
      onBlur={(e) => {
        // Só fecha se o foco saiu do conjunto campo + painel.
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setAberta(false);
      }}
    >
      <div
        className={cn(
          "flex h-9 items-center gap-[9px] rounded-[8px] border border-linha-controle",
          "bg-[var(--superficie-lateral)] pr-2 pl-[11px]",
          "transition-colors duration-[var(--dur-fast)]",
          "hover:border-[var(--purple-300)]",
          "focus-within:border-[var(--purple-400)] focus-within:bg-superficie-cartao",
        )}
      >
        <IconeBusca className="flex-none text-sutil" />
        <input
          ref={campo}
          type="search"
          name="busca-global"
          role="combobox"
          aria-expanded={mostrando}
          aria-controls="busca-global-lista"
          aria-autocomplete="list"
          aria-activedescendant={
            mostrando && itens.length > 0 ? `busca-global-opcao-${ativo}` : undefined
          }
          aria-label="Buscar lançamento, cliente, funcionário ou categoria"
          autoComplete="off"
          spellCheck={false}
          enterKeyHint="search"
          placeholder="Buscar lançamento, cliente, funcionário…"
          value={termo}
          onChange={(e) => {
            setTermo(e.target.value);
            setAberta(true);
          }}
          onFocus={() => setAberta(true)}
          onKeyDown={aoTeclar}
          className={cn(
            "min-w-0 flex-1 border-0 bg-transparent text-[13px] text-[var(--fg)]",
            "outline-none placeholder:text-sutil",
            // O `×` nativo do `type=search` no Chrome não segue o tema; some.
            "[&::-webkit-search-cancel-button]:hidden",
          )}
        />
        {termo.length > 0 ? (
          <button
            type="button"
            aria-label="Limpar a busca"
            onClick={() => {
              setTermo("");
              setAdiado("");
              campo.current?.focus();
            }}
            className="flex size-5 flex-none items-center justify-center rounded-[6px] text-sutil transition-colors hover:bg-[var(--bg-muted)] hover:text-forte"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M5 5l14 14M19 5 5 19"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
              />
            </svg>
          </button>
        ) : (
          <span
            aria-hidden="true"
            className="flex-none rounded-[4px] border border-linha-controle bg-superficie-cartao px-[5px] py-[1px] font-mono text-[10px] text-[var(--ink-300)]"
          >
            {mac ? "⌘K" : "Ctrl K"}
          </span>
        )}
      </div>

      {/* Contagem falada por leitor de tela, sem depender de enxergar o dropdown. */}
      <span aria-live="polite" className="sr-only">
        {buscando
          ? isFetching
            ? "Buscando…"
            : `${itens.length} ${itens.length === 1 ? "resultado" : "resultados"} para ${adiado}`
          : ""}
      </span>

      {mostrando ? (
        <div
          ref={painel}
          id="busca-global-lista"
          role="listbox"
          aria-label="Resultados da busca"
          className={cn(
            // Nunca mais largo que a tela: no celular o campo tem ~200px e um
            // `min-w` fixo empurraria o painel para fora da viewport.
            "absolute top-[calc(100%+6px)] left-0 z-50 max-h-[420px] overflow-y-auto",
            "w-[max(100%,min(420px,calc(100vw-28px)))]",
            "animate-surgir rounded-[10px] border border-linha-controle bg-superficie-cartao p-1",
            "shadow-[var(--sombra-painel)] [overscroll-behavior:contain]",
          )}
        >
          {vazio ? (
            <p className="px-3 py-6 text-center text-[12px] leading-relaxed text-suave">
              Nada encontrado para <strong className="text-forte">“{adiado}”</strong>.
              <br />A busca cobre descrição de lançamento, nome de cliente, nome e função de
              funcionário e nome de categoria.
            </p>
          ) : itens.length === 0 && isFetching ? (
            <p className="px-3 py-6 text-center text-[12px] text-sutil">Buscando…</p>
          ) : (
            itens.map((item, i) => {
              const cabecalho = item.grupo !== grupoAnterior ? item.grupo : null;
              grupoAnterior = item.grupo;
              return (
                <div key={item.chave}>
                  {cabecalho ? (
                    <div className="rotulo-seccao px-[9px] pt-[9px] pb-[5px]">{cabecalho}</div>
                  ) : null}
                  <Link
                    href={item.rota}
                    id={`busca-global-opcao-${i}`}
                    role="option"
                    aria-selected={i === ativo}
                    aria-label={item.rotulo}
                    data-ativo={i === ativo ? "sim" : undefined}
                    tabIndex={-1}
                    onMouseMove={() => setAtivo(i)}
                    // Sem isto o clique tira o foco do campo, o `onBlur` fecha o
                    // painel e o `onClick` nunca chega a acontecer. Não atrapalha
                    // `⌘`/`Ctrl`+clique: `preventDefault` no `mousedown` só
                    // impede a troca de foco e a seleção de texto.
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={(e) => {
                      // Deixa `⌘`/`Ctrl`/`Shift` abrirem em outra aba, como link normal.
                      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
                      e.preventDefault();
                      irPara(item);
                    }}
                    className={cn(
                      "flex items-center gap-3 rounded-[6px] px-[9px] py-[7px] text-[13px] no-underline",
                      "text-[var(--fg)] transition-colors duration-[var(--dur-fast)]",
                      i === ativo
                        ? "bg-[var(--brand-tint)] text-forte"
                        : "hover:bg-[var(--bg-subtle)]",
                    )}
                  >
                    {item.conteudo}
                  </Link>
                </div>
              );
            })
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Tecla desenhada — mesmo desenho da folha de atalhos. */
function Tecla({ children }: { children: ReactNode }) {
  return (
    <kbd className="flex-none rounded-[4px] border border-linha-controle bg-[var(--bg-subtle)] px-[5px] py-[1px] font-mono text-[10px] text-sutil">
      {children}
    </kbd>
  );
}
