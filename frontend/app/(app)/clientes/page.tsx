"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { CabecalhoTela, Quadro } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { Seletor } from "@/componentes/comum/Seletor";
import { Button } from "@/componentes/ui/button";
import { Paginacao } from "@/componentes/comum/Paginacao";
import { FormCliente } from "@/componentes/clientes/FormCliente";
import { SituacaoCliente } from "@/componentes/clientes/SituacaoCliente";
import { useClientes, useSessao } from "@/lib/consultas";
import { dinheiro, iniciais, tempoDeCasa } from "@/lib/formato";
import { ROTULO_MUNDO } from "@/componentes/comum/BadgeMundo";

/**
 * Clientes (T186, `FR-080`–`FR-084`).
 *
 * **Cliente não tem mundo** (research.md D-04). O filtro de mundo age sobre
 * a *movimentação*: `?mundo=digital` traz quem tem ao menos um lançamento
 * nesse mundo. Cliente sem lançamento nenhum aparece nos três estados do
 * seletor, marcado com `sem_movimentacao` — e a tela explica isso em vez de
 * deixar a pessoa achando que sumiu.
 *
 * A ordenação padrão põe os atrasados no topo (`FR-083`); a situação é
 * derivada no servidor, nunca gravada.
 */
export default function PaginaClientes() {
  const { data: sessao } = useSessao();
  const [busca, setBusca] = useState("");
  const [situacao, setSituacao] = useState<"" | "em_dia" | "atrasado">("");
  const [pagina, setPagina] = useState(1);
  const [criando, setCriando] = useState(false);

  const { data, isLoading } = useClientes({
    busca: busca.trim() || undefined,
    situacao: situacao || undefined,
    pagina,
    por_pagina: 50,
  });

  const podeCadastrar = sessao?.permissoes.cadastros ?? false;
  const atrasados = (data?.itens ?? []).filter((c) => c.situacao === "atrasado");

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Gestão"
        titulo="Clientes"
        apoio="Quem paga, quanto e desde quando. O filtro de mundo vale pela movimentação — cliente não tem mundo."
        acoes={
          podeCadastrar ? (
            <Button size="sm" onClick={() => setCriando(true)}>
              <Plus size={15} />
              Novo cliente
            </Button>
          ) : null
        }
      />

      {atrasados.length > 0 ? (
        <div
          className="flex flex-wrap items-center gap-3 rounded-[10px] border px-[18px] py-3"
          style={{
            background: "var(--st-atrasado-bg)",
            borderColor: "var(--st-atrasado-dot)",
            color: "var(--st-atrasado-fg)",
          }}
        >
          <span className="font-[family-name:var(--font-display)] text-[13px] font-bold">
            {atrasados.length} {atrasados.length === 1 ? "cliente" : "clientes"} além da tolerância
          </span>
          {atrasados.slice(0, 4).map((c) => (
            <Link
              key={c.id}
              href={`/clientes/${c.id}`}
              className="rounded-[4px] px-1.5 py-0.5 text-[13px] font-medium underline-offset-2 transition-colors hover:bg-[var(--st-atrasado-dot)]/20 hover:underline"
            >
              {c.nome} · {dinheiro(c.valor_atrasado)}
            </Link>
          ))}
        </div>
      ) : null}

      <Quadro>
        <div className="flex flex-wrap items-center gap-2 border-b border-linha-suave px-4 py-3">
          <div className="flex h-9 min-w-[240px] flex-1 items-center gap-2 rounded-[8px] border border-linha-controle bg-[var(--superficie-lateral)] px-3 md:max-w-[320px]">
            <Search size={15} className="text-sutil" />
            <input
              data-busca-da-tela
              type="search"
              name="busca-clientes"
              aria-label="Buscar cliente por nome ou empresa"
              autoComplete="off"
              spellCheck={false}
              enterKeyHint="search"
              value={busca}
              onChange={(e) => {
                setBusca(e.target.value);
                setPagina(1);
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape" && busca) {
                  e.preventDefault();
                  setBusca("");
                  setPagina(1);
                }
              }}
              placeholder="Nome ou empresa…"
              className="min-w-0 flex-1 border-0 bg-transparent text-[13px] outline-none placeholder:text-sutil [&::-webkit-search-cancel-button]:hidden"
            />
          </div>
          <Seletor
            rotuloAcessivel="Situação"
            valor={situacao}
            aoMudar={(v) => {
              setSituacao(v as typeof situacao);
              setPagina(1);
            }}
            className="w-auto pl-3"
            opcoes={[
              { valor: "", rotulo: "Situação: todas" },
              { valor: "em_dia", rotulo: "Em dia", cor: "var(--st-efetivado-dot)" },
              { valor: "atrasado", rotulo: "Atrasado", cor: "var(--st-atrasado-dot)" },
            ]}
          />
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-2 p-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-[8px] bg-[var(--bg-subtle)]" />
            ))}
          </div>
        ) : (data?.itens.length ?? 0) === 0 ? (
          <EstadoVazio
            titulo="Nenhum cliente neste recorte"
            descricao="Clientes sem nenhum lançamento aparecem em qualquer mundo. Se a lista está vazia, ou não há cadastro ou o filtro de situação está estreito."
          />
        ) : (
          <ul>
            {data!.itens.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/clientes/${c.id}`}
                  className="flex flex-wrap items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-3 no-underline transition-colors last:border-b-0 hover:bg-[var(--linha-hover)]"
                >
                  <span className="flex size-9 flex-none items-center justify-center rounded-[8px] bg-[var(--brand-tint-2)] font-[family-name:var(--font-display)] text-[12px] font-extrabold text-[var(--lateral-ativo-fg)]">
                    {iniciais(c.nome)}
                  </span>

                  <span className="flex min-w-[200px] flex-1 flex-col">
                    <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
                      {c.nome}
                    </span>
                    <span className="text-[12px] text-sutil">
                      {c.empresa ?? "—"}
                      {c.servicos.length > 0
                        ? ` · ${c.servicos.map((s) => s.nome).join(", ")}`
                        : ""}
                      {/* Tempo de casa — derivado do lançamento mais antigo. Só entra
                          quando há passado de verdade: num cliente cadastrado hoje a
                          linha seria "cliente desde hoje", que não informa nada. */}
                      {c.cliente_desde && tempoDeCasa(c.cliente_desde) !== "menos de 1 mês"
                        ? ` · cliente há ${tempoDeCasa(c.cliente_desde)}`
                        : ""}
                    </span>
                  </span>

                  <span className="flex w-[150px] flex-col text-[12px] text-suave">
                    <span className="text-sutil">Cobrança</span>
                    <span>
                      {c.tipo_cobranca === "recorrente"
                        ? `Mensal, dia ${c.dia_cobranca} · ${dinheiro(c.valor_recorrente)}`
                        : c.tipo_cobranca === "parcelada"
                          ? "Parcelada"
                          : "Pontual"}
                    </span>
                    {c.mundo_cobranca ? (
                      <span className="text-sutil">
                        cobra em {ROTULO_MUNDO[c.mundo_cobranca]}
                      </span>
                    ) : null}
                  </span>

                  <SituacaoCliente cliente={c} />

                  <span className="flex w-[140px] flex-col items-end">
                    <span className="numerico text-[14px] font-bold text-[var(--receita-fg)]">
                      {dinheiro(c.total_recebido_periodo)}
                    </span>
                    <span className="text-[11px] text-sutil">
                      {dinheiro(c.total_recebido_historico)} no total
                    </span>
                  </span>

                  {c.sem_movimentacao ? (
                    <span className="rounded-full bg-[var(--bg-muted)] px-2 py-[2px] text-[10px] text-suave">
                      sem movimentação
                    </span>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        )}

        <Paginacao paginacao={data?.paginacao} aoIr={setPagina} substantivo="clientes" />
      </Quadro>

      <FormCliente aberta={criando} cliente={null} aoFechar={() => setCriando(false)} />
    </div>
  );
}
