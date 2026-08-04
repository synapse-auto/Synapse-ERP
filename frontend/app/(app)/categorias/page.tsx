"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Archive, Pencil, Plus } from "lucide-react";
import { toast } from "sonner";
import { CabecalhoTela, Quadro } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { Button } from "@/componentes/ui/button";
import { Checkbox } from "@/componentes/ui/checkbox";
import { DialogoArquivarCategoria } from "@/componentes/categorias/DialogoArquivarCategoria";
import { FormCategoria } from "@/componentes/categorias/FormCategoria";
import { useCategorias, useInvalidarFinanceiro, useSessao } from "@/lib/consultas";
import { useEscopo } from "@/lib/consultas";
import { api, mensagemDoErro, paraQueryString } from "@/lib/api";
import { dinheiro, inteiro } from "@/lib/formato";
import type { Categoria } from "@/lib/tipos";

/**
 * Categorias (T185, `FR-072`–`FR-079`).
 *
 * A **lista é a mesma nos três mundos** (`FR-006`) — categoria não tem mundo
 * —, mas o `uso` (contagem e total) respeita o mundo ativo (`FR-074`). É por
 * isso que trocar de mundo aqui muda os números e não some com linhas.
 *
 * Arquivar é o único caminho: não existe excluir (`RN-06`). Com lançamentos,
 * o servidor responde `422` e o diálogo pergunta para onde vão.
 */
export default function PaginaCategorias() {
  const router = useRouter();
  const escopo = useEscopo();
  const { data: sessao } = useSessao();
  const [incluirArquivadas, setIncluirArquivadas] = useState(false);
  const { data, isLoading } = useCategorias(incluirArquivadas);
  const invalidar = useInvalidarFinanceiro();

  const [editando, setEditando] = useState<Categoria | null>(null);
  const [criando, setCriando] = useState(false);
  const [arquivando, setArquivando] = useState<Categoria | null>(null);

  const podeEditar = sessao?.permissoes.cadastros ?? false;

  const desarquivar = useMutation({
    mutationFn: (id: string) => api.post(`/api/categorias/${id}/desarquivar`),
    onSuccess: () => {
      invalidar();
      toast.success("Categoria desarquivada.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  function filtrarPor(categoriaId: string) {
    router.push(
      `/lancamentos${paraQueryString({ ...escopo.parametros, categoria_id: categoriaId } as never)}`,
    );
  }

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Estrutura"
        titulo="Categorias"
        apoio="A lista é a mesma nos dois mundos; a contagem e o total respeitam o mundo e o período escolhidos."
        acoes={
          <>
            <label className="flex cursor-pointer items-center gap-2 text-[13px] text-suave">
              <Checkbox
                checked={incluirArquivadas}
                onCheckedChange={(v) => setIncluirArquivadas(Boolean(v))}
              />
              Mostrar arquivadas
            </label>
            {podeEditar ? (
              <Button size="sm" onClick={() => setCriando(true)}>
                <Plus size={15} />
                Nova categoria
              </Button>
            ) : null}
          </>
        }
      />

      <Quadro>
        {isLoading ? (
          <div className="flex flex-col gap-2 p-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded-[8px] bg-[var(--bg-subtle)]" />
            ))}
          </div>
        ) : (data?.itens.length ?? 0) === 0 ? (
          <EstadoVazio
            titulo="Nenhuma categoria"
            descricao="As nove categorias iniciais vêm do seed do banco. Se a lista está vazia, o seed ainda não rodou."
          />
        ) : (
          <ul>
            {data!.itens.map((c) => (
              <li
                key={c.id}
                className="flex flex-wrap items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-3 last:border-b-0"
              >
                <span
                  aria-hidden
                  className="size-[10px] flex-none rounded-[2px]"
                  style={{ background: c.cor ?? "var(--fg-subtle)" }}
                />

                <button
                  type="button"
                  onClick={() => filtrarPor(c.id)}
                  className="flex min-w-[200px] flex-1 flex-col items-start text-left"
                >
                  <span className="flex items-center gap-2">
                    <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
                      {c.nome}
                    </span>
                    {c.especial ? (
                      <span className="rounded-full bg-[var(--brand-tint-2)] px-2 py-[1px] text-[10px] font-bold text-[var(--lateral-ativo-fg)]">
                        especial · {c.vinculo === "cliente" ? "clientes" : "funcionários"}
                      </span>
                    ) : null}
                    {c.arquivada_em ? (
                      <span className="rounded-full bg-[var(--bg-muted)] px-2 py-[1px] text-[10px] font-bold text-suave">
                        arquivada
                      </span>
                    ) : null}
                  </span>
                  <span className="text-[12px] text-sutil">
                    {c.subcategorias.length === 0
                      ? "sem subcategorias"
                      : `${inteiro(c.subcategorias.length)} ${c.subcategorias.length === 1 ? "subcategoria" : "subcategorias"}`}
                  </span>
                </button>

                <span
                  className="rounded-full px-2.5 py-[3px] text-[11px] font-bold"
                  style={{
                    background:
                      c.tipo === "receita"
                        ? "var(--receita-bg)"
                        : c.tipo === "despesa"
                          ? "var(--despesa-bg)"
                          : "var(--bg-muted)",
                    color:
                      c.tipo === "receita"
                        ? "var(--receita-fg)"
                        : c.tipo === "despesa"
                          ? "var(--despesa-fg)"
                          : "var(--fg-muted)",
                  }}
                >
                  {c.tipo === "ambas" ? "Receita e despesa" : c.tipo === "receita" ? "Receita" : "Despesa"}
                </span>

                <span className="w-[110px] text-right text-[12px] text-suave">
                  {inteiro(c.uso.quantidade_lancamentos)} lanç.
                </span>
                <span className="numerico w-[130px] text-right text-[13px] font-semibold text-forte">
                  {dinheiro(c.uso.total_movimentado)}
                </span>

                {podeEditar ? (
                  <span className="flex items-center gap-1">
                    <button
                      type="button"
                      aria-label={`Editar ${c.nome}`}
                      onClick={() => setEditando(c)}
                      className="rounded-[6px] p-1.5 text-suave hover:bg-[var(--bg-subtle)]"
                    >
                      <Pencil size={15} />
                    </button>
                    {c.arquivada_em ? (
                      <Button size="sm" variant="outline" onClick={() => desarquivar.mutate(c.id)}>
                        Desarquivar
                      </Button>
                    ) : (
                      <button
                        type="button"
                        aria-label={`Arquivar ${c.nome}`}
                        onClick={() => setArquivando(c)}
                        className="rounded-[6px] p-1.5 text-suave hover:bg-[var(--bg-subtle)]"
                      >
                        <Archive size={15} />
                      </button>
                    )}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Quadro>

      <FormCategoria
        aberta={criando || Boolean(editando)}
        categoria={editando}
        aoFechar={() => {
          setCriando(false);
          setEditando(null);
        }}
      />

      <DialogoArquivarCategoria
        categoria={arquivando}
        categorias={data?.itens ?? []}
        aoFechar={() => setArquivando(null)}
      />
    </div>
  );
}
