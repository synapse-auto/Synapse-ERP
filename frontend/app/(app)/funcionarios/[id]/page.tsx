"use client";

import { use, useState } from "react";
import Link from "next/link";
import { Archive, ArrowLeft, Pencil } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { CabecalhoTela, BotaoChrome, Quadro } from "@/componentes/comum/CabecalhoTela";
import { Cartao, RotuloCartao } from "@/componentes/comum/Cartao";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { BadgeStatus } from "@/componentes/comum/BadgeStatus";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { DataBR } from "@/componentes/comum/DataBR";
import { FormFuncionario } from "@/componentes/funcionarios/FormFuncionario";
import { PainelDetalhe } from "@/componentes/lancamentos/PainelDetalhe";
import { api, mensagemDoErro } from "@/lib/api";
import { useFuncionario, useInvalidarFinanceiro, useSessao } from "@/lib/consultas";
import { dinheiro } from "@/lib/formato";

/**
 * Perfil do funcionário (T189, `FR-087`, `FR-088`).
 *
 * Custo histórico e do período, pagamentos e próximos. **Bônus e vales
 * avulsos entram na conta**: são lançamentos na mesma subcategoria espelho, e
 * é o servidor que os soma ao custo — a tela não separa "folha" de "extra"
 * por conta própria.
 */
export default function PaginaFuncionario({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: f, isLoading } = useFuncionario(id);
  const { data: sessao } = useSessao();
  const invalidar = useInvalidarFinanceiro();
  const [editando, setEditando] = useState(false);
  const [lancamento, setLancamento] = useState<string | null>(null);

  const arquivar = useMutation({
    mutationFn: () => api.post(`/api/funcionarios/${id}/arquivar`),
    onSuccess: () => {
      invalidar();
      toast.success("Funcionário arquivado. Os pagamentos passados ficam no histórico.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  // Simétrico ao do cliente. O aviso vem do servidor: a folha **não** volta junto, e
  // religá-la é editar o funcionário — recriar a recorrência sozinho reativaria um
  // pagamento mensal que alguém desligou de propósito.
  const desarquivar = useMutation({
    mutationFn: () => api.post<{ aviso_folha?: string }>(`/api/funcionarios/${id}/desarquivar`),
    onSuccess: (r) => {
      invalidar();
      toast.success(r?.aviso_folha ?? "Funcionário de volta.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  if (isLoading || !f) {
    return (
      <div className="mx-auto max-w-[var(--conteudo-largura-max)] px-4 pt-5 sm:px-[30px] sm:pt-[26px]">
        <div className="h-40 animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
      </div>
    );
  }

  const podeEditar = sessao?.permissoes.cadastros ?? false;

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Funcionários"
        titulo={f.nome}
        apoio={
          <span className="flex flex-wrap items-center gap-2">
            {f.funcao ?? "—"}
            <BadgeMundo mundo={f.mundo} />
            <span className="text-sutil">
              {f.tipo_contratacao === "pj" ? "PJ" : "Freelancer"} · pagamento todo dia{" "}
              {f.dia_pagamento}
            </span>
          </span>
        }
        acoes={
          <>
            <Link href="/funcionarios">
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
                {f.arquivado_em ? (
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

      <div className="grid gap-4 sm:grid-cols-3">
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Custo no período</RotuloCartao>
          <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-[var(--despesa-fg)]">
            {dinheiro(f.custo_periodo ?? "0")}
          </span>
          <span className="text-[11px] text-sutil">folha, bônus e vales somados</span>
        </Cartao>
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Custo histórico</RotuloCartao>
          <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-forte">
            {dinheiro(f.custo_historico ?? "0")}
          </span>
        </Cartao>
        <Cartao className="flex flex-col gap-1.5">
          <RotuloCartao>Folha mensal</RotuloCartao>
          <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-forte">
            {dinheiro(f.valor_mensal)}
          </span>
          {f.recorrencia ? (
            <span className="text-[11px] text-sutil">
              {f.recorrencia.rotulo} · efetivação automática
            </span>
          ) : null}
        </Cartao>
      </div>

      {f.proximos_pagamentos.length > 0 ? (
        <Cartao className="flex flex-col gap-3">
          <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
            Próximos pagamentos
          </span>
          <ul className="flex flex-col">
            {f.proximos_pagamentos.map((p) => (
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
        </Cartao>
      ) : null}

      <Quadro>
        <div className="border-b border-linha-suave px-4 py-3">
          <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
            Pagamentos
          </span>
        </div>
        {f.pagamentos.length === 0 ? (
          <EstadoVazio titulo="Nenhum pagamento no período" compacto />
        ) : (
          <ul>
            {f.pagamentos.map((l) => (
              <li key={l.lancamento_id}>
                <button
                  type="button"
                  onClick={() => setLancamento(l.lancamento_id)}
                  className="flex w-full items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-2.5 text-left transition-colors last:border-b-0 hover:bg-[var(--linha-hover)]"
                >
                  <DataBR valor={l.data} formato="empilhada" />
                  <span className="min-w-0 flex-1 truncate text-[13px]">{l.descricao}</span>
                  <BadgeStatus status={l.status} compacto />
                  <span
                    className="numerico w-[120px] text-right text-[13px] font-semibold"
                    style={{
                      color:
                        l.status === "efetivado" ? "var(--despesa-fg)" : "var(--valor-previsto-fg)",
                    }}
                  >
                    − {dinheiro(l.valor)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Quadro>

      <FormFuncionario aberta={editando} funcionario={f} aoFechar={() => setEditando(false)} />
      <PainelDetalhe id={lancamento} aoFechar={() => setLancamento(null)} aoEditar={() => {}} />
    </div>
  );
}
