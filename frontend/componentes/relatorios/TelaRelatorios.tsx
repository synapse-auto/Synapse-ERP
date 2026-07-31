"use client";

import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { CabecalhoTela, BotaoChrome, Quadro } from "@/componentes/comum/CabecalhoTela";
import { Cartao, RotuloCartao } from "@/componentes/comum/Cartao";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { Delta } from "@/componentes/comum/Delta";
import { IconeExportar } from "@/componentes/comum/icones";
import { ROTULO_MUNDO } from "@/componentes/comum/BadgeMundo";
import {
  useDre,
  useEscopo,
  useMatrizMensal,
  useRelatorioClientes,
  useVariacaoCategorias,
} from "@/lib/consultas";
import { baixarArquivo, mensagemDoErro } from "@/lib/api";
import { dinheiro, mesCurto, percentual } from "@/lib/formato";
import type { MundoFiltro } from "@/lib/tipos";

/**
 * Relatórios (T191–T194, `FR-090`–`FR-095`).
 *
 * Quatro relatórios em quatro abas. Duas regras do contrato que a tela
 * respeita sem improvisar:
 *
 * - **CSV e PDF recebem a resposta já montada** no servidor, com os mesmos
 *   dados do JSON. A tela só pede o formato; não remonta nada.
 * - **PDF só existe em DRE e Clientes.** Matriz e variação são largas demais
 *   para A4 e o servidor recusa com `400`. Por isso o botão nem aparece nas
 *   outras abas — e a explicação vai junto.
 *
 * O limiar de destaque da variação vem em `limiar_destaque_percentual`; o
 * número **não** aparece escrito no código (`FR-092`, `RNF-02`).
 */

type Aba = "dre" | "clientes" | "variacao" | "matriz";

const ABAS: { valor: Aba; rotulo: string; pdf: boolean; rota: string }[] = [
  { valor: "dre", rotulo: "DRE", pdf: true, rota: "dre" },
  { valor: "clientes", rotulo: "Ranking de clientes", pdf: true, rota: "clientes" },
  { valor: "variacao", rotulo: "Variação por categoria", pdf: false, rota: "variacao-categorias" },
  { valor: "matriz", rotulo: "Matriz mensal", pdf: false, rota: "matriz-mensal" },
];

