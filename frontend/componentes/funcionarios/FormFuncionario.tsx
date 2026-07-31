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
import { PontoMundo } from "@/componentes/comum/BadgeMundo";
import { api, ErroApi, mensagemDoErro } from "@/lib/api";
import { useInvalidarFinanceiro } from "@/lib/consultas";
import { useEstadoGlobal } from "@/lib/estado-global";
import type { Funcionario, Mundo, TipoContratacao } from "@/lib/tipos";

/**
 * Cadastro de funcionário (`FR-085`–`FR-088`).
 *
 * **O mundo é obrigatório e imutável** (`RN-15`): na edição o campo aparece
 * travado. Mandar diferente devolve `409` — e a mensagem que aparece é a do
 * servidor.
 *
 * Criar cria a subcategoria espelho e a recorrência mensal da folha na mesma
 * transação, com efetivação automática.
 */
export function FormFuncionario({
  aberta,
  funcionario,
  aoFechar,
}: {
  aberta: boolean;
  funcionario: Funcionario | null;
  aoFechar: () => void;
}) {
  const invalidar = useInvalidarFinanceiro();
  const mundoGlobal = useEstadoGlobal((e) => e.mundo);

  const [nome, setNome] = useState("");
  const [funcao, setFuncao] = useState("");
  const [tipo, setTipo] = useState<TipoContratacao>("pj");
  const [valor, setValor] = useState("");
  const [dia, setDia] = useState("5");
  const [mundo, setMundo] = useState<Mundo>("digital");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!aberta) return;
    setErro(null);
    setNome(funcionario?.nome ?? "");
    setFuncao(funcionario?.funcao ?? "");
    setTipo(funcionario?.tipo_contratacao ?? "pj");
    setValor(funcionario?.valor_mensal ?? "");
    setDia(String(funcionario?.dia_pagamento ?? 5));
    setMundo(funcionario?.mundo ?? (mundoGlobal === "ambos" ? "digital" : mundoGlobal));
  }, [aberta, funcionario, mundoGlobal]);

  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      funcionario
        ? api.put(`/api/funcionarios/${funcionario.id}`, { corpo })
        : api.post("/api/funcionarios", { corpo }),
    onSuccess: () => {
      invalidar();
      toast.success(funcionario ? "Funcionário atualizado." : "Funcionário cadastrado.", {
        description: funcionario
          ? undefined
          : "A folha mensal já foi criada como recorrência, com efetivação automática.",
      });
      aoFechar();
    },
    onError: (e) => setErro(e instanceof ErroApi ? e.message : mensagemDoErro(e)),
  });

  return (
    <Dialog open={aberta} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>{funcionario ? "Editar funcionário" : "Novo funcionário"}</DialogTitle>
          <DialogDescription>
            O cadastro cria a subcategoria da pessoa e a folha mensal automaticamente.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="nome-fun">Nome</Label>
            <Input id="nome-fun" value={nome} onChange={(e) => setNome(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="funcao-fun">Função</Label>
            <Input id="funcao-fun" value={funcao} onChange={(e) => setFuncao(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="valor-fun">Valor mensal</Label>
            <Input
              id="valor-fun"
              inputMode="decimal"
              className="numerico"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dia-fun">Dia do pagamento</Label>
            <Input
              id="dia-fun"
              type="number"
              min={1}
              max={31}
              value={dia}
              onChange={(e) => setDia(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tipo-fun">Contratação</Label>
            <select
              id="tipo-fun"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoContratacao)}
              className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
            >
              <option value="pj">PJ</option>
              <option value="freelancer">Freelancer</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Mundo</Label>
          <div className="flex gap-2">
            {(["digital", "infra"] as Mundo[]).map((m) => (
              <button
                key={m}
                type="button"
                disabled={Boolean(funcionario)}
                onClick={() => setMundo(m)}
                className="flex h-9 items-center gap-2 rounded-[10px] border px-3 font-[family-name:var(--font-display)] text-[12.5px] font-bold disabled:cursor-not-allowed disabled:opacity-60"
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
          <p className="text-[11.5px] text-sutil">
            {funcionario
              ? "O mundo é imutável depois de criado (RN-15)."
              : "A folha vai gerar despesa neste mundo, todo mês, e isso não muda depois."}
          </p>
        </div>

        {erro ? (
          <p
            role="alert"
            className="rounded-[10px] px-3 py-2 text-[12.5px]"
            style={{ background: "var(--st-atrasado-bg)", color: "var(--st-atrasado-fg)" }}
          >
            {erro}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button
            disabled={!nome.trim() || !valor.trim() || salvar.isPending}
            onClick={() =>
              salvar.mutate({
                nome: nome.trim(),
                funcao: funcao.trim() || null,
                tipo_contratacao: tipo,
                valor_mensal: Number(valor.replace(",", ".")).toFixed(2),
                dia_pagamento: Number(dia),
                mundo,
              })
            }
          >
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
