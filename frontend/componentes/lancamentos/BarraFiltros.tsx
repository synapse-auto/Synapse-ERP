"use client";

import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { IconeBusca } from "@/componentes/comum/icones";
import { PontoMundo, ROTULO_MUNDO } from "@/componentes/comum/BadgeMundo";
import { rotuloDoStatus } from "@/componentes/comum/BadgeStatus";
import { Popover, PopoverContent, PopoverTrigger } from "@/componentes/ui/popover";
import { Input } from "@/componentes/ui/input";
import { Label } from "@/componentes/ui/label";
import { Checkbox } from "@/componentes/ui/checkbox";
import { useCategorias, useCentrosCusto, useServicos, useTags } from "@/lib/consultas";
import { useEstadoGlobal } from "@/lib/estado-global";
import { dinheiro } from "@/lib/formato";
import { FILTROS_VAZIOS, quantidadeAtiva, type FiltrosLancamento } from "./filtros";
import type { ResumoFiltrado, StatusLancamento } from "@/lib/tipos";

/**
 * Barra de filtros da lista (T163, `FR-037`–`FR-039`).
 *
 * Três coisas que a spec cobra e que estão aqui:
 * - filtros **combináveis** — todos valem ao mesmo tempo;
 * - cada marcador ativo é **removível sozinho**, mais um "limpar tudo";
 * - contador e **somas do conjunto filtrado** ao lado, vindos de
 *   `resumo_filtrado` (o servidor soma; a tela não recalcula, senão a soma da
 *   página divergiria da soma do filtro).
 */

const SELETOR =
  "h-[34px] rounded-[6px] border border-linha-controle bg-superficie-cartao pr-8 pl-[11px] text-[13px] text-[var(--ink-700)] dark:text-[var(--fg)] outline-none cursor-pointer";

const STATUS: StatusLancamento[] = [
  "efetivado",
  "programado",
  "pendente",
  "atrasado",
  "cancelado",
];

interface Marcador {
  chave: string;
  rotulo: string;
  limpar: () => void;
}

