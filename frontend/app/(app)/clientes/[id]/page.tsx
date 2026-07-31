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
import { dinheiro, iniciais, mesCurto } from "@/lib/formato";
import type { MundoFiltro } from "@/lib/tipos";

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
      <div className="mx-auto max-w-[var(--conteudo-largura-max)] px-[30px] pt-[26px]">
        <div className="h-40 animate-pulse rounded-[14px] bg-[var(--bg-subtle)]" />
      </div>
    );
  }

  const podeEditar = sessao?.permissoes.cadastros ?? false;

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-[30px] pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Clientes"
        titulo={c.nome}
        apoio={
          <span className="flex flex-wrap items-center gap-2">
            {c.empresa ?? "—"}
            {c.contato_email ? <span className="text-sutil">· {c.contato_email}</span> : null}
            {c.contato_telefone ? <span className="text-sutil">· {c.contato_telefone}</span> : null}
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

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Recebido no período</RotuloCartao>
          <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-[var(--receita-fg)]">
            {dinheiro(c.total_recebido_periodo)}
          </span>
        </Cartao>
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Recebido no total</RotuloCartao>
          <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-forte">
            {dinheiro(c.total_recebido_historico)}
          </span>
        </Cartao>
        <Cartao className="flex flex-col gap-2">
          <RotuloCartao>Por mundo</RotuloCartao>
          {Object.entries(c.quebra_por_mundo).map(([m, v]) => (
            <span key={m} className="flex items-center gap-2 text-[12.5px]">
              <span
                aria-hidden
                className="size-[7px] rounded-[2.5px]"
                style={{ background: `var(--mundo-${m})` }}
              />
              <span className="flex-1 text-suave">{ROTULO_MUNDO[m as MundoFiltro]}</span>
              <span className="numerico font-semibold text-forte">{dinheiro(v)}</span>
            </span>
          ))}
        </Cartao>
        <Cartao className="flex flex-col items-start gap-2">
          <RotuloCartao>Situação</RotuloCartao>
          <SituacaoCliente cliente={c} />
          {c.recorrencia ? (
            <p className="text-[11.5px] text-sutil">
              {c.recorrencia.rotulo} ·{" "}
              {c.recorrencia.efetivar_automaticamente
                ? "efetivação automática"
                : "exige confirmação"}
              {c.recorrencia.ativa ? "" : " · desativada"}
            </p>
          ) : null}
        </Cartao>
      </div>

      {c.recorrencia?.aviso_inadimplencia ? (
        <p
          className="rounded-[12px] px-4 py-3 text-[12.5px]"
          style={{ background: "var(--st-pendente-bg)", color: "var(--st-pendente-fg)" }}
        >
          {c.recorrencia.aviso_inadimplencia}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Cartao className="flex flex-col gap-2">
          <span className="font-[family-name:var(--font-display)] text-[14.5px] font-bold text-forte">
            Receita mês a mês
          </span>
          {c.receita_mensal.length === 0 ? (
            <EstadoVazio titulo="Sem histórico ainda" compacto />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart
                data={c.receita_mensal.map((p) => ({ mes: p.mes, v: Number(p.valor) }))}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
              >
                <defs>
                  <linearGradient id="areaCliente" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COR.receita} stopOpacity={0.24} />
                    <stop offset="100%" stopColor={COR.receita} stopOpacity={0} />
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
                            valor: dinheiro(Number(payload[0].value)),
                            cor: COR.receita,
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
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Cartao>

        <Cartao className="flex flex-col gap-3">
          <span className="font-[family-name:var(--font-display)] text-[14.5px] font-bold text-forte">
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
                  <span className="numerico flex-1 text-right text-[12.5px] font-semibold">
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
                  <span
                    className="numerico w-[120px] text-right text-[13px] font-semibold"
                    style={{
                      color:
                        l.status === "efetivado" ? "var(--receita-fg)" : "var(--valor-previsto-fg)",
                    }}
                  >
                    + {dinheiro(l.valor)}
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
