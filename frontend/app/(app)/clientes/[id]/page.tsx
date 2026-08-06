"use client";

import { use, useState } from "react";
import Link from "next/link";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { ArrowLeft, Archive, Pencil } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { CabecalhoTela, BotaoChrome, Quadro } from "@/componentes/comum/CabecalhoTela";
import { Cartao, RotuloCartao } from "@/componentes/comum/Cartao";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { BadgeStatus } from "@/componentes/comum/BadgeStatus";
import { BadgeMundo, ROTULO_MUNDO } from "@/componentes/comum/BadgeMundo";
import { DataBR } from "@/componentes/comum/DataBR";
import { SituacaoCliente } from "@/componentes/clientes/SituacaoCliente";
import { FormCliente } from "@/componentes/clientes/FormCliente";
import { PainelDetalhe } from "@/componentes/lancamentos/PainelDetalhe";
import { CaixaDeDica, COR } from "@/componentes/graficos/base";
import { api, mensagemDoErro } from "@/lib/api";
import { useCliente, useInvalidarFinanceiro, useSessao } from "@/lib/consultas";
import { dinheiro, iniciais, mesAno, mesCurto, percentual, tempoDeCasa } from "@/lib/formato";
import type { Mundo, MundoFiltro } from "@/lib/tipos";

/**
 * Perfil do cliente (T187, `FR-081`).
 *
 * Total recebido no histórico e no período, receita mês a mês, quebra por
 * mundo (que existe justamente porque o cliente não tem mundo), lançamentos,
 * próximos recebimentos e a situação com o critério explicado.
 */
