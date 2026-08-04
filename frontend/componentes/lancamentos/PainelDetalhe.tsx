"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Ban,
  CheckCircle2,
  Copy,
  ExternalLink,
  Pencil,
  Scissors,
  Trash2,
} from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/componentes/ui/sheet";
import { Button } from "@/componentes/ui/button";
import { BadgeStatus } from "@/componentes/comum/BadgeStatus";
import { BadgeMundo, NOME_COMPLETO_MUNDO } from "@/componentes/comum/BadgeMundo";
import { DataBR } from "@/componentes/comum/DataBR";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { PainelAnexos } from "./PainelAnexos";
import { DialogoSplit } from "./DialogoSplit";
import { LinhaDoTempo } from "./LinhaDoTempo";
import { useLancamento } from "@/lib/consultas";
import { useCancelar, useDuplicar, useEfetivar, useExcluir } from "./acoes";
import { dinheiro } from "@/lib/formato";
import type { AcaoDisponivel } from "@/lib/tipos";

/**
 * Painel de detalhe (T165, `FR-041`, `FR-042`).
 *
 * Um clique na linha abre este painel; duplo clique abre a edição — é o que
 * a linha de apoio da tela promete.
 *
 * **As ações vêm de `acoes_disponiveis`**, calculado no servidor a partir do
 * status e do papel. O frontend não decide quando mostrar "confirmar
 * recebimento" (`FR-042`); ele desenha o que veio.
 */

const ROTULO_ACAO: Record<AcaoDisponivel, string> = {
  editar: "Editar",
  duplicar: "Duplicar",
  dividir: "Dividir",
  excluir: "Excluir",
  confirmar_efetivacao: "Confirmar",
  cancelar: "Cancelar",
  restaurar: "Restaurar",
};

