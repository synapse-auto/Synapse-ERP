"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Quadro } from "@/componentes/comum/CabecalhoTela";
import { Button } from "@/componentes/ui/button";
import { Input } from "@/componentes/ui/input";
import { Switch } from "@/componentes/ui/switch";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { api, ErroApi, mensagemDoErro } from "@/lib/api";
import { chaves, useConfiguracoes } from "@/lib/consultas";
import type { RespostaConfiguracoes } from "@/lib/tipos";

/**
 * Parâmetros do sistema (`FR-105`, `FR-106`, `RNF-02`).
 *
 * A tela é **gerada a partir da resposta**: cada chave vira um campo, o tipo
 * do campo vem do tipo do valor e o texto de ajuda é a `descricao` que veio
 * do banco. Não existe lista de chaves escrita aqui — chave nova no banco
 * aparece na tela sem deploy, que é o ponto inteiro de `RNF-02`.
 *
 * Mudar `inadimplencia_dias_tolerancia` **reavalia os clientes na hora**, e a
 * resposta diz quantos mudaram de situação. Esse número aparece no aviso.
 */
export function SecaoParametros({ podeEscrever }: { podeEscrever: boolean }) {
  const { data, isLoading } = useConfiguracoes();
  const cliente = useQueryClient();
  const [rascunho, setRascunho] = useState<Record<string, unknown>>({});

  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      api.put<RespostaConfiguracoes>("/api/configuracoes", { corpo }),
    onSuccess: (r) => {
      cliente.invalidateQueries({ queryKey: chaves.configuracoes });
      cliente.invalidateQueries({ queryKey: ["dashboard"] });
      cliente.invalidateQueries({ queryKey: ["clientes"] });
      setRascunho({});
      const efeitos = r.efeitos ?? {};
      const partes = Object.entries(efeitos).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`);
      toast.success("Configurações salvas.", {
        description: partes.length ? partes.join(" · ") : undefined,
      });
    },
    onError: (e) => toast.error(e instanceof ErroApi ? e.message : mensagemDoErro(e)),
  });

  if (isLoading) {
    return <div className="h-[420px] animate-pulse rounded-[14px] bg-[var(--bg-subtle)]" />;
  }
  if (!data || Object.keys(data).length === 0) {
    return (
      <Quadro>
        <EstadoVazio titulo="Nenhuma configuração devolvida pelo servidor" />
      </Quadro>
    );
  }

  const alterado = Object.keys(rascunho).length > 0;

  function valorAtual(chave: string): unknown {
    return chave in rascunho ? rascunho[chave] : data![chave].valor;
  }

  function mudar(chave: string, valor: unknown) {
    setRascunho((r) => ({ ...r, [chave]: valor }));
  }

  return (
    <>
      <Quadro>
        {Object.entries(data).map(([chave, cfg]) => {
          const v = valorAtual(chave);
          const rotulo = chave.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

          return (
            <div
              key={chave}
              className="flex flex-wrap items-start gap-4 border-b border-[var(--linha-suave)] px-4 py-3.5 last:border-b-0"
            >
              <div className="flex min-w-[260px] flex-1 flex-col gap-1">
                <span className="text-[13px] font-semibold text-[var(--fg)]">{rotulo}</span>
                {/* `descricao` vem do banco — é o texto de ajuda de `FR-106` */}
                <span className="max-w-[70ch] text-[11.5px] leading-[1.5] text-suave">
                  {cfg.descricao}
                </span>
                <code className="font-mono text-[10px] text-sutil">{chave}</code>
              </div>

              <div className="flex w-[260px] justify-end">
                {typeof v === "boolean" ? (
                  <Switch
                    checked={v}
                    disabled={!podeEscrever}
                    onCheckedChange={(x) => mudar(chave, x)}
                  />
                ) : typeof v === "number" ? (
                  <Input
                    type="number"
                    value={String(v)}
                    disabled={!podeEscrever}
                    onChange={(e) => mudar(chave, Number(e.target.value))}
                    className="numerico w-[120px] text-right"
                  />
                ) : typeof v === "string" ? (
                  <Input
                    value={v}
                    disabled={!podeEscrever}
                    onChange={(e) => mudar(chave, e.target.value)}
                  />
                ) : (
                  // Listas e objetos (multiplicadores, dias de alerta, catálogo
                  // de cards) são editados como JSON: são estrutura, e inventar
                  // um formulário por formato daria mais chance de erro que de
                  // ajuda.
                  <textarea
                    value={JSON.stringify(v, null, 0)}
                    disabled={!podeEscrever}
                    onChange={(e) => {
                      try {
                        mudar(chave, JSON.parse(e.target.value));
                      } catch {
                        /* JSON incompleto enquanto digita — ignorado */
                      }
                    }}
                    rows={2}
                    className="w-full rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 py-1.5 font-mono text-[11px] outline-none disabled:opacity-60"
                  />
                )}
              </div>
            </div>
          );
        })}
      </Quadro>

      {podeEscrever ? (
        <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-[12px] border border-linha-chrome bg-superficie-cartao px-4 py-3 shadow-[var(--shadow-md)]">
          <span className="mr-auto text-[12px] text-sutil">
            {alterado
              ? `${Object.keys(rascunho).length} ${Object.keys(rascunho).length === 1 ? "alteração pendente" : "alterações pendentes"}`
              : "Nada alterado"}
          </span>
          <Button variant="outline" disabled={!alterado} onClick={() => setRascunho({})}>
            Descartar
          </Button>
          <Button disabled={!alterado || salvar.isPending} onClick={() => salvar.mutate(rascunho)}>
            Salvar
          </Button>
        </div>
      ) : (
        <p className="px-1 text-[11.5px] text-sutil">
          Somente leitura: alterar parâmetros é do gestor. O servidor recusa a escrita mesmo que
          este formulário fosse habilitado.
        </p>
      )}
    </>
  );
}
