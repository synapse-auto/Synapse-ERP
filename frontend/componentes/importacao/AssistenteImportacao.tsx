"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/componentes/ui/dialog";
import { Button } from "@/componentes/ui/button";
import { Label } from "@/componentes/ui/label";
import { Progress } from "@/componentes/ui/progress";
import { PontoMundo } from "@/componentes/comum/BadgeMundo";
import { api, mensagemDoErro } from "@/lib/api";
import { useCategorias, useInvalidarFinanceiro } from "@/lib/consultas";
import { useEstadoGlobal } from "@/lib/estado-global";
import type { Importacao, Mundo, PreviaMapeamento, ProgressoImportacao } from "@/lib/tipos";

/**
 * Assistente de importação CSV/OFX (T198, `FR-044`).
 *
 * Três etapas, que são as três requisições do contrato:
 *
 * 1. **enviar** — `POST /api/importacoes` lê o arquivo e **não grava**;
 * 2. **mapear** — coluna→campo, mundo obrigatório e o de-para de categorias;
 * 3. **confirmar** — grava em lotes com cursor, com barra de progresso.
 *
 * Duas regras que a tela precisa respeitar sem torcer:
 *
 * - **`mundo` é obrigatório** no mapeamento. Arquivo importado não traz mundo
 *   e `RN-15` não admite nulo.
 * - **A sugestão de categoria sugere, não aplica.** Cada texto não
 *   reconhecido vem com a categoria mais parecida; quem aceita é a pessoa.
 *   Gravar a adivinhação contaminaria DRE, relatório e Dashboard com um erro
 *   invisível.
 *
 * A importação vale 24 horas. Passado o prazo, mapear e confirmar respondem
 * `409` mandando enviar de novo — e a mensagem que aparece é a do servidor.
 */

type Etapa = "enviar" | "mapear" | "gravando" | "pronto";

