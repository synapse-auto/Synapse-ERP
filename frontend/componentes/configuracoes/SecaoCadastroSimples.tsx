"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Quadro } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { Button } from "@/componentes/ui/button";
import { Input } from "@/componentes/ui/input";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { api, mensagemDoErro } from "@/lib/api";
import type { Mundo } from "@/lib/tipos";

/**
 * Serviços, centros de custo e tags — três cadastros com a mesma forma
 * (contracts/cadastros.md §5, §6, §7).
 *
 * Um componente só, porque a diferença entre eles é de campo, não de
 * comportamento. Serviços e centros de custo têm mundo; tags não têm mundo,
 * têm cor, e **podem ser criadas por operador** (`RN-14`).
 *
 * Serviços e centros de custo **arquivam**; tag é o único cadastro com
 * `DELETE` de verdade — e ele remove só os vínculos, nunca o lançamento.
 */

interface Item {
  id: string;
  nome: string;
  mundo?: Mundo;
  cor?: string | null;
  arquivado_em?: string | null;
  /** Serviço não tem `arquivado_em` — tem `ativo`. Os dois querem dizer o mesmo aqui. */
  ativo?: boolean;
}

/** Um item arquivado, seja qual for o nome do campo no recurso. */
function estaArquivado(i: Item): boolean {
  return Boolean(i.arquivado_em) || i.ativo === false;
}

export function SecaoCadastroSimples({
  titulo,
  descricao,
  recurso,
  comMundo = false,
  comCor = false,
  podeEscrever,
  podeCriarSendoOperador = false,
}: {
  titulo: string;
  descricao: string;
  recurso: "servicos" | "centros-custo" | "tags";
  comMundo?: boolean;
  comCor?: boolean;
  podeEscrever: boolean;
  podeCriarSendoOperador?: boolean;
}) {
  const cliente = useQueryClient();
  const [nome, setNome] = useState("");
  const [mundo, setMundo] = useState<Mundo>("digital");
  const [cor, setCor] = useState("#8B6CF0");

  // Aqui a lista traz **também os arquivados**, ao contrário da leitura que alimenta o
  // formulário de lançamento. Esta é a tela de gestão do cadastro: sem os arquivados, o
  // selo "arquivado" nunca aparecia e não havia de onde clicar em "desarquivar".
  // Serviço usa `incluir_inativos` porque o campo lá é `ativo` (contracts/cadastros.md §5).
  const { data, isLoading } = useQuery<{ itens: Item[] }>({
    queryKey: [recurso, "config"],
    queryFn: () =>
      api.get<{ itens: Item[] }>(`/api/${recurso}`, {
        consulta: {
          mundo: "ambos",
          ...(recurso === "servicos" ? { incluir_inativos: true } : {}),
          ...(recurso === "centros-custo" ? { incluir_arquivados: true } : {}),
        },
      }),
  });

  function invalidar() {
    cliente.invalidateQueries({ queryKey: [recurso, "config"] });
    cliente.invalidateQueries({ queryKey: [recurso === "centros-custo" ? "centros-custo" : recurso] });
  }

  const criar = useMutation({
    mutationFn: () =>
      api.post(`/api/${recurso}`, {
        corpo: comCor ? { nome: nome.trim(), cor } : { nome: nome.trim(), mundo },
      }),
    onSuccess: () => {
      invalidar();
      setNome("");
      toast.success("Cadastro criado.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const arquivar = useMutation({
    mutationFn: (id: string) => api.post(`/api/${recurso}/${id}/arquivar`),
    onSuccess: () => {
      invalidar();
      toast.success("Arquivado.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const desarquivar = useMutation({
    mutationFn: (id: string) => api.post(`/api/${recurso}/${id}/desarquivar`),
    onSuccess: () => {
      invalidar();
      toast.success("De volta à lista.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const excluir = useMutation({
    mutationFn: (id: string) => api.delete(`/api/${recurso}/${id}`),
    onSuccess: () => {
      invalidar();
      toast.success("Tag excluída. Os lançamentos ficaram; só o vínculo saiu.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const podeCriar = podeEscrever || podeCriarSendoOperador;

  return (
    <Quadro>
      <div className="flex flex-col gap-1 border-b border-linha-suave px-4 py-3">
        <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
          {titulo}
        </span>
        <span className="text-[12px] text-suave">{descricao}</span>
      </div>

      {podeCriar ? (
        <div className="flex flex-wrap items-center gap-2 border-b border-linha-suave bg-[var(--superficie-lateral)] px-4 py-3">
          <Input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome"
            className="max-w-[280px]"
            onKeyDown={(e) => {
              if (e.key === "Enter" && nome.trim()) criar.mutate();
            }}
          />
          {comMundo ? (
            <select
              aria-label="Mundo"
              value={mundo}
              onChange={(e) => setMundo(e.target.value as Mundo)}
              className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
            >
              <option value="digital">Digital</option>
              <option value="infra">Infra</option>
            </select>
          ) : null}
          {comCor ? (
            <input
              type="color"
              aria-label="Cor"
              value={cor}
              onChange={(e) => setCor(e.target.value)}
              className="h-9 w-12 cursor-pointer rounded-[10px] border border-linha-controle bg-superficie-cartao p-1"
            />
          ) : null}
          <Button size="sm" disabled={!nome.trim() || criar.isPending} onClick={() => criar.mutate()}>
            <Plus size={15} />
            Adicionar
          </Button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-2 p-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded-[10px] bg-[var(--bg-subtle)]" />
          ))}
        </div>
      ) : (data?.itens.length ?? 0) === 0 ? (
        <EstadoVazio titulo="Nada cadastrado ainda" compacto />
      ) : (
        <ul>
          {data!.itens.map((i) => (
            <li
              key={i.id}
              className="flex items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-2.5 last:border-b-0"
            >
              {comCor ? (
                <span
                  aria-hidden
                  className="size-[10px] flex-none rounded-[3px]"
                  style={{ background: i.cor ?? "var(--fg-subtle)" }}
                />
              ) : null}
              <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--fg)]">{i.nome}</span>
              {i.mundo ? <BadgeMundo mundo={i.mundo} /> : null}
              {estaArquivado(i) ? (
                <span className="rounded-full bg-[var(--bg-muted)] px-2 py-[1px] text-[10px] text-suave">
                  arquivado
                </span>
              ) : null}
              {podeEscrever ? (
                recurso === "tags" ? (
                  <button
                    type="button"
                    aria-label={`Excluir ${i.nome}`}
                    onClick={() => excluir.mutate(i.id)}
                    className="rounded-[7px] p-1.5 text-suave hover:bg-[var(--st-atrasado-bg)] hover:text-[var(--st-atrasado-fg)]"
                  >
                    <Trash2 size={15} />
                  </button>
                ) : estaArquivado(i) ? (
                  <button
                    type="button"
                    aria-label={`Desarquivar ${i.nome}`}
                    onClick={() => desarquivar.mutate(i.id)}
                    className="rounded-[7px] p-1.5 text-suave hover:bg-[var(--bg-subtle)]"
                  >
                    <ArchiveRestore size={15} />
                  </button>
                ) : (
                  <button
                    type="button"
                    aria-label={`Arquivar ${i.nome}`}
                    onClick={() => arquivar.mutate(i.id)}
                    className="rounded-[7px] p-1.5 text-suave hover:bg-[var(--bg-subtle)]"
                  >
                    <Archive size={15} />
                  </button>
                )
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Quadro>
  );
}
