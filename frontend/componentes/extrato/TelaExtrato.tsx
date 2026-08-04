"use client";

import { useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { cn } from "@/lib/utils";
import { CabecalhoTela, Quadro } from "@/componentes/comum/CabecalhoTela";
import { Cartao } from "@/componentes/comum/Cartao";
import { Delta } from "@/componentes/comum/Delta";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { BadgeStatus } from "@/componentes/comum/BadgeStatus";
import { PainelDetalhe } from "@/componentes/lancamentos/PainelDetalhe";
import { CaixaDeDica, COR, useMovimentoReduzido } from "@/componentes/graficos/base";
import { useEscopo, useExtrato } from "@/lib/consultas";
import { dataCurta, dinheiro } from "@/lib/formato";
import type { Agrupamento, Extrato, Pendencia } from "@/lib/tipos";
import { useRouter } from "next/navigation";

/**
 * Extrato (T182–T184, `FR-047`–`FR-052`).
 *
 * É o extrato bancário do negócio: o que entrou e o que saiu, agrupado por
 * dia, semana ou mês, com **saldo acumulado ao fim de cada grupo**.
 *
 * Duas regras de `RN-05` aparecem na tela:
 * - grupos futuros são marcados como **previstos** e seus valores **não**
 *   entram no saldo acumulado — quem garante isso é o servidor, e a tela
 *   mostra a marca para a pessoa entender por que a conta "não fecha" com o
 *   que ela vê;
 * - a seção "A pagar / A receber" **ignora o filtro de período**: pendência
 *   não é histórico, e conta vencida em maio continua a pagar em julho.
 */

const AGRUPAMENTOS: { valor: Agrupamento; rotulo: string }[] = [
  { valor: "dia", rotulo: "Por dia" },
  { valor: "semana", rotulo: "Por semana" },
  { valor: "mes", rotulo: "Por mês" },
];

export function TelaExtrato() {
  const router = useRouter();
  const [agrupamento, setAgrupamento] = useState<Agrupamento>("dia");
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const { data, isLoading } = useExtrato(agrupamento);
  const escopo = useEscopo();
  const semMovimento = useMovimentoReduzido();

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Leitura rápida"
        titulo="Extrato"
        apoio="O que entrou e o que saiu, com saldo acumulado — como um extrato bancário."
        acoes={
          <div
            role="radiogroup"
            aria-label="Agrupar o extrato por"
            className="flex items-center gap-[2px] rounded-[6px] border border-linha-suave bg-segmento p-[3px]"
          >
            {AGRUPAMENTOS.map((a) => (
              <button
                key={a.valor}
                type="button"
                role="radio"
                aria-checked={agrupamento === a.valor}
                onClick={() => setAgrupamento(a.valor)}
                className={cn(
                  "rounded-[6px] px-[11px] py-[6px] font-[family-name:var(--font-display)] text-[13px] font-semibold transition-colors",
                  agrupamento === a.valor
                    ? "bg-superficie-cartao text-[var(--ink-700)] shadow-[0_1px_2px_rgba(30,22,51,0.08)] dark:text-[var(--fg-strong)]"
                    : "text-suave hover:text-[var(--fg)]",
                )}
              >
                {a.rotulo}
              </button>
            ))}
          </div>
        }
      />

      {isLoading || !data ? (
        <div className="flex flex-col gap-4">
          <div className="h-[104px] animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
          <div className="h-[420px] animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
        </div>
      ) : (
        <>
          <CabecalhoResumo resumo={data.resumo} />

          {data.grafico.length > 0 ? (
            <Cartao className="flex flex-col gap-2">
              <span className="rotulo-seccao">Receitas × despesas no período</span>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart
                  data={data.grafico.map((g) => ({
                    rotulo: g.rotulo,
                    receitas: Number(g.receitas),
                    despesas: Number(g.despesas),
                  }))}
                  margin={{ top: 8, right: 0, bottom: 0, left: 0 }}
                >
                  <XAxis
                    dataKey="rotulo"
                    tickFormatter={(v) => dataCurta(String(v))}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: COR.eixo, fontSize: 10 }}
                    interval="preserveStartEnd"
                  />
                  <Tooltip
                    cursor={{ fill: "var(--bg-subtle)" }}
                    content={({ active, payload, label }) =>
                      active && payload?.length ? (
                        <CaixaDeDica
                          titulo={dataCurta(String(label))}
                          linhas={payload.map((p) => ({
                            rotulo: p.dataKey === "receitas" ? "Receitas" : "Despesas",
                            valor: dinheiro(Number(p.value)),
                            cor: String(p.color),
                          }))}
                        />
                      ) : null
                    }
                  />
                  <Bar
                    dataKey="receitas"
                    fill={COR.receita}
                    radius={[3, 3, 0, 0]}
                    maxBarSize={14}
                    isAnimationActive={!semMovimento}
                  />
                  <Bar
                    dataKey="despesas"
                    fill={COR.despesa}
                    radius={[3, 3, 0, 0]}
                    maxBarSize={14}
                    isAnimationActive={!semMovimento}
                  />
                </BarChart>
              </ResponsiveContainer>
            </Cartao>
          ) : null}

          <SecaoPendencias
            pendencias={data.pendencias}
            aoAbrir={setSelecionado}
            aoVerTodos={(tipo) =>
              router.push(
                `/lancamentos?mundo=${escopo.mundo}&tipo=${tipo}&status=programado&status=pendente&status=atrasado`,
              )
            }
          />

          <Quadro>
            {data.grupos.length === 0 ? (
              <EstadoVazio
                titulo="Nada neste período"
                descricao="Não houve movimentação no mundo e no período escolhidos."
              />
            ) : (
              data.grupos.map((g) => (
                <section key={`${g.inicio}-${g.fim}`}>
                  <header
                    className={cn(
                      "flex flex-wrap items-center gap-3 border-b border-linha-suave px-4 py-2.5",
                      g.previsto ? "bg-[var(--st-programado-bg)]" : "bg-[var(--superficie-lateral)]",
                    )}
                  >
                    <span className="font-[family-name:var(--font-display)] text-[13px] font-bold text-forte">
                      {g.rotulo}
                    </span>
                    {g.previsto ? (
                      <span
                        className="rounded-full px-2 py-[2px] text-[10px] font-bold"
                        style={{
                          background: "var(--superficie-cartao)",
                          color: "var(--st-programado-fg)",
                        }}
                      >
                        previsto · não entra no saldo
                      </span>
                    ) : null}
                    <span className="flex-1" />
                    <span className="numerico text-[12px] text-[var(--receita-fg)]">
                      + {dinheiro(g.totais.receitas)}
                    </span>
                    <span className="numerico text-[12px] text-[var(--despesa-fg)]">
                      − {dinheiro(g.totais.despesas)}
                    </span>
                    <span className="flex items-baseline gap-1.5">
                      <span className="text-[11px] text-sutil">saldo</span>
                      <span className="numerico font-[family-name:var(--font-display)] text-[13px] font-extrabold text-forte">
                        {dinheiro(g.saldo_acumulado)}
                      </span>
                    </span>
                  </header>

                  <ul>
                    {g.lancamentos.map((l) => (
                      <li key={l.id}>
                        <button
                          type="button"
                          onClick={() => setSelecionado(l.id)}
                          className="flex w-full items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-2.5 text-left transition-colors hover:bg-[var(--linha-hover)]"
                        >
                          <span
                            aria-hidden
                            className="size-[7px] flex-none rounded-[2.5px]"
                            style={{ background: l.categoria.cor ?? "var(--fg-subtle)" }}
                          />
                          <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--fg)]">
                            {l.descricao}
                            <span className="text-sutil">
                              {" "}
                              · {l.categoria.nome}
                              {l.subcategoria ? ` · ${l.subcategoria.nome}` : ""}
                            </span>
                          </span>
                          {escopo.mundo === "ambos" ? <BadgeMundo mundo={l.mundo} /> : null}
                          <BadgeStatus status={l.status} compacto />
                          <span
                            className="numerico w-[120px] text-right text-[13px] font-semibold"
                            style={{
                              color:
                                l.status === "efetivado"
                                  ? l.tipo === "receita"
                                    ? "var(--receita-fg)"
                                    : "var(--despesa-fg)"
                                  : "var(--valor-previsto-fg)",
                            }}
                          >
                            {l.tipo === "receita" ? "+ " : "− "}
                            {dinheiro(l.valor)}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ))
            )}
          </Quadro>
        </>
      )}

      <PainelDetalhe
        id={selecionado}
        aoFechar={() => setSelecionado(null)}
        aoEditar={(id) => router.push(`/lancamentos?selecionado=${id}`)}
      />
    </div>
  );
}