export function TelaRelatorios() {
  const [aba, setAba] = useState<Aba>("dre");
  const escopo = useEscopo();

  const dre = useDre(aba === "dre");
  const clientes = useRelatorioClientes(aba === "clientes");
  const variacao = useVariacaoCategorias(aba === "variacao");
  const matriz = useMatrizMensal(aba === "matriz");

  const abaAtual = ABAS.find((a) => a.valor === aba)!;

  async function exportar(formato: "csv" | "pdf") {
    try {
      const nome = `${abaAtual.rota}-${escopo.mundo}-${escopo.periodo}.${formato}`;
      await baixarArquivo(`/api/relatorios/${abaAtual.rota}`, nome, {
        consulta: { ...escopo.parametros, formato },
      });
    } catch (e) {
      toast.error(mensagemDoErro(e));
    }
  }

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-[30px] pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Fechamento"
        titulo="Relatórios"
        apoio="Os mesmos números da tela saem em CSV e em PDF — o arquivo é montado no servidor, a partir da mesma resposta."
        acoes={
          <>
            <BotaoChrome onClick={() => void exportar("csv")}>
              <IconeExportar />
              CSV
            </BotaoChrome>
            {abaAtual.pdf ? (
              <BotaoChrome onClick={() => void exportar("pdf")}>
                <IconeExportar />
                PDF
              </BotaoChrome>
            ) : null}
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-[2px] self-start rounded-[9px] border border-linha-suave bg-segmento p-[3px]">
        {ABAS.map((a) => (
          <button
            key={a.valor}
            type="button"
            onClick={() => setAba(a.valor)}
            className={cn(
              "rounded-[7px] px-[13px] py-[7px] font-[family-name:var(--font-display)] text-[12.5px] font-semibold transition-colors",
              aba === a.valor
                ? "bg-superficie-cartao text-[var(--ink-700)] shadow-[0_1px_2px_rgba(30,22,51,0.08)] dark:text-[var(--fg-strong)]"
                : "text-suave hover:text-[var(--fg)]",
            )}
          >
            {a.rotulo}
          </button>
        ))}
      </div>

      {!abaAtual.pdf ? (
        <p className="px-1 text-[11.5px] text-sutil">
          Este relatório sai só em CSV: numa folha A4 a matriz fica ilegível, e o servidor recusa
          o PDF em vez de entregar um arquivo que ninguém consegue ler.
        </p>
      ) : null}

      {aba === "dre" ? (
        dre.isLoading || !dre.data ? (
          <Esqueleto />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <CartaoNumero
                rotulo="Receita bruta"
                valor={dre.data.receita_bruta}
                cor="var(--receita-fg)"
                comparativo={dre.data.comparativo_periodo_anterior?.receita_bruta}
              />
              <CartaoNumero
                rotulo="Despesa total"
                valor={dre.data.despesa_total}
                cor="var(--despesa-fg)"
                inverso
                comparativo={dre.data.comparativo_periodo_anterior?.despesa_total}
              />
              <CartaoNumero
                rotulo="Resultado"
                valor={dre.data.resultado}
                comparativo={dre.data.comparativo_periodo_anterior?.resultado}
              />
              <Cartao className="flex flex-col gap-1.5">
                <RotuloCartao>Margem</RotuloCartao>
                <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-forte">
                  {percentual(dre.data.margem_percentual)}
                </span>
                <span className="text-[11px] text-sutil">
                  No ano: {dinheiro(dre.data.acumulado_ano?.resultado)} ·{" "}
                  {percentual(dre.data.acumulado_ano?.margem_percentual)}
                </span>
              </Cartao>
            </div>

            {dre.data.leitura_linguagem_natural ? (
              <Cartao className="flex flex-col gap-2">
                <RotuloCartao cor="marca">Leitura do período</RotuloCartao>
                <p className="text-[14px] leading-[1.6] text-[var(--fg)]">
                  {dre.data.leitura_linguagem_natural}
                </p>
              </Cartao>
            ) : null}

            <div className="grid gap-4 lg:grid-cols-2">
              <BlocoDre titulo="Receitas" linhas={dre.data.receitas} cor="var(--receita-fg)" />
              <BlocoDre titulo="Despesas" linhas={dre.data.despesas} cor="var(--despesa-fg)" />
            </div>
          </>
        )
      ) : null}

      {aba === "clientes" ? (
        clientes.isLoading || !clientes.data ? (
          <Esqueleto />
        ) : clientes.data.clientes.length === 0 ? (
          <Quadro>
            <EstadoVazio titulo="Nenhuma receita de cliente no período" />
          </Quadro>
        ) : (
          <Quadro>
            <div className="grid grid-cols-[36px_minmax(180px,1fr)_140px_110px_120px_1fr] items-center border-b border-linha-suave bg-[var(--superficie-lateral)] px-4 py-2.5">
              {["#", "Cliente", "Recebido", "% do total", "Situação", "Por mundo"].map((h) => (
                <span
                  key={h}
                  className="font-[family-name:var(--font-display)] text-[10.5px] font-bold tracking-[0.07em] text-sutil uppercase"
                >
                  {h}
                </span>
              ))}
            </div>
            {clientes.data.clientes.map((c, i) => (
              <div
                key={c.cliente_id}
                className="grid grid-cols-[36px_minmax(180px,1fr)_140px_110px_120px_1fr] items-center border-b border-[var(--linha-suave)] px-4 py-2.5 last:border-b-0"
              >
                <span className="font-mono text-[11px] text-sutil">{i + 1}</span>
                <span className="truncate pr-3 text-[13px] text-[var(--fg)]">{c.nome}</span>
                <span className="numerico text-[13px] font-semibold text-[var(--receita-fg)]">
                  {dinheiro(c.total_recebido)}
                </span>
                <span className="numerico text-[12.5px] text-suave">
                  {percentual(c.percentual_faturamento)}
                </span>
                <span
                  className="w-fit rounded-full px-2 py-[2px] text-[10.5px] font-bold"
                  style={{
                    background:
                      c.situacao === "atrasado" ? "var(--st-atrasado-bg)" : "var(--st-efetivado-bg)",
                    color:
                      c.situacao === "atrasado" ? "var(--st-atrasado-fg)" : "var(--st-efetivado-fg)",
                  }}
                >
                  {c.situacao === "atrasado" ? "Atrasado" : "Em dia"}
                </span>
                <span className="flex flex-wrap gap-3 text-[11.5px] text-suave">
                  {Object.entries(c.quebra_por_mundo).map(([m, v]) => (
                    <span key={m} className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-[6px] rounded-[2px]"
                        style={{ background: `var(--mundo-${m})` }}
                      />
                      {ROTULO_MUNDO[m as MundoFiltro]} <span className="numerico">{dinheiro(v)}</span>
                    </span>
                  ))}
                </span>
              </div>
            ))}
            <div className="flex items-center justify-between bg-[var(--superficie-lateral)] px-4 py-3">
              <span className="text-[12.5px] text-sutil">Faturamento do período</span>
              <span className="numerico font-[family-name:var(--font-display)] text-[14px] font-extrabold text-forte">
                {dinheiro(clientes.data.faturamento_total)}
              </span>
            </div>
          </Quadro>
        )
      ) : null}

      {aba === "variacao" ? (
        variacao.isLoading || !variacao.data ? (
          <Esqueleto />
        ) : (
          <Quadro>
            <p className="border-b border-linha-suave px-4 py-2.5 text-[12px] text-sutil">
              Destaque quando a variação passa de{" "}
              <strong className="text-[var(--fg)]">
                {variacao.data.limiar_destaque_percentual}%
              </strong>{" "}
              — o critério vem da configuração, não do código.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-[12.5px]">
                <thead className="bg-[var(--superficie-lateral)]">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-[family-name:var(--font-display)] text-[10.5px] font-bold tracking-[0.07em] text-sutil uppercase">
                      Categoria
                    </th>
                    {variacao.data.meses.map((m) => (
                      <th
                        key={m}
                        className="px-3 py-2.5 text-right font-[family-name:var(--font-display)] text-[10.5px] font-bold tracking-[0.07em] text-sutil uppercase"
                      >
                        {mesCurto(m)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {variacao.data.linhas.map((l) => (
                    <tr key={l.categoria_id} className="border-t border-[var(--linha-suave)]">
                      <td className="px-4 py-2 whitespace-nowrap">{l.nome}</td>
                      {l.valores.map((v) => (
                        <td key={v.mes} className="px-3 py-2 text-right">
                          <span className="numerico block">{dinheiro(v.valor)}</span>
                          {v.variacao_percentual !== null ? (
                            <span
                              className={cn(
                                "numerico block text-[10.5px]",
                                v.destacar ? "font-bold" : "text-sutil",
                              )}
                              style={
                                v.destacar
                                  ? {
                                      color:
                                        Number(v.variacao_percentual) > 0
                                          ? "var(--despesa-fg)"
                                          : "var(--receita-fg)",
                                    }
                                  : undefined
                              }
                            >
                              {percentual(v.variacao_percentual, { sinal: true })}
                            </span>
                          ) : null}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Quadro>
        )
      ) : null}

      {aba === "matriz" ? (
        matriz.isLoading || !matriz.data ? (
          <Esqueleto />
        ) : (
          <Quadro>
            <div className="overflow-x-auto">
              <table className="w-full text-[12.5px]">
                <thead className="bg-[var(--superficie-lateral)]">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-[family-name:var(--font-display)] text-[10.5px] font-bold tracking-[0.07em] text-sutil uppercase">
                      Categoria
                    </th>
                    {matriz.data.meses.map((m) => (
                      <th
                        key={m}
                        className="px-3 py-2.5 text-right font-[family-name:var(--font-display)] text-[10.5px] font-bold tracking-[0.07em] text-sutil uppercase"
                      >
                        {mesCurto(m)}
                      </th>
                    ))}
                    <th className="px-4 py-2.5 text-right font-[family-name:var(--font-display)] text-[10.5px] font-bold tracking-[0.07em] text-sutil uppercase">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {matriz.data.linhas.map((l) => (
                    <tr key={l.categoria_id} className="border-t border-[var(--linha-suave)]">
                      <td className="flex items-center gap-2 px-4 py-2 whitespace-nowrap">
                        <span
                          aria-hidden
                          className="size-[7px] rounded-[2px]"
                          style={{ background: l.cor ?? "var(--fg-subtle)" }}
                        />
                        {l.nome}
                      </td>
                      {matriz.data!.meses.map((m) => (
                        <td key={m} className="numerico px-3 py-2 text-right text-suave">
                          {dinheiro(l.valores[m] ?? "0")}
                        </td>
                      ))}
                      <td className="numerico px-4 py-2 text-right font-semibold text-forte">
                        {dinheiro(l.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-[var(--superficie-lateral)]">
                  <tr>
                    <td className="px-4 py-2.5 font-semibold">Total</td>
                    {matriz.data.meses.map((m) => (
                      <td key={m} className="numerico px-3 py-2.5 text-right font-semibold">
                        {dinheiro(matriz.data!.totais_por_mes[m] ?? "0")}
                      </td>
                    ))}
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>
          </Quadro>
        )
      ) : null}
    </div>
  );
}

function CartaoNumero({
  rotulo,
  valor,
  cor,
  inverso,
  comparativo,
}: {
  rotulo: string;
  valor: string;
  cor?: string;
  inverso?: boolean;
  comparativo?: Parameters<typeof Delta>[0]["comparativo"];
}) {
  return (
    <Cartao className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <RotuloCartao>{rotulo}</RotuloCartao>
        {comparativo ? <Delta comparativo={comparativo} inverso={inverso} /> : null}
      </div>
      <span
        className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em]"
        style={{ color: cor ?? "var(--fg-strong)" }}
      >
        {dinheiro(valor)}
      </span>
    </Cartao>
  );
}

function BlocoDre({
  titulo,
  linhas,
  cor,
}: {
  titulo: string;
  linhas: { categoria_id: string; nome: string; valor: string; subcategorias: { nome: string; valor: string }[] }[];
  cor: string;
}) {
  return (
    <Quadro>
      <div className="border-b border-linha-suave bg-[var(--superficie-lateral)] px-4 py-2.5">
        <span className="font-[family-name:var(--font-display)] text-[13px] font-bold text-forte">
          {titulo}
        </span>
      </div>
      {linhas.length === 0 ? (
        <EstadoVazio titulo={`Nenhuma ${titulo.toLowerCase()} no período`} compacto />
      ) : (
        linhas.map((l) => (
          <div key={l.categoria_id} className="border-b border-[var(--linha-suave)] last:border-b-0">
            <div className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="text-[13px] font-semibold text-[var(--fg)]">{l.nome}</span>
              <span className="numerico text-[13px] font-bold" style={{ color: cor }}>
                {dinheiro(l.valor)}
              </span>
            </div>
            {l.subcategorias.length > 0 ? (
              <ul className="bg-[var(--bg-subtle)] px-4 pb-2">
                {l.subcategorias.map((s) => (
                  <li
                    key={s.nome}
                    className="flex items-center justify-between gap-3 py-1 text-[12px] text-suave"
                  >
                    <span className="pl-3">{s.nome}</span>
                    <span className="numerico">{dinheiro(s.valor)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))
      )}
    </Quadro>
  );
}

function Esqueleto() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-[104px] animate-pulse rounded-[14px] bg-[var(--bg-subtle)]" />
        ))}
      </div>
      <div className="h-[320px] animate-pulse rounded-[14px] bg-[var(--bg-subtle)]" />
    </div>
  );
}