export function AssistenteImportacao({
  aberto,
  aoFechar,
}: {
  aberto: boolean;
  aoFechar: () => void;
}) {
  const entrada = useRef<HTMLInputElement>(null);
  const mundoGlobal = useEstadoGlobal((e) => e.mundo);
  const { data: categorias } = useCategorias();
  const invalidar = useInvalidarFinanceiro();

  const [etapa, setEtapa] = useState<Etapa>("enviar");
  const [ocupado, setOcupado] = useState(false);
  const [importacao, setImportacao] = useState<Importacao | null>(null);
  const [previa, setPrevia] = useState<PreviaMapeamento | null>(null);
  const [mundo, setMundo] = useState<Mundo>(mundoGlobal === "ambos" ? "digital" : mundoGlobal);
  const [mapa, setMapa] = useState<Record<string, string>>({});
  const [dePara, setDePara] = useState<Record<string, string>>({});
  const [progresso, setProgresso] = useState<ProgressoImportacao | null>(null);

  useEffect(() => {
    if (aberto) return;
    setEtapa("enviar");
    setImportacao(null);
    setPrevia(null);
    setMapa({});
    setDePara({});
    setProgresso(null);
  }, [aberto]);

  async function enviarArquivo(arquivo: File) {
    setOcupado(true);
    try {
      const dados = new FormData();
      dados.append("arquivo", arquivo);
      const r = await api.post<Importacao>("/api/importacoes", { formulario: dados });
      setImportacao(r);
      // Palpite de mapeamento por nome de coluna; a pessoa confere e corrige.
      const inicial: Record<string, string> = {};
      for (const c of r.colunas_detectadas) {
        const n = c.toLowerCase();
        if (/data|date/.test(n)) inicial[c] = "data";
        else if (/desc|hist|memo|lan[çc]/.test(n)) inicial[c] = "descricao";
        else if (/valor|amount|montante/.test(n)) inicial[c] = "valor";
        else if (/categ/.test(n)) inicial[c] = "categoria";
        else if (/tipo/.test(n)) inicial[c] = "tipo";
      }
      setMapa(inicial);
      setEtapa("mapear");
    } catch (e) {
      toast.error(mensagemDoErro(e));
    } finally {
      setOcupado(false);
    }
  }

  async function mapear() {
    if (!importacao) return;
    setOcupado(true);
    try {
      const r = await api.post<PreviaMapeamento>(
        `/api/importacoes/${importacao.importacao_id}/mapeamento`,
        { corpo: { mundo, colunas: mapa, categorias: dePara } },
      );
      setPrevia(r);
    } catch (e) {
      toast.error(mensagemDoErro(e));
    } finally {
      setOcupado(false);
    }
  }

  async function confirmar() {
    if (!importacao) return;
    setEtapa("gravando");
    let cursor: string | null = null;
    try {
      // Grava em lotes com cursor, como as recorrências longas: uma invocação
      // da função não dá conta de um arquivo grande, e a barra existe
      // justamente para a interface não travar.
      for (;;) {
        const r: ProgressoImportacao = await api.post<ProgressoImportacao>(
          `/api/importacoes/${importacao.importacao_id}/confirmar`,
          { corpo: { cursor } },
        );
        setProgresso(r);
        if (r.concluida) break;
        cursor = r.cursor;
      }
      invalidar();
      setEtapa("pronto");
    } catch (e) {
      toast.error(mensagemDoErro(e));
      setEtapa("mapear");
    }
  }

  const naoReconhecidas = previa?.resumo.categorias_nao_reconhecidas ?? [];
  const podeConfirmar = Boolean(previa && previa.resumo.validas > 0);

  return (
    <Dialog open={aberto} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-[760px]">
        <DialogHeader>
          <DialogTitle>Importar CSV ou OFX</DialogTitle>
          <DialogDescription>
            O arquivo é lido, conferido e só grava quando você confirmar. Nada é gravado nas duas
            primeiras etapas.
          </DialogDescription>
        </DialogHeader>

        <ol className="flex items-center gap-2 text-[12px]">
          {(
            [
              ["enviar", "1 · Enviar"],
              ["mapear", "2 · Conferir"],
              ["pronto", "3 · Gravar"],
            ] as const
          ).map(([chave, rotulo], i) => {
            const indice = ["enviar", "mapear", "gravando", "pronto"].indexOf(etapa);
            const meu = ["enviar", "mapear", "pronto"].indexOf(chave);
            const feito = meu < (indice === 2 ? 2 : indice);
            const atual = chave === etapa || (chave === "pronto" && etapa === "gravando");
            return (
              <li key={chave} className="flex items-center gap-2">
                {i > 0 ? <span className="h-px w-6 bg-linha-suave" /> : null}
                <span
                  className={cn(
                    "rounded-full px-2.5 py-1 font-[family-name:var(--font-display)] font-semibold",
                    atual
                      ? "bg-[var(--brand-tint-2)] text-[var(--lateral-ativo-fg)]"
                      : feito
                        ? "bg-[var(--receita-bg)] text-[var(--receita-fg)]"
                        : "bg-[var(--bg-subtle)] text-sutil",
                  )}
                >
                  {rotulo}
                </span>
              </li>
            );
          })}
        </ol>

        {etapa === "enviar" ? (
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (e.dataTransfer.files[0]) void enviarArquivo(e.dataTransfer.files[0]);
            }}
            className="flex flex-col items-center gap-3 rounded-[12px] border border-dashed border-linha-controle bg-[var(--bg-subtle)] px-6 py-12 text-center"
          >
            <Upload size={22} className="text-suave" />
            <p className="text-[13px] text-suave">
              Arraste o extrato aqui ou{" "}
              <button
                type="button"
                onClick={() => entrada.current?.click()}
                className="font-semibold text-[var(--brand-hover)] underline underline-offset-2"
              >
                escolha o arquivo
              </button>
            </p>
            <p className="max-w-[52ch] text-[12px] text-sutil">
              CSV e OFX. A leitura de OFX é feita sem biblioteca externa por causa do tamanho da
              função — um arquivo malformado pode ser recusado, e nesse caso o CSV resolve.
            </p>
            {ocupado ? <Loader2 size={16} className="animate-spin text-suave" /> : null}
            <input
              ref={entrada}
              type="file"
              accept=".csv,.ofx,text/csv"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) void enviarArquivo(e.target.files[0]);
                e.target.value = "";
              }}
            />
          </div>
        ) : null}

        {etapa === "mapear" && importacao ? (
          <div className="flex flex-col gap-5">
            <p className="text-[13px] text-suave">
              <strong className="text-[var(--fg)]">{importacao.nome_arquivo}</strong> ·{" "}
              {importacao.total_linhas} linhas
            </p>

            {/* Mundo — obrigatório */}
            <div className="flex flex-col gap-2 rounded-[10px] border border-linha-suave bg-[var(--bg-subtle)] p-4">
              <Label>Mundo destes lançamentos</Label>
              <div className="flex gap-2">
                {(["digital", "infra"] as Mundo[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMundo(m)}
                    className="flex h-9 items-center gap-2 rounded-[8px] border px-3 font-[family-name:var(--font-display)] text-[13px] font-bold"
                    style={
                      mundo === m
                        ? {
                            background: `var(--mundo-${m}-bg)`,
                            color: `var(--mundo-${m}-fg)`,
                            borderColor: `var(--mundo-${m})`,
                          }
                        : { borderColor: "var(--linha-controle)", color: "var(--fg-muted)" }
                    }
                  >
                    <PontoMundo mundo={m} className="size-[7px]" />
                    {m === "digital" ? "Synapse Digital" : "Synapse Infra"}
                  </button>
                ))}
              </div>
              <p className="text-[12px] text-sutil">
                Obrigatório: o arquivo não traz mundo, e lançamento sem mundo não existe.
              </p>
            </div>

            {/* Colunas */}
            <div className="flex flex-col gap-2">
              <span className="rotulo-seccao">Colunas do arquivo</span>
              <div className="grid gap-2 sm:grid-cols-2">
                {importacao.colunas_detectadas.map((c) => (
                  <label key={c} className="flex items-center gap-2 text-[13px]">
                    <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-suave">
                      {c}
                    </span>
                    <select
                      value={mapa[c] ?? ""}
                      onChange={(e) => setMapa((m) => ({ ...m, [c]: e.target.value }))}
                      className="h-8 w-[140px] rounded-[6px] border border-linha-controle bg-superficie-cartao px-2 text-[12px] outline-none"
                    >
                      <option value="">ignorar</option>
                      <option value="data">Data</option>
                      <option value="descricao">Descrição</option>
                      <option value="valor">Valor</option>
                      <option value="tipo">Tipo</option>
                      <option value="categoria">Categoria</option>
                    </select>
                  </label>
                ))}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="self-start"
                disabled={ocupado}
                onClick={() => void mapear()}
              >
                {ocupado ? <Loader2 size={14} className="animate-spin" /> : null}
                Conferir a prévia
              </Button>
            </div>

            {previa ? (
              <>
                <div className="flex gap-4 rounded-[10px] bg-[var(--bg-subtle)] p-4 text-[13px]">
                  <span>
                    <strong className="numerico text-[16px] text-[var(--receita-fg)]">
                      {previa.resumo.validas}
                    </strong>{" "}
                    válidas
                  </span>
                  <span>
                    <strong className="numerico text-[16px] text-[var(--despesa-fg)]">
                      {previa.resumo.invalidas}
                    </strong>{" "}
                    com problema
                  </span>
                </div>

                {naoReconhecidas.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    <span className="rotulo-seccao">Categorias não reconhecidas</span>
                    <p className="text-[12px] text-sutil">
                      A sugestão é só sugestão — nada é aplicado sozinho. Escolha o destino de
                      cada uma; categorias novas não são criadas pela importação.
                    </p>
                    {naoReconhecidas.map((c) => (
                      <div key={c.texto} className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-suave">
                          {c.texto}
                        </span>
                        <select
                          value={dePara[c.texto] ?? c.sugestao_id ?? ""}
                          onChange={(e) =>
                            setDePara((d) => ({ ...d, [c.texto]: e.target.value }))
                          }
                          className="h-8 w-[220px] rounded-[6px] border border-linha-controle bg-superficie-cartao px-2 text-[12px] outline-none"
                        >
                          <option value="">escolha a categoria…</option>
                          {(categorias?.itens ?? []).map((cat) => (
                            <option key={cat.id} value={cat.id}>
                              {cat.nome}
                              {cat.id === c.sugestao_id ? "  (sugerida)" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                ) : null}

                <div className="overflow-x-auto rounded-[10px] border border-linha-suave">
                  <table className="w-full text-[12px]">
                    <thead className="bg-[var(--superficie-lateral)]">
                      <tr>
                        {["#", "Data", "Descrição", "Valor", "Categoria", "Problemas"].map((h) => (
                          <th
                            key={h}
                            className="px-3 py-2 text-left font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.07em] text-sutil uppercase"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previa.linhas.slice(0, 12).map((l) => (
                        <tr
                          key={l.indice}
                          className={cn(
                            "border-t border-linha-suave",
                            l.erros.length > 0 && "bg-[var(--st-atrasado-bg)]",
                          )}
                        >
                          <td className="px-3 py-1.5 text-sutil">{l.indice + 1}</td>
                          <td className="px-3 py-1.5">{l.data ?? "—"}</td>
                          <td className="max-w-[220px] truncate px-3 py-1.5">
                            {l.descricao ?? "—"}
                          </td>
                          <td className="numerico px-3 py-1.5 text-right">{l.valor ?? "—"}</td>
                          <td className="px-3 py-1.5">
                            {l.categoria_texto ?? "—"}
                            {l.categoria_sugerida_nome ? (
                              <span className="text-sutil"> → {l.categoria_sugerida_nome}</span>
                            ) : null}
                          </td>
                          <td className="px-3 py-1.5 text-[var(--despesa-fg)]">
                            {l.erros.join(" · ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </div>
        ) : null}

        {etapa === "gravando" ? (
          <div className="flex flex-col gap-3 py-8">
            <p className="text-center text-[13px] text-suave">
              Gravando em lotes — a interface não trava.
            </p>
            <Progress
              value={
                progresso && progresso.total > 0
                  ? (progresso.gravadas / progresso.total) * 100
                  : 8
              }
            />
            <p className="numerico text-center text-[12px] text-sutil">
              {progresso ? `${progresso.gravadas} de ${progresso.total}` : "iniciando…"}
            </p>
          </div>
        ) : null}

        {etapa === "pronto" ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <p className="font-[family-name:var(--font-display)] text-[16px] font-bold text-forte">
              {progresso?.gravadas ?? 0} lançamentos importados
            </p>
            <p className="max-w-[46ch] text-[13px] text-suave">
              Cada um registrou auditoria com a origem “importação” e o nome do arquivo — a linha
              do tempo não vai dizer que alguém digitou tudo isso à mão.
            </p>
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            {etapa === "pronto" ? "Fechar" : "Cancelar"}
          </Button>
          {etapa === "mapear" ? (
            <Button disabled={!podeConfirmar} onClick={() => void confirmar()}>
              Gravar {previa?.resumo.validas ?? 0} lançamentos
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
