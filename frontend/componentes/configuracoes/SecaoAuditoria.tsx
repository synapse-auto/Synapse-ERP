"use client";

import { useQuery } from "@tanstack/react-query";
import { Quadro } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { LinhaDoTempo } from "@/componentes/lancamentos/LinhaDoTempo";
import { api } from "@/lib/api";
import { chaves } from "@/lib/consultas";
import type { EventoAuditoria } from "@/lib/tipos";

/**
 * Auditoria geral (`FR-103`, `SC-014`).
 *
 * Somente leitura — não há escrita nem exclusão pela API. O modo geral, com
 * filtros de usuário e período, é de gestor; o operador vê a linha do tempo
 * de um registro pelo painel de detalhe do lançamento.
 */
export function SecaoAuditoria({ ehGestor }: { ehGestor: boolean }) {
  const { data, isLoading } = useQuery<{ itens: EventoAuditoria[] }>({
    queryKey: chaves.auditoria({ geral: true }),
    queryFn: () => api.get<{ itens: EventoAuditoria[] }>("/api/auditoria", { consulta: { por_pagina: 60 } }),
    enabled: ehGestor,
  });

  if (!ehGestor) {
    return (
      <Quadro>
        <EstadoVazio
          titulo="A visão geral da auditoria é de gestor"
          descricao="O histórico de cada lançamento continua disponível para você, no painel de detalhe."
        />
      </Quadro>
    );
  }

  return (
    <Quadro>
      <div className="flex flex-col gap-1 border-b border-linha-suave px-4 py-3">
        <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
          Últimas alterações
        </span>
        <span className="text-[12px] text-suave">
          Quem fez, o quê e quando. Edição de ocorrência passada já efetivada aparece marcada como
          alteração histórica.
        </span>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2 p-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-14 animate-pulse rounded-[8px] bg-[var(--bg-subtle)]" />
          ))}
        </div>
      ) : (data?.itens.length ?? 0) === 0 ? (
        <EstadoVazio titulo="Nenhuma alteração registrada" compacto />
      ) : (
        <div className="p-4">
          <LinhaDoTempo eventos={data!.itens} />
        </div>
      )}
    </Quadro>
  );
}