export function PainelDetalhe({
  id,
  aoFechar,
  aoEditar,
}: {
  id: string | null;
  aoFechar: () => void;
  aoEditar: (id: string) => void;
}) {
  const { data: l, isLoading } = useLancamento(id);
  const [splitAberto, setSplitAberto] = useState(false);

  const efetivar = useEfetivar();
  const cancelar = useCancelar();
  const duplicar = useDuplicar();
  const excluir = useExcluir();

  const acoes = l?.acoes_disponiveis ?? [];
  const pode = (a: AcaoDisponivel) => acoes.includes(a);

  return (
    <Sheet open={Boolean(id)} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto p-0 sm:max-w-[480px]">
        {isLoading || !l ? (
          <div className="flex flex-col gap-4 p-6">
            <div className="h-6 w-2/3 animate-pulse rounded bg-[var(--bg-subtle)]" />
            <div className="h-10 w-1/2 animate-pulse rounded bg-[var(--bg-subtle)]" />
            <div className="h-40 animate-pulse rounded-[10px] bg-[var(--bg-subtle)]" />
          </div>
        ) : (
          <>
            <SheetHeader className="gap-3 border-b border-linha-suave p-6">
              <div className="flex flex-wrap items-center gap-2">
                <BadgeStatus status={l.status} />
                <BadgeMundo mundo={l.mundo} />
                {l.origem.rotulo ? (
                  <span className="rounded-full bg-segmento px-2 py-[3px] text-[11px] text-suave">
                    {l.origem.rotulo}
                  </span>
                ) : null}
              </div>
              <SheetTitle className="text-[19px] leading-[1.25] font-extrabold tracking-[-0.02em]">
                {l.descricao}
              </SheetTitle>
              <SheetDescription asChild>
                <div className="flex items-baseline gap-3">
                  <span
                    className="numerico font-[family-name:var(--font-display)] text-[30px] leading-none font-extrabold tracking-[-0.035em]"
                    style={{
                      color:
                        l.status === "efetivado"
                          ? l.tipo === "receita"
                            ? "var(--receita-fg)"
                            : "var(--despesa-fg)"
                          : "var(--fg-strong)",
                    }}
                  >
                    {l.tipo === "receita" ? "+ " : "− "}
                    {dinheiro(l.valor)}
                  </span>
                  <DataBR valor={l.data} className="text-[13px] text-suave" />
                </div>
              </SheetDescription>

              {l.moeda_origem !== "BRL" ? (
                <p className="rounded-[8px] bg-[var(--receita-bg)] px-3 py-2 text-[12px] text-[var(--receita-fg)]">
                  Original {l.moeda_origem} {l.valor_origem} · cotação {l.cotacao}
                  {l.cotacao_manual ? " (informada à mão)" : ""} na data do lançamento.
                </p>
              ) : null}
            </SheetHeader>

            {/* Ações — exatamente as que o servidor liberou */}
            <div className="flex flex-wrap gap-2 border-b border-linha-suave px-6 py-4">
              {pode("confirmar_efetivacao") ? (
                <Button size="sm" onClick={() => efetivar.mutate(l.id)}>
                  <CheckCircle2 size={15} />
                  {l.tipo === "receita" ? "Confirmar recebimento" : "Confirmar pagamento"}
                </Button>
              ) : null}
              {pode("editar") ? (
                <Button size="sm" variant="outline" onClick={() => aoEditar(l.id)}>
                  <Pencil size={15} />
                  {ROTULO_ACAO.editar}
                </Button>
              ) : null}
              {pode("duplicar") ? (
                <Button size="sm" variant="outline" onClick={() => duplicar.mutate(l.id)}>
                  <Copy size={15} />
                  {ROTULO_ACAO.duplicar}
                </Button>
              ) : null}
              {pode("dividir") ? (
                <Button size="sm" variant="outline" onClick={() => setSplitAberto(true)}>
                  <Scissors size={15} />
                  {ROTULO_ACAO.dividir}
                </Button>
              ) : null}
              {pode("cancelar") ? (
                <Button size="sm" variant="outline" onClick={() => cancelar.mutate(l.id)}>
                  <Ban size={15} />
                  {ROTULO_ACAO.cancelar}
                </Button>
              ) : null}
              {pode("excluir") ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-[var(--danger-500)]"
                  onClick={() => {
                    excluir.mutate(l.id);
                    aoFechar();
                  }}
                >
                  <Trash2 size={15} />
                  {ROTULO_ACAO.excluir}
                </Button>
              ) : null}
              {acoes.length === 0 ? (
                <p className="text-[12px] text-sutil">
                  Nenhuma ação disponível para este lançamento no seu papel.
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-6 p-6">
              <Secao titulo="Classificação">
                <Linha rotulo="Categoria">
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden
                      className="size-[7px] rounded-[2px]"
                      style={{ background: l.categoria.cor ?? "var(--fg-subtle)" }}
                    />
                    {l.categoria.nome}
                    {l.subcategoria ? (
                      <span className="text-suave">· {l.subcategoria.nome}</span>
                    ) : null}
                  </span>
                </Linha>
                <Linha rotulo="Serviço">{l.servico?.nome ?? "—"}</Linha>
                <Linha rotulo="Centro de custo">{l.centro_custo?.nome ?? "Geral"}</Linha>
                <Linha rotulo="Mundo">{NOME_COMPLETO_MUNDO[l.mundo]}</Linha>
                {l.tags.length > 0 ? (
                  <Linha rotulo="Tags">
                    <span className="flex flex-wrap gap-1">
                      {l.tags.map((t) => (
                        <span
                          key={t.id}
                          className="rounded-full bg-segmento px-2 py-[2px] text-[11px] font-semibold"
                          style={{ color: t.cor ?? "var(--fg-muted)" }}
                        >
                          {t.nome}
                        </span>
                      ))}
                    </span>
                  </Linha>
                ) : null}
              </Secao>

              <Secao titulo="Programação">
                <Linha rotulo="Efetivação">
                  {l.efetivar_automaticamente
                    ? "Automática na data — nunca vence"
                    : "Manual — exige confirmação, e por isso pode virar atrasado"}
                </Linha>
                {l.origem.tipo !== "manual" ? (
                  <Linha rotulo="Origem">
                    {l.origem.rotulo ?? l.origem.tipo}
                    {l.origem.tipo === "parcelamento" && l.origem.id ? (
                      <Link
                        href={`/lancamentos?parcelamento=${l.origem.id}`}
                        className="ml-2 inline-flex items-center gap-1 rounded-[4px] px-1 text-[12px] font-medium text-[var(--brand-hover)] underline-offset-2 transition-colors hover:bg-[var(--brand-tint)] hover:underline"
                      >
                        ver a série <ExternalLink size={11} aria-hidden="true" />
                      </Link>
                    ) : null}
                  </Linha>
                ) : null}
                {l.parcela_numero && l.parcela_total ? (
                  <Linha rotulo="Parcela">
                    {l.parcela_numero}/{l.parcela_total}
                  </Linha>
                ) : null}
              </Secao>

              {l.partes_split.length > 0 ? (
                <Secao titulo="Partes">
                  <p className="mb-2 text-[12px] text-sutil">
                    Este lançamento foi dividido: ele saiu dos totais e só as partes contam.
                  </p>
                  {l.partes_split.map((p) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between gap-3 border-b border-linha-suave py-2 last:border-b-0"
                    >
                      <span className="min-w-0 flex-1 truncate text-[13px]">{p.descricao}</span>
                      <span className="text-[12px] text-suave">{p.categoria.nome}</span>
                      <span className="numerico text-[13px] font-semibold">
                        {dinheiro(p.valor)}
                      </span>
                    </div>
                  ))}
                </Secao>
              ) : null}

              {l.lancamento_pai ? (
                <Secao titulo="Parte de um split">
                  <p className="text-[13px] text-suave">
                    Esta linha é parte de{" "}
                    <strong className="text-[var(--fg)]">{l.lancamento_pai.descricao}</strong> (
                    {dinheiro(l.lancamento_pai.valor)}). O comprovante mora no lançamento original.
                  </p>
                </Secao>
              ) : null}

              <Secao titulo="Anexos">
                <PainelAnexos lancamento={l} />
              </Secao>

              {l.observacoes ? (
                <Secao titulo="Observações">
                  <p className="text-[13px] leading-[1.6] text-suave">{l.observacoes}</p>
                </Secao>
              ) : null}

              <Secao titulo="Histórico">
                {l.historico.length === 0 ? (
                  <EstadoVazio titulo="Sem alterações registradas" compacto />
                ) : (
                  <LinhaDoTempo eventos={l.historico} />
                )}
              </Secao>
            </div>

            <DialogoSplit
              lancamento={l}
              aberto={splitAberto}
              aoFechar={() => setSplitAberto(false)}
            />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="rotulo-seccao">{titulo}</h3>
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

function Linha({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-linha-suave py-2 last:border-b-0">
      <span className="flex-none text-[12px] text-sutil">{rotulo}</span>
      <span className="text-right text-[13px] text-[var(--fg)]">{children}</span>
    </div>
  );
}