/** Cabeçalho-resumo comparativo (`FR-048`) — quatro colunas, como no mockup. */
function CabecalhoResumo({ resumo }: { resumo: Extrato["resumo"] }) {
  const colunas: { chave: string; rotulo: string; valor: string; inverso?: boolean }[] = [
    { chave: "total_receitas", rotulo: "Receitas", valor: resumo.total_receitas },
    { chave: "total_despesas", rotulo: "Despesas", valor: resumo.total_despesas, inverso: true },
    { chave: "resultado", rotulo: "Resultado", valor: resumo.resultado },
    { chave: "saldo_final", rotulo: "Saldo final", valor: resumo.saldo_final },
  ];

  return (
    <div className="grid overflow-hidden rounded-[12px] border border-linha-chrome bg-superficie-cartao shadow-[var(--sombra-cartao)] sm:grid-cols-2 xl:grid-cols-4">
      {colunas.map((c, i) => (
        <div
          key={c.chave}
          className={cn(
            "flex flex-col gap-1.5 px-5 py-4",
            i > 0 && "border-t border-linha-suave xl:border-t-0 xl:border-l",
          )}
        >
          <span className="rotulo-seccao">{c.rotulo}</span>
          <span className="flex flex-wrap items-center gap-2">
            <span
              className="numerico font-[family-name:var(--font-display)] text-[22px] font-extrabold tracking-[-0.03em]"
              style={{
                color:
                  c.chave === "total_receitas"
                    ? "var(--receita-fg)"
                    : c.chave === "total_despesas"
                      ? "var(--despesa-fg)"
                      : "var(--fg-strong)",
              }}
            >
              {dinheiro(c.valor)}
            </span>
            <Delta comparativo={resumo.comparativos?.[c.chave]} inverso={c.inverso} />
          </span>
        </div>
      ))}
    </div>
  );
}

