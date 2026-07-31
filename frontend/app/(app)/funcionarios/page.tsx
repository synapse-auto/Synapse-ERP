"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { CabecalhoTela, Quadro } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { Button } from "@/componentes/ui/button";
import { Checkbox } from "@/componentes/ui/checkbox";
import { FormFuncionario } from "@/componentes/funcionarios/FormFuncionario";
import { useFuncionarios, useSessao } from "@/lib/consultas";
import { dinheiro, iniciais } from "@/lib/formato";

/**
 * Funcionários (T188, `FR-085`).
 *
 * Diferença de modelagem em relação a clientes: **funcionário tem `mundo`**,
 * obrigatório e imutável (`RN-15`). Por isso a lista respeita o seletor
 * global de mundo de verdade, e não por movimentação derivada.
 *
 * Cadastrar cria a subcategoria espelho e a recorrência mensal da folha na
 * mesma transação. A folha nasce com efetivação automática: é despesa certa,
 * e deixá-la pendente encheria a caixa de confirmações mensais sem informação.
 */
export default function PaginaFuncionarios() {
  const { data: sessao } = useSessao();
  const [incluirArquivados, setIncluirArquivados] = useState(false);
  const { data, isLoading } = useFuncionarios(incluirArquivados);
  const [criando, setCriando] = useState(false);

  const podeCadastrar = sessao?.permissoes.cadastros ?? false;
  const total = (data?.itens ?? []).reduce((a, f) => a + Number(f.valor_mensal), 0);

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-[30px] pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Gestão"
        titulo="Funcionários"
        apoio={
          <>
            Folha mensal de{" "}
            <strong className="font-semibold text-[var(--ink-600)] dark:text-[var(--fg)]">
              {dinheiro(total)}
            </strong>{" "}
            no mundo selecionado. Bônus e vales entram como lançamentos avulsos na mesma
            subcategoria e somam ao custo.
          </>
        }
        acoes={
          <>
            <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-suave">
              <Checkbox
                checked={incluirArquivados}
                onCheckedChange={(v) => setIncluirArquivados(Boolean(v))}
              />
              Mostrar arquivados
            </label>
            {podeCadastrar ? (
              <Button size="sm" onClick={() => setCriando(true)}>
                <Plus size={15} />
                Novo funcionário
              </Button>
            ) : null}
          </>
        }
      />

      <Quadro>
        {isLoading ? (
          <div className="flex flex-col gap-2 p-4">
            {[0, 1].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-[10px] bg-[var(--bg-subtle)]" />
            ))}
          </div>
        ) : (data?.itens.length ?? 0) === 0 ? (
          <EstadoVazio
            titulo="Nenhum funcionário neste mundo"
            descricao="O funcionário pertence a um mundo e não muda de mundo. Se você espera ver alguém aqui, confira o seletor no topo."
          />
        ) : (
          <ul>
            {data!.itens.map((f) => (
              <li key={f.id}>
                <Link
                  href={`/funcionarios/${f.id}`}
                  className="flex flex-wrap items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-3 no-underline transition-colors last:border-b-0 hover:bg-[var(--linha-hover)]"
                >
                  <span className="flex size-9 flex-none items-center justify-center rounded-[10px] bg-[var(--st-programado-bg)] font-[family-name:var(--font-display)] text-[12px] font-extrabold text-[var(--st-programado-fg)]">
                    {iniciais(f.nome)}
                  </span>
                  <span className="flex min-w-[200px] flex-1 flex-col">
                    <span className="flex items-center gap-2">
                      <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
                        {f.nome}
                      </span>
                      <BadgeMundo mundo={f.mundo} />
                      {f.arquivado_em ? (
                        <span className="rounded-full bg-[var(--bg-muted)] px-2 py-[1px] text-[10px] font-bold text-suave">
                          arquivado
                        </span>
                      ) : null}
                    </span>
                    <span className="text-[11.5px] text-sutil">{f.funcao ?? "—"}</span>
                  </span>

                  <span className="w-[110px] text-[12px] text-suave">
                    {f.tipo_contratacao === "pj" ? "PJ" : "Freelancer"}
                  </span>

                  <span className="flex w-[150px] flex-col items-end">
                    <span className="numerico text-[13.5px] font-bold text-[var(--despesa-fg)]">
                      {dinheiro(f.valor_mensal)}
                    </span>
                    <span className="text-[10.5px] text-sutil">todo dia {f.dia_pagamento}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Quadro>

      <FormFuncionario aberta={criando} funcionario={null} aoFechar={() => setCriando(false)} />
    </div>
  );
}