export default function PaginaCliente({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: c, isLoading } = useCliente(id);
  const { data: sessao } = useSessao();
  const invalidar = useInvalidarFinanceiro();
  const [editando, setEditando] = useState(false);
  const [lancamento, setLancamento] = useState<string | null>(null);

  const arquivar = useMutation({
    mutationFn: () => api.post<{ ocorrencias_futuras_removidas?: number }>(`/api/clientes/${id}/arquivar`),
    onSuccess: (r) => {
      invalidar();
      toast.success(
        r.ocorrencias_futuras_removidas
          ? `Cliente arquivado. ${r.ocorrencias_futuras_removidas} cobranças futuras removidas.`
          : "Cliente arquivado.",
      );
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const desarquivar = useMutation({
    mutationFn: () => api.post<{ mensagem?: string }>(`/api/clientes/${id}/desarquivar`),
    onSuccess: () => {
      invalidar();
      toast.success("Cliente desarquivado.", {
        description: "A recorrência não volta sozinha — edite o cliente para reativar a cobrança.",
      });
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  if (isLoading || !c) {
    return (
      <div className="mx-auto max-w-[var(--conteudo-largura-max)] px-4 pt-5 sm:px-[30px] sm:pt-[26px]">
        <div className="h-40 animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
      </div>
    );
  }

  const podeEditar = sessao?.permissoes.cadastros ?? false;
  const margemNegativa = Number(c.custos.margem_periodo) < 0;

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Clientes"
        titulo={c.nome}
        apoio={
          <span className="flex flex-wrap items-center gap-2">
            {c.empresa ?? "—"}
            {c.contato_email ? <span className="text-sutil">· {c.contato_email}</span> : null}
            {c.contato_telefone ? <span className="text-sutil">· {c.contato_telefone}</span> : null}
            {/* Derivado do lançamento mais antigo, nunca gravado (data-model §3.4).
                Com o histórico retroativo carregado, é aqui que "desde quando" aparece. */}
            {c.cliente_desde ? (
              <span className="text-sutil" title={`Cliente há ${tempoDeCasa(c.cliente_desde)}`}>
                · Cliente desde {mesAno(c.cliente_desde)}
              </span>
            ) : null}
          </span>
        }
        acoes={
          <>
            <Link href="/clientes">
              <BotaoChrome>
                <ArrowLeft size={14} />
                Voltar
              </BotaoChrome>
            </Link>
            {podeEditar ? (
              <>
                <BotaoChrome onClick={() => setEditando(true)}>
                  <Pencil size={14} />
                  Editar
                </BotaoChrome>
                {c.arquivado_em ? (
                  <BotaoChrome onClick={() => desarquivar.mutate()}>Desarquivar</BotaoChrome>
                ) : (
                  <BotaoChrome onClick={() => arquivar.mutate()}>
                    <Archive size={14} />
                    Arquivar
                  </BotaoChrome>
                )}
              </>
            ) : null}
          </>
        }
      />

      {/* Receita, custo e margem do período lado a lado (`FR-081`, `RF-58`). O custo
          é a soma dos lançamentos de despesa na categoria especial de custo do
          cliente — a mesma subcategoria espelho de sempre, do outro lado do sinal. */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Recebido no período</RotuloCartao>
          <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-[var(--receita-fg)]">
            {dinheiro(c.total_recebido_periodo)}
          </span>
          <span className="text-[12px] text-sutil">
            {dinheiro(c.total_recebido_historico)} no total
          </span>
        </Cartao>
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Custo no período</RotuloCartao>
          <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-[var(--despesa-fg)]">
            {dinheiro(c.custos.total_periodo)}
          </span>
          <span className="text-[12px] text-sutil">
            {dinheiro(c.custos.total_historico)} no total
          </span>
        </Cartao>
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Margem no período</RotuloCartao>
          <span
            className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em]"
            style={{ color: margemNegativa ? "var(--despesa-fg)" : "var(--receita-fg)" }}
          >
            {dinheiro(c.custos.margem_periodo)}
          </span>
          {/* Nulo quando não houve receita no período — "0,0%" seria mentira. */}
          <span className="text-[12px] text-sutil">
            {c.custos.margem_percentual_periodo === null
              ? "Sem receita no período"
              : `${percentual(c.custos.margem_percentual_periodo)} do que ele pagou`}
          </span>
        </Cartao>
        <Cartao className="flex flex-col items-start gap-2">
          <RotuloCartao>Situação</RotuloCartao>
          <SituacaoCliente cliente={c} />
          {c.recorrencia ? (
            <p className="text-[12px] text-sutil">
              {c.recorrencia.rotulo} ·{" "}
              {c.recorrencia.efetivar_automaticamente
                ? "efetivação automática"
                : "exige confirmação"}
              {c.recorrencia.ativa ? "" : " · desativada"}
            </p>
          ) : null}
        </Cartao>
      </div>

      <Cartao className="flex flex-col gap-2">
        <RotuloCartao>Por mundo · histórico</RotuloCartao>
        <div className="grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
          {Object.entries(c.quebra_por_mundo).map(([m, v]) => (
            <span key={m} className="flex items-center gap-2 text-[13px]">
              <span
                aria-hidden
                className="size-[7px] rounded-[2.5px]"
                style={{ background: `var(--mundo-${m})` }}
              />
              <span className="flex-1 text-suave">{ROTULO_MUNDO[m as MundoFiltro]}</span>
              <span className="numerico font-semibold text-[var(--receita-fg)]">
                {dinheiro(v)}
              </span>
              <span className="numerico w-[110px] text-right font-semibold text-[var(--despesa-fg)]">
                − {dinheiro(c.quebra_custo_por_mundo[m as Mundo] ?? "0")}
              </span>
            </span>
          ))}
        </div>
      </Cartao>

      {c.recorrencia?.aviso_inadimplencia ? (
        <p
          className="rounded-[10px] px-4 py-3 text-[13px]"
          style={{ background: "var(--st-pendente-bg)", color: "var(--st-pendente-fg)" }}
        >
          {c.recorrencia.aviso_inadimplencia}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Cartao className="flex flex-col gap-2">
          <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
            Receita e custo mês a mês
          </span>
          {c.receita_mensal.length === 0 ? (
            <EstadoVazio titulo="Sem histórico ainda" compacto />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart
                data={c.receita_mensal.map((p) => ({
                  mes: p.mes,
                  v: Number(p.valor),
                  custo: Number(p.custo),
                  margem: Number(p.margem),
                }))}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
              >
                <defs>
                  <linearGradient id="areaCliente" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COR.receita} stopOpacity={0.24} />
                    <stop offset="100%" stopColor={COR.receita} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="areaCustoCliente" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COR.despesa} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={COR.despesa} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="mes"
                  tickFormatter={(v) => mesCurto(String(v))}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: COR.eixo, fontSize: 11 }}
                />
                <Tooltip
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <CaixaDeDica
                        titulo={mesCurto(String(label))}
                        linhas={[
                          {
                            rotulo: "Recebido",
                            valor: dinheiro(Number(payload[0].payload.v)),
                            cor: COR.receita,
                          },
                          {
                            rotulo: "Custo",
                            valor: dinheiro(Number(payload[0].payload.custo)),
                            cor: COR.despesa,
                          },
                          {
                            rotulo: "Margem",
                            valor: dinheiro(Number(payload[0].payload.margem)),
                            cor: COR.marca,
                          },
                        ]}
                      />
                    ) : null
                  }
                />
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke={COR.receita}
                  strokeWidth={1.8}
                  fill="url(#areaCliente)"
                />
                {/* `RF-58`. Custo desenhado por cima, na mesma escala: onde a área
                    vermelha alcança a verde, o cliente parou de dar lucro. */}
                <Area
                  type="monotone"
                  dataKey="custo"
                  stroke={COR.despesa}
                  strokeWidth={1.8}
                  fill="url(#areaCustoCliente)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Cartao>

        <Cartao className="flex flex-col gap-3">
          <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
            Próximos recebimentos
          </span>
          {c.proximos_recebimentos.length === 0 ? (
            <EstadoVazio titulo="Nada programado" compacto />
          ) : (
            <ul className="flex flex-col">
              {c.proximos_recebimentos.map((p) => (
                <li
                  key={p.lancamento_id}
                  className="flex items-center gap-3 border-b border-linha-suave py-2 last:border-b-0"
                >
                  <DataBR valor={p.data} formato="curta" className="text-[12px] text-suave" />
                  <BadgeStatus status={p.status} compacto />
                  <span className="numerico flex-1 text-right text-[13px] font-semibold">
                    {dinheiro(p.valor)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Cartao>
      </div>

      <Quadro>
        <div className="border-b border-linha-suave px-4 py-3">
          <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
            Lançamentos do cliente
          </span>
        </div>
        {c.lancamentos.itens.length === 0 ? (
          <EstadoVazio titulo="Nenhum lançamento no período" compacto />
        ) : (
          <ul>
            {c.lancamentos.itens.map((l) => (
              <li key={l.id}>
                <button
                  type="button"
                  onClick={() => setLancamento(l.id)}
                  className="flex w-full items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-2.5 text-left transition-colors last:border-b-0 hover:bg-[var(--linha-hover)]"
                >
                  <DataBR valor={l.data} formato="empilhada" />
                  <span className="min-w-0 flex-1 truncate text-[13px]">{l.descricao}</span>
                  <BadgeMundo mundo={l.mundo} />
                  <BadgeStatus status={l.status} compacto />
                  {/* O sinal vem do `tipo` do lançamento, não do fato de estar no
                      perfil do cliente: desde `RF-58` esta lista mistura o que ele
                      pagou com o que ele custou, e um "+" em cima de despesa seria
                      leitura errada do número. */}
                  <span
                    className="numerico w-[120px] text-right text-[13px] font-semibold"
                    style={{
                      color:
                        l.status !== "efetivado"
                          ? "var(--valor-previsto-fg)"
                          : l.tipo === "despesa"
                            ? "var(--despesa-fg)"
                            : "var(--receita-fg)",
                    }}
                  >
                    {l.tipo === "despesa" ? "− " : "+ "}
                    {dinheiro(l.valor)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Quadro>

      <FormCliente aberta={editando} cliente={c} aoFechar={() => setEditando(false)} />
      <PainelDetalhe id={lancamento} aoFechar={() => setLancamento(null)} aoEditar={() => {}} />

      <p className="px-1 text-[11px] text-sutil">
        {iniciais(c.nome)} · situação derivada do histórico, nunca gravada.
      </p>
    </div>
  );
}