export function BarraFiltros({
  filtros,
  aoMudar,
  resumo,
  className,
}: {
  filtros: FiltrosLancamento;
  aoMudar: (parcial: Partial<FiltrosLancamento>) => void;
  resumo?: ResumoFiltrado | null;
  className?: string;
}) {
  const mundoGlobal = useEstadoGlobal((e) => e.mundo);
  const { data: categorias } = useCategorias();
  const { data: servicos } = useServicos();
  const { data: centros } = useCentrosCusto();
  const { data: tags } = useTags();

  const [buscaLocal, setBuscaLocal] = useState(filtros.busca);
  useEffect(() => setBuscaLocal(filtros.busca), [filtros.busca]);
  useEffect(() => {
    const t = setTimeout(() => {
      if (buscaLocal !== filtros.busca) aoMudar({ busca: buscaLocal, pagina: 1 });
    }, 260);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaLocal]);

  const catPorId = new Map((categorias?.itens ?? []).map((c) => [c.id, c]));
  const svcPorId = new Map((servicos?.itens ?? []).map((s) => [s.id, s]));
  const ccPorId = new Map((centros?.itens ?? []).map((c) => [c.id, c]));
  const tagPorId = new Map((tags?.itens ?? []).map((t) => [t.id, t]));

  const marcadores: Marcador[] = [];
  if (filtros.mundoDaLista)
    marcadores.push({
      chave: "mundo",
      rotulo: `Mundo: ${ROTULO_MUNDO[filtros.mundoDaLista]}`,
      limpar: () => aoMudar({ mundoDaLista: "", pagina: 1 }),
    });
  if (filtros.tipo)
    marcadores.push({
      chave: "tipo",
      rotulo: `Tipo: ${filtros.tipo === "receita" ? "Receita" : "Despesa"}`,
      limpar: () => aoMudar({ tipo: "", pagina: 1 }),
    });
  for (const s of filtros.status)
    marcadores.push({
      chave: `status-${s}`,
      rotulo: `Status: ${rotuloDoStatus(s)}`,
      limpar: () => aoMudar({ status: filtros.status.filter((x) => x !== s), pagina: 1 }),
    });
  for (const id of filtros.categoria_id)
    marcadores.push({
      chave: `cat-${id}`,
      rotulo: `Categoria: ${catPorId.get(id)?.nome ?? "…"}`,
      limpar: () => aoMudar({ categoria_id: filtros.categoria_id.filter((x) => x !== id), pagina: 1 }),
    });
  for (const id of filtros.servico_id)
    marcadores.push({
      chave: `svc-${id}`,
      rotulo: `Serviço: ${svcPorId.get(id)?.nome ?? "…"}`,
      limpar: () => aoMudar({ servico_id: filtros.servico_id.filter((x) => x !== id), pagina: 1 }),
    });
  for (const id of filtros.centro_custo_id)
    marcadores.push({
      chave: `cc-${id}`,
      rotulo: `Centro de custo: ${ccPorId.get(id)?.nome ?? "…"}`,
      limpar: () =>
        aoMudar({ centro_custo_id: filtros.centro_custo_id.filter((x) => x !== id), pagina: 1 }),
    });
  for (const id of filtros.tag_id)
    marcadores.push({
      chave: `tag-${id}`,
      rotulo: `Tag: ${tagPorId.get(id)?.nome ?? "…"}`,
      limpar: () => aoMudar({ tag_id: filtros.tag_id.filter((x) => x !== id), pagina: 1 }),
    });
  if (filtros.valor_min)
    marcadores.push({
      chave: "vmin",
      rotulo: `A partir de ${dinheiro(filtros.valor_min)}`,
      limpar: () => aoMudar({ valor_min: "", pagina: 1 }),
    });
  if (filtros.valor_max)
    marcadores.push({
      chave: "vmax",
      rotulo: `Até ${dinheiro(filtros.valor_max)}`,
      limpar: () => aoMudar({ valor_max: "", pagina: 1 }),
    });
  if (filtros.busca.trim())
    marcadores.push({
      chave: "busca",
      rotulo: `Busca: “${filtros.busca.trim()}”`,
      limpar: () => aoMudar({ busca: "", pagina: 1 }),
    });

  const ativos = quantidadeAtiva(filtros);
  const resultado = resumo ? Number(resumo.resultado) : 0;

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-[9px] border-b border-[var(--linha-suave)] px-4 py-[14px]">
        <div className="flex h-[34px] min-w-[280px] flex-1 items-center gap-2 rounded-[6px] border border-linha-controle bg-[var(--superficie-lateral)] px-[11px] md:max-w-[340px]">
          <IconeBusca className="flex-none text-sutil" />
          <input
            data-busca-da-tela
            type="search"
            name="busca-lancamentos"
            aria-label="Buscar nos lançamentos filtrados"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="search"
            value={buscaLocal}
            onChange={(e) => setBuscaLocal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape" && buscaLocal) {
                e.preventDefault();
                setBuscaLocal("");
              }
            }}
            placeholder="Descrição, categoria, cliente…"
            className="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-[var(--fg)] outline-none placeholder:text-sutil [&::-webkit-search-cancel-button]:hidden"
          />
          {buscaLocal ? (
            <button
              type="button"
              onClick={() => setBuscaLocal("")}
              aria-label="Limpar busca"
              className="flex size-5 flex-none items-center justify-center rounded-[6px] text-sutil transition-colors hover:bg-[var(--bg-muted)] hover:text-[var(--fg)]"
            >
              <X size={14} />
            </button>
          ) : null}
        </div>

        <select
          aria-label="Tipo"
          value={filtros.tipo}
          onChange={(e) =>
            aoMudar({ tipo: e.target.value as FiltrosLancamento["tipo"], pagina: 1 })
          }
          className={SELETOR}
        >
          <option value="">Tipo: todos</option>
          <option value="receita">Receita</option>
          <option value="despesa">Despesa</option>
        </select>

        <select
          aria-label="Status"
          value={filtros.status.length === 1 ? filtros.status[0] : ""}
          onChange={(e) =>
            aoMudar({
              status: e.target.value ? [e.target.value as StatusLancamento] : [],
              pagina: 1,
            })
          }
          className={SELETOR}
        >
          <option value="">Status: todos</option>
          {STATUS.map((s) => (
            <option key={s} value={s}>
              {rotuloDoStatus(s)}
            </option>
          ))}
        </select>

        <select
          aria-label="Categoria"
          value={filtros.categoria_id.length === 1 ? filtros.categoria_id[0] : ""}
          onChange={(e) =>
            aoMudar({ categoria_id: e.target.value ? [e.target.value] : [], pagina: 1 })
          }
          className={cn(SELETOR, "max-w-[210px]")}
        >
          <option value="">Categoria: todas</option>
          {(categorias?.itens ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </select>

        {mundoGlobal === "ambos" ? (
          <select
            aria-label="Mundo da lista"
            value={filtros.mundoDaLista}
            onChange={(e) =>
              aoMudar({
                mundoDaLista: e.target.value as FiltrosLancamento["mundoDaLista"],
                pagina: 1,
              })
            }
            className={SELETOR}
          >
            <option value="">Mundo: ambos</option>
            <option value="digital">Digital</option>
            <option value="infra">Infra</option>
          </select>
        ) : (
          <span
            className="inline-flex h-[34px] items-center gap-[7px] rounded-[6px] px-3 font-[family-name:var(--font-display)] text-[13px] font-bold"
            style={{
              background: `var(--mundo-${mundoGlobal}-bg)`,
              color: `var(--mundo-${mundoGlobal}-fg)`,
            }}
          >
            <PontoMundo mundo={mundoGlobal} className="size-[7px]" />
            Mundo: {ROTULO_MUNDO[mundoGlobal]}
          </span>
        )}

        <MaisFiltros filtros={filtros} aoMudar={aoMudar} />

        <div className="flex-1" />

        <div className="flex items-center gap-[14px] pr-[2px]">
          <span className="text-[13px] text-sutil">
            <strong className="font-[family-name:var(--font-display)] text-[14px] font-extrabold text-forte">
              {resumo?.quantidade ?? 0}
            </strong>{" "}
            resultados
          </span>
          <span aria-hidden className="h-[18px] w-px bg-linha-suave" />
          <span className="numerico font-[family-name:var(--font-display)] text-[13px] font-bold text-[var(--receita-fg)]">
            + {dinheiro(resumo?.total_receitas ?? "0")}
          </span>
          <span className="numerico font-[family-name:var(--font-display)] text-[13px] font-bold text-[var(--despesa-fg)]">
            − {dinheiro(resumo?.total_despesas ?? "0")}
          </span>
          <span
            className="numerico rounded-full bg-[var(--bg-subtle)] px-[9px] py-[3px] font-[family-name:var(--font-display)] text-[13px] font-extrabold"
            style={{ color: resultado >= 0 ? "var(--receita-fg)" : "var(--despesa-fg)" }}
          >
            = {dinheiro(resumo?.resultado ?? "0")}
          </span>
        </div>
      </div>

      {ativos > 0 ? (
        <div className="flex flex-wrap items-center gap-[7px] border-b border-[var(--linha-suave)] bg-[var(--superficie-lateral)] px-4 py-[10px]">
          <span className="text-[12px] font-medium text-sutil">Filtros ativos</span>
          {marcadores.map((m) => (
            <span
              key={m.chave}
              className="inline-flex items-center gap-[6px] rounded-full bg-[var(--brand-tint-2)] py-1 pr-[6px] pl-[10px] font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--lateral-ativo-fg)]"
            >
              {m.rotulo}
              <button
                type="button"
                onClick={m.limpar}
                aria-label={`Remover o filtro ${m.rotulo}`}
                title={`Remover o filtro ${m.rotulo}`}
                className="flex size-[18px] items-center justify-center rounded-full text-[var(--brand-hover)] transition-colors hover:bg-[var(--purple-200)] hover:text-[var(--brand-press)]"
              >
                <X size={13} strokeWidth={2.4} aria-hidden="true" />
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={() =>
              aoMudar({
                ...FILTROS_VAZIOS,
                ordenar: filtros.ordenar,
                direcao: filtros.direcao,
                por_pagina: filtros.por_pagina,
              })
            }
            className="rounded-[4px] px-1 text-[12px] text-sutil underline underline-offset-2 transition-colors hover:text-[var(--fg)]"
          >
            Limpar tudo
          </button>
        </div>
      ) : null}
    </div>
  );
}

/** Os filtros que não cabem na linha: serviço, centro de custo, tags e faixa de valor. */
function MaisFiltros({
  filtros,
  aoMudar,
}: {
  filtros: FiltrosLancamento;
  aoMudar: (parcial: Partial<FiltrosLancamento>) => void;
}) {
  const { data: servicos } = useServicos();
  const { data: centros } = useCentrosCusto();
  const { data: tags } = useTags();

  function alternar(campo: "servico_id" | "centro_custo_id" | "tag_id", id: string) {
    const atual = filtros[campo];
    aoMudar({
      [campo]: atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id],
      pagina: 1,
    } as Partial<FiltrosLancamento>);
  }

  // Quantos filtros estão ligados **dentro** deste painel. Sem isso o botão
  // parece desligado mesmo com três tags marcadas escondidas atrás dele.
  const dentro =
    filtros.servico_id.length +
    filtros.centro_custo_id.length +
    filtros.tag_id.length +
    (filtros.valor_min ? 1 : 0) +
    (filtros.valor_max ? 1 : 0);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={
            dentro > 0 ? `Mais filtros — ${dentro} ativos` : "Mais filtros: serviço, centro de custo, tags e faixa de valor"
          }
          className={cn(
            "flex h-[34px] items-center gap-[6px] rounded-[6px] border border-dashed px-[11px] text-[13px]",
            "transition-colors duration-[var(--dur-fast)] hover:border-[var(--purple-400)] hover:text-[var(--lateral-ativo-fg)]",
            dentro > 0
              ? "border-solid border-[var(--purple-300)] bg-[var(--brand-tint)] text-[var(--lateral-ativo-fg)]"
              : "border-[#D6CFEA] bg-superficie-cartao text-suave dark:border-[var(--border-strong)]",
          )}
        >
          <Plus size={14} strokeWidth={2} aria-hidden="true" />
          Mais filtros
          {dentro > 0 ? (
            <span className="numerico ml-[2px] rounded-full bg-[var(--brand)] px-[6px] text-[11px] font-bold text-[var(--fg-onbrand)]">
              {dentro}
            </span>
          ) : null}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        collisionPadding={12}
        className="w-[min(360px,calc(100vw-24px))]"
      >
        <div className="flex flex-col gap-4">
          <ListaDeMarcar
            titulo="Serviço"
            itens={(servicos?.itens ?? []).map((s) => ({ id: s.id, nome: s.nome }))}
            marcados={filtros.servico_id}
            aoAlternar={(id) => alternar("servico_id", id)}
          />
          <ListaDeMarcar
            titulo="Centro de custo"
            vazio="Nenhum centro cadastrado. Ausência de centro significa “geral”."
            itens={(centros?.itens ?? []).map((c) => ({ id: c.id, nome: c.nome }))}
            marcados={filtros.centro_custo_id}
            aoAlternar={(id) => alternar("centro_custo_id", id)}
          />
          <ListaDeMarcar
            titulo="Tags"
            itens={(tags?.itens ?? []).map((t) => ({ id: t.id, nome: t.nome }))}
            marcados={filtros.tag_id}
            aoAlternar={(id) => alternar("tag_id", id)}
          />

          <div className="flex flex-col gap-2">
            <span className="rotulo-seccao">Faixa de valor</span>
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <Label htmlFor="vmin" className="sr-only">
                  Valor mínimo
                </Label>
                <Input
                  id="vmin"
                  name="valor_min"
                  inputMode="decimal"
                  autoComplete="off"
                  className="numerico"
                  placeholder="0,00"
                  value={filtros.valor_min}
                  onChange={(e) => aoMudar({ valor_min: e.target.value, pagina: 1 })}
                />
              </div>
              <span className="text-sutil">até</span>
              <div className="flex-1">
                <Label htmlFor="vmax" className="sr-only">
                  Valor máximo
                </Label>
                <Input
                  id="vmax"
                  name="valor_max"
                  inputMode="decimal"
                  autoComplete="off"
                  className="numerico"
                  placeholder="5.000,00"
                  value={filtros.valor_max}
                  onChange={(e) => aoMudar({ valor_max: e.target.value, pagina: 1 })}
                />
              </div>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function ListaDeMarcar({
  titulo,
  itens,
  marcados,
  aoAlternar,
  vazio = "Nada cadastrado ainda.",
}: {
  titulo: string;
  itens: { id: string; nome: string }[];
  marcados: string[];
  aoAlternar: (id: string) => void;
  vazio?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="rotulo-seccao">{titulo}</span>
      {itens.length === 0 ? (
        <p className="text-[12px] text-sutil">{vazio}</p>
      ) : (
        <div className="flex max-h-[132px] flex-col gap-1.5 overflow-y-auto pr-1">
          {itens.map((i) => (
            <label key={i.id} className="flex cursor-pointer items-center gap-2 text-[13px]">
              <Checkbox
                checked={marcados.includes(i.id)}
                onCheckedChange={() => aoAlternar(i.id)}
              />
              {i.nome}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
