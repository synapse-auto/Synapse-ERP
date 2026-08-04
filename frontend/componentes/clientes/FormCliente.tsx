"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/componentes/ui/dialog";
import { Button } from "@/componentes/ui/button";
import { Input } from "@/componentes/ui/input";
import { Label } from "@/componentes/ui/label";
import { Textarea } from "@/componentes/ui/textarea";
import { Checkbox } from "@/componentes/ui/checkbox";
import { PontoMundo } from "@/componentes/comum/BadgeMundo";
import { Seletor } from "@/componentes/comum/Seletor";
import { api, ErroApi, mensagemDoErro } from "@/lib/api";
import { useInvalidarFinanceiro, useServicos } from "@/lib/consultas";
import type { Cliente, Mundo, TipoCobranca } from "@/lib/tipos";

/**
 * Cadastro de cliente (`FR-080`–`FR-082`).
 *
 * Criar um cliente faz três coisas na mesma transação, do lado do servidor:
 * cria o cliente, cria a **subcategoria espelho** na categoria com
 * `vinculo=cliente` e, se a cobrança for recorrente, cria a **recorrência da
 * mensalidade** no `mundo_cobranca`.
 *
 * `mundo_cobranca` é obrigatório quando a cobrança é recorrente — é o mundo
 * em que a mensalidade vai gerar lançamento, não o mundo do cliente (que não
 * existe).
 *
 * `efetivar_automaticamente` em branco herda a configuração. A escolha muda o
 * alerta de inadimplência: mensalidade automática nunca vence, e por isso
 * nunca aparece como atrasada. A resposta do servidor traz esse aviso pronto.
 */
