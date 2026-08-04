"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, TrendingDown, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/componentes/ui/popover";
import { ScrollArea } from "@/componentes/ui/scroll-area";
import { Button } from "@/componentes/ui/button";
import { IconeSino } from "@/componentes/comum/icones";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { api } from "@/lib/api";
import { chaves, useNotificacoes, useSessao } from "@/lib/consultas";
import { instante } from "@/lib/formato";
import type { Notificacao, TipoNotificacao } from "@/lib/tipos";

/**
 * Sino e painel de notificações (T159 e T195, `FR-096`–`FR-100`).
 *
 * O contador de não lidas vem em dois lugares — `GET /api/sessao` e
 * `GET /api/notificacoes` — e a fonte que vale enquanto o painel está aberto
 * é a lista, porque é ela que muda quando se marca como lida.
 *
 * **Não existe criação de notificação pela interface**: elas nascem das
 * rotinas (contracts/plataforma.md §4). O que o usuário faz aqui é ler.
 */

const ICONE: Record<TipoNotificacao, typeof AlertTriangle> = {
  vencimento: CalendarClock,
  inadimplencia: AlertTriangle,
  resumo_semanal: Wallet,
  caixa_baixo: TrendingDown,
};

const COR: Record<TipoNotificacao, string> = {
  vencimento: "var(--st-programado-fg)",
  inadimplencia: "var(--st-atrasado-fg)",
  resumo_semanal: "var(--brand-hover)",
  caixa_baixo: "var(--st-pendente-fg)",
};

const FUNDO: Record<TipoNotificacao, string> = {
  vencimento: "var(--st-programado-bg)",
  inadimplencia: "var(--st-atrasado-bg)",
  resumo_semanal: "var(--brand-tint-2)",
  caixa_baixo: "var(--st-pendente-bg)",
};

export function SinoNotificacoes({ className }: { className?: string }) {
  const [aberto, setAberto] = useState(false);
  const router = useRouter();
  const cliente = useQueryClient();
  const { data: sessao } = useSessao();
  const { data, isLoading } = useNotificacoes(false);

  const naoLidas = data?.nao_lidas ?? sessao?.notificacoes_nao_lidas ?? 0;

  const marcarUma = useMutation({
    mutationFn: (id: string) => api.post(`/api/notificacoes/${id}/marcar-lida`),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ["notificacoes"] });
      cliente.invalidateQueries({ queryKey: chaves.sessao });
    },
  });

  const marcarTodas = useMutation({
    mutationFn: () => api.post("/api/notificacoes/marcar-todas-lidas"),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ["notificacoes"] });
      cliente.invalidateQueries({ queryKey: chaves.sessao });
    },
  });

  function abrirOrigem(n: Notificacao) {
    if (!n.lida_em) marcarUma.mutate(n.id);
    setAberto(false);
    if (n.lancamento_id) router.push(`/lancamentos?selecionado=${n.lancamento_id}`);
    else if (n.cliente_id) router.push(`/clientes/${n.cliente_id}`);
  }

  return (
    <Popover open={aberto} onOpenChange={setAberto}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={
            naoLidas > 0 ? `Notificações — ${naoLidas} não lidas` : "Notificações — nenhuma nova"
          }
          className={cn(
            "relative flex size-9 flex-none items-center justify-center rounded-[8px]",
            "border border-linha-controle bg-superficie-cartao text-[var(--fg-muted)]",
            "transition-colors hover:bg-[var(--bg-subtle)] hover:text-[var(--ink-600)]",
            className,
          )}
        >
          <IconeSino tamanho={17} />
          {naoLidas > 0 ? (
            <span
              className={cn(
                "absolute -top-[3px] -right-[3px] flex h-4 min-w-4 items-center justify-center rounded-full px-1",
                "border-2 border-superficie-cartao bg-[var(--danger-500)] text-white",
                "font-[family-name:var(--font-display)] text-[10px] font-extrabold",
              )}
            >
              {naoLidas > 99 ? "99+" : naoLidas}
            </span>
          ) : null}
        </button>
      </PopoverTrigger>

      {/* No celular o painel não pode ser mais largo que a tela. */}
      <PopoverContent
        align="end"
        collisionPadding={12}
        className="w-[min(400px,calc(100vw-24px))] p-0"
      >
        <header className="flex items-center justify-between gap-2 border-b border-linha-suave px-4 py-3">
          <div className="flex flex-col">
            <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
              Notificações
            </span>
            <span className="text-[12px] text-sutil">
              {naoLidas > 0 ? `${naoLidas} não lidas` : "Tudo lido"}
            </span>
          </div>
          {naoLidas > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => marcarTodas.mutate()}
              disabled={marcarTodas.isPending}
            >
              Marcar todas
            </Button>
          ) : null}
        </header>

        <ScrollArea className="max-h-[420px]">
          {isLoading ? (
            <div className="flex flex-col gap-3 p-4">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded-[8px] bg-[var(--bg-subtle)]" />
              ))}
            </div>
          ) : (data?.itens.length ?? 0) === 0 ? (
            <EstadoVazio
              titulo="Nenhum aviso"
              descricao="Contas a vencer, clientes em atraso e o resumo de segunda aparecem aqui."
              compacto
            />
          ) : (
            <ul className="flex flex-col">
              {data!.itens.map((n) => {
                const Icone = ICONE[n.tipo] ?? AlertTriangle;
                return (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => abrirOrigem(n)}
                      className={cn(
                        "flex w-full items-start gap-3 border-b border-linha-suave px-4 py-3 text-left last:border-b-0",
                        "transition-colors hover:bg-[var(--bg-subtle)]",
                        !n.lida_em && "bg-[var(--brand-tint)]",
                      )}
                    >
                      <span
                        className="mt-[2px] flex size-8 flex-none items-center justify-center rounded-[8px]"
                        style={{ background: FUNDO[n.tipo], color: COR[n.tipo] }}
                      >
                        <Icone size={16} strokeWidth={2} />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                        <span className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate font-[family-name:var(--font-display)] text-[13px] font-bold text-[var(--fg)]">
                            {n.titulo}
                          </span>
                          {n.mundo ? <BadgeMundo mundo={n.mundo} /> : null}
                        </span>
                        <span className="text-[12px] text-suave">{n.corpo}</span>
                        <span className="text-[11px] text-sutil">{instante(n.criado_em)}</span>
                      </span>
                      {!n.lida_em ? (
                        <span
                          role="img"
                          aria-label="Não lida"
                          className="mt-2 size-[7px] flex-none rounded-full bg-[var(--brand)]"
                        />
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