/** Seção fixa "A pagar / A receber" (`FR-051`), com vencidos em vermelho. */
function SecaoPendencias({
  pendencias,
  aoAbrir,
  aoVerTodos,
}: {
  pendencias: Extrato["pendencias"];
  aoAbrir: (id: string) => void;
  aoVerTodos: (tipo: "receita" | "despesa") => void;
}) {
  const listas: { titulo: string; tipo: "receita" | "despesa"; itens: Pendencia[] }[] = [
    { titulo: "A receber", tipo: "receita", itens: pendencias.a_receber },
    { titulo: "A pagar", tipo: "despesa", itens: pendencias.a_pagar },
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {listas.map((l) => {
        const total = l.itens.reduce((a, p) => a + Number(p.valor), 0);
        const vencidos = l.itens.filter((p) => p.vencido);
        return (
          <Cartao key={l.tipo} className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
                {l.titulo}
              </span>
              <span
                className="numerico font-[family-name:var(--font-display)] text-[16px] font-extrabold"
                style={{ color: l.tipo === "receita" ? "var(--receita-fg)" : "var(--despesa-fg)" }}
              >
                {dinheiro(total)}
              </span>
            </div>

            {vencidos.length > 0 ? (
              <p
                className="rounded-[8px] px-3 py-2 text-[12px]"
                style={{ background: "var(--st-atrasado-bg)", color: "var(--st-atrasado-fg)" }}
              >
                {vencidos.length} {vencidos.length === 1 ? "vencido" : "vencidos"} ·{" "}
                {dinheiro(vencidos.reduce((a, p) => a + Number(p.valor), 0))}
              </p>
            ) : null}

            {l.itens.length === 0 ? (
              <EstadoVazio titulo="Nada pendente" compacto />
            ) : (
              <ul className="flex flex-col">
                {l.itens.slice(0, 6).map((p) => (
                  <li key={p.lancamento_id}>
                    <button
                      type="button"
                      onClick={() => aoAbrir(p.lancamento_id)}
                      aria-label={`Abrir ${p.descricao}`}
                      className={cn(
                        "flex w-full items-center gap-3 border-b border-linha-suave py-2 text-left last:border-b-0",
                        // Sem hover a linha não avisava que abre o lançamento.
                        "-mx-2 rounded-[6px] px-2 transition-colors duration-[var(--dur-fast)]",
                        "hover:bg-[var(--linha-hover)]",
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--fg)]">
                        {p.descricao}
                      </span>
                      <span
                        className={cn(
                          "text-[12px]",
                          p.vencido ? "font-semibold text-[var(--despesa-fg)]" : "text-sutil",
                        )}
                      >
                        {dataCurta(p.data)}
                      </span>
                      <BadgeStatus status={p.status} compacto />
                      <span className="numerico w-[110px] text-right text-[13px] font-semibold">
                        {dinheiro(p.valor)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {l.itens.length > 6 ? (
              <button
                type="button"
                onClick={() => aoVerTodos(l.tipo)}
                className="self-start rounded-[4px] text-[12px] font-semibold text-[var(--brand-hover)] underline-offset-2 transition-colors hover:text-[var(--brand-press)] hover:underline"
              >
                Ver os {l.itens.length} na lista →
              </button>
            ) : null}

            <p className="text-[11px] text-sutil">
              Esta seção ignora o filtro de período — pendência não é histórico.
            </p>
          </Cartao>
        );
      })}
    </div>
  );
}