export function FormCliente({
  aberta,
  cliente,
  aoFechar,
}: {
  aberta: boolean;
  cliente: Cliente | null;
  aoFechar: () => void;
}) {
  const invalidar = useInvalidarFinanceiro();
  const { data: servicos } = useServicos("ambos");

  const [nome, setNome] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [email, setEmail] = useState("");
  const [telefone, setTelefone] = useState("");
  const [tipoCobranca, setTipoCobranca] = useState<TipoCobranca>("pontual");
  const [valor, setValor] = useState("");
  const [dia, setDia] = useState("10");
  const [mundoCobranca, setMundoCobranca] = useState<Mundo>("digital");
  const [servicoIds, setServicoIds] = useState<string[]>([]);
  const [observacoes, setObservacoes] = useState("");
  const [efetivacao, setEfetivacao] = useState<"padrao" | "sim" | "nao">("padrao");
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    if (!aberta) return;
    setErro(null);
    setAviso(null);
    setNome(cliente?.nome ?? "");
    setEmpresa(cliente?.empresa ?? "");
    setEmail(cliente?.contato_email ?? "");
    setTelefone(cliente?.contato_telefone ?? "");
    setTipoCobranca(cliente?.tipo_cobranca ?? "pontual");
    setValor(cliente?.valor_recorrente ?? "");
    setDia(String(cliente?.dia_cobranca ?? 10));
    setMundoCobranca(cliente?.mundo_cobranca ?? "digital");
    setServicoIds(cliente?.servicos.map((s) => s.id) ?? []);
    setObservacoes(cliente?.observacoes ?? "");
    setEfetivacao("padrao");
  }, [aberta, cliente]);

  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      cliente
        ? api.put<Record<string, unknown>>(`/api/clientes/${cliente.id}`, { corpo })
        : api.post<Record<string, unknown>>("/api/clientes", { corpo }),
    onSuccess: (r) => {
      invalidar();
      const rec = (r as { recorrencia?: { aviso_inadimplencia?: string } }).recorrencia;
      if (rec?.aviso_inadimplencia) setAviso(rec.aviso_inadimplencia);
      toast.success(cliente ? "Cliente atualizado." : "Cliente criado.");
      if (!rec?.aviso_inadimplencia) aoFechar();
    },
    onError: (e) => setErro(e instanceof ErroApi ? e.message : mensagemDoErro(e)),
  });

  const recorrente = tipoCobranca === "recorrente";

  return (
    <Dialog open={aberta} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-[620px]">
        <DialogHeader>
          <DialogTitle>{cliente ? "Editar cliente" : "Novo cliente"}</DialogTitle>
          <DialogDescription>
            O cadastro cria a subcategoria do cliente automaticamente — e, se a cobrança for
            recorrente, também a mensalidade.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="nome-cli">Nome</Label>
            <Input
              id="nome-cli"
              name="nome"
              autoComplete="off"
              required
              placeholder="Estrutural Vidros…"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="empresa-cli">Empresa</Label>
            <Input
              id="empresa-cli"
              name="empresa"
              autoComplete="off"
              placeholder="Razão social…"
              value={empresa}
              onChange={(e) => setEmpresa(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email-cli">E-mail</Label>
            <Input
              id="email-cli"
              name="contato_email"
              type="email"
              inputMode="email"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              placeholder="contato@empresa.com.br"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fone-cli">Telefone</Label>
            <Input
              id="fone-cli"
              name="contato_telefone"
              type="tel"
              inputMode="tel"
              autoComplete="off"
              spellCheck={false}
              placeholder="(11) 98888-7777"
              value={telefone}
              onChange={(e) => setTelefone(e.target.value)}
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="cobranca">Cobrança</Label>
          <Seletor
            id="cobranca"
            nome="tipo_cobranca"
            valor={tipoCobranca}
            aoMudar={(v) => setTipoCobranca(v as TipoCobranca)}
            opcoes={[
              { valor: "pontual", rotulo: "Pontual — por projeto" },
              { valor: "recorrente", rotulo: "Recorrente — mensalidade" },
              { valor: "parcelada", rotulo: "Parcelada" },
            ]}
          />
        </div>

        {recorrente ? (
          <div className="flex flex-col gap-4 rounded-[10px] border border-linha-suave bg-[var(--bg-subtle)] p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="valor-cli">Valor mensal</Label>
                <Input
                  id="valor-cli"
                  inputMode="decimal"
                  className="numerico"
                  value={valor}
                  onChange={(e) => setValor(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="dia-cli">Dia da cobrança</Label>
                <Input
                  id="dia-cli"
                  type="number"
                  min={1}
                  max={31}
                  value={dia}
                  onChange={(e) => setDia(e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Mundo da cobrança</span>
              <div role="radiogroup" aria-label="Mundo da cobrança" className="flex gap-2">
                {(["digital", "infra"] as Mundo[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="radio"
                    aria-checked={mundoCobranca === m}
                    onClick={() => setMundoCobranca(m)}
                    className="flex h-9 items-center gap-2 rounded-[8px] border px-3 font-[family-name:var(--font-display)] text-[13px] font-semibold transition-colors duration-[var(--dur-fast)]"
                    style={
                      mundoCobranca === m
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
                É onde a mensalidade vira lançamento. O cliente em si não tem mundo.
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="efetivacao-cli">Efetivação da mensalidade</Label>
              <Seletor
                id="efetivacao-cli"
                nome="efetivar_automaticamente"
                valor={efetivacao}
                aoMudar={(v) => setEfetivacao(v as typeof efetivacao)}
                opcoes={[
                  { valor: "padrao", rotulo: "Usar o padrão configurado" },
                  {
                    valor: "nao",
                    rotulo: "Manual — exige confirmação (permite alerta de atraso)",
                  },
                  {
                    valor: "sim",
                    rotulo: "Automática na data (nunca aparece como atrasada)",
                  },
                ]}
              />
            </div>
          </div>
        ) : null}

        {(servicos?.itens.length ?? 0) > 0 ? (
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Serviços contratados</span>
            <div className="flex flex-wrap gap-3">
              {servicos!.itens.map((s) => (
                <label key={s.id} className="flex cursor-pointer items-center gap-2 text-[13px]">
                  <Checkbox
                    checked={servicoIds.includes(s.id)}
                    onCheckedChange={() =>
                      setServicoIds((a) =>
                        a.includes(s.id) ? a.filter((x) => x !== s.id) : [...a, s.id],
                      )
                    }
                  />
                  {s.nome}
                </label>
              ))}
            </div>
          </div>
        ) : null}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="obs-cli">Observações</Label>
          <Textarea
            id="obs-cli"
            rows={2}
            value={observacoes}
            onChange={(e) => setObservacoes(e.target.value)}
          />
        </div>

        {aviso ? (
          <p
            className="rounded-[8px] px-3 py-2.5 text-[13px]"
            style={{ background: "var(--st-pendente-bg)", color: "var(--st-pendente-fg)" }}
          >
            {aviso}
          </p>
        ) : null}

        {erro ? (
          <p
            role="alert"
            className="rounded-[8px] px-3 py-2 text-[13px]"
            style={{ background: "var(--st-atrasado-bg)", color: "var(--st-atrasado-fg)" }}
          >
            {erro}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            {aviso ? "Fechar" : "Cancelar"}
          </Button>
          <Button
            disabled={!nome.trim() || salvar.isPending}
            aria-busy={salvar.isPending}
            onClick={() =>
              salvar.mutate({
                nome: nome.trim(),
                empresa: empresa.trim() || null,
                contato_email: email.trim() || null,
                contato_telefone: telefone.trim() || null,
                tipo_cobranca: tipoCobranca,
                valor_recorrente: recorrente
                  ? Number(valor.replace(",", ".")).toFixed(2)
                  : null,
                dia_cobranca: recorrente ? Number(dia) : null,
                mundo_cobranca: recorrente ? mundoCobranca : null,
                servico_ids: servicoIds,
                observacoes: observacoes.trim() || null,
                efetivar_automaticamente:
                  efetivacao === "padrao" ? null : efetivacao === "sim",
              })
            }
          >
            {salvar.isPending ? "Salvando…" : "Salvar cliente"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
