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
import { Switch } from "@/componentes/ui/switch";
import { Seletor } from "@/componentes/comum/Seletor";
import { SeletorIcone } from "@/componentes/comum/SeletorIcone";
import { ICONE_PADRAO } from "@/componentes/comum/catalogo-icones";
import { api, ErroApi, mensagemDoErro } from "@/lib/api";
import { useInvalidarFinanceiro } from "@/lib/consultas";
import type { Categoria, TipoCategoria, VinculoSubcategoria } from "@/lib/tipos";

/**
 * Criar e editar categoria (`FR-072`, `FR-079`).
 *
 * **Promover a especial é só marcar o interruptor e escolher o vínculo** —
 * não há deploy envolvido, que é exatamente o que `FR-079` promete. Se outra
 * categoria ativa já ocupa o vínculo, o servidor responde `409` nomeando
 * qual é; a mensagem que aparece é a dele.
 *
 * Categoria não aceita `mundo`: a lista é a mesma nos dois mundos.
 */
export function FormCategoria({
  aberta,
  categoria,
  aoFechar,
}: {
  aberta: boolean;
  categoria: Categoria | null;
  aoFechar: () => void;
}) {
  const invalidar = useInvalidarFinanceiro();
  const [nome, setNome] = useState("");
  const [cor, setCor] = useState("#8B6CF0");
  const [icone, setIcone] = useState(ICONE_PADRAO);
  const [tipo, setTipo] = useState<TipoCategoria>("despesa");
  const [especial, setEspecial] = useState(false);
  const [vinculo, setVinculo] = useState<VinculoSubcategoria>("cliente");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!aberta) return;
    setErro(null);
    setNome(categoria?.nome ?? "");
    setCor(categoria?.cor ?? "#8B6CF0");
    setIcone(categoria?.icone ?? ICONE_PADRAO);
    setTipo(categoria?.tipo ?? "despesa");
    setEspecial(categoria?.especial ?? false);
    setVinculo(categoria?.vinculo ?? "cliente");
  }, [aberta, categoria]);

  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      categoria
        ? api.put(`/api/categorias/${categoria.id}`, { corpo })
        : api.post("/api/categorias", { corpo }),
    onSuccess: () => {
      invalidar();
      toast.success(categoria ? "Categoria atualizada." : "Categoria criada.");
      aoFechar();
    },
    onError: (e) => {
      setErro(e instanceof ErroApi ? e.message : mensagemDoErro(e));
    },
  });

  return (
    <Dialog open={aberta} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{categoria ? "Editar categoria" : "Nova categoria"}</DialogTitle>
          <DialogDescription>
            A categoria vale nos dois mundos. Quem separa Digital de Infra é o lançamento.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="nome-cat">Nome</Label>
            <Input id="nome-cat" value={nome} onChange={(e) => setNome(e.target.value)} />
          </div>

          <div className="grid grid-cols-[1fr_110px] gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tipo-cat">Aceita lançamentos de</Label>
              <Seletor
                id="tipo-cat"
                nome="tipo"
                valor={tipo}
                aoMudar={(v) => setTipo(v as TipoCategoria)}
                opcoes={[
                  { valor: "despesa", rotulo: "Despesa", cor: "var(--despesa-fg)" },
                  { valor: "receita", rotulo: "Receita", cor: "var(--receita-fg)" },
                  // Categoria especial precisa de um lado (`RF-58`): é o `tipo` que
                  // separa "Clientes" de "Custos Operacionais" dentro do mesmo
                  // vínculo. Oferecer "ambas" aqui só levaria a um `400` no salvar.
                  ...(especial ? [] : [{ valor: "ambas", rotulo: "Receita e despesa" }]),
                ]}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cor-cat">Cor</Label>
              <input
                id="cor-cat"
                type="color"
                value={cor}
                onChange={(e) => setCor(e.target.value)}
                className="h-9 w-full cursor-pointer rounded-[8px] border border-linha-controle bg-superficie-cartao p-1"
              />
            </div>
          </div>

          {/* O ícone é dado editável da categoria (`FR-072`) e a coluna é
              `not null`: até 2026-08-05 o formulário mandava `icone: null` e o
              servidor recusava com `400 validacao` — criar categoria não
              funcionava. Agora sempre sai um nome Lucide válido do catálogo. */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="icone-cat">Ícone</Label>
            <SeletorIcone id="icone-cat" valor={icone} aoMudar={setIcone} cor={cor} />
            <p className="text-[12px] text-sutil">
              Aparece na lista de categorias, na cor escolhida acima.
            </p>
          </div>

          <label className="flex items-start justify-between gap-4 rounded-[10px] border border-linha-suave bg-[var(--bg-subtle)] px-4 py-3">
            <span className="flex flex-col gap-0.5">
              <span className="text-[13px] font-semibold text-[var(--fg)]">Categoria especial</span>
              <span className="text-[12px] text-suave">
                As subcategorias passam a nascer do cadastro de clientes ou de funcionários, e o
                Dashboard ganha o bloco correspondente.
              </span>
            </span>
            <Switch
              checked={especial}
              onCheckedChange={(marcado) => {
                setEspecial(marcado);
                // "Ambas" não é um lado, e categoria especial precisa de um
                // (`RF-58`). Trocar aqui evita o `400` no salvar.
                if (marcado && tipo === "ambas") setTipo("despesa");
              }}
            />
          </label>

          {especial ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vinculo-cat">Vínculo</Label>
              <Seletor
                id="vinculo-cat"
                nome="vinculo"
                valor={vinculo}
                aoMudar={(v) => setVinculo(v as VinculoSubcategoria)}
                opcoes={[
                  { valor: "cliente", rotulo: "Clientes" },
                  { valor: "funcionario", rotulo: "Funcionários" },
                ]}
              />
              <p className="text-[12px] text-sutil">
                Cabe uma categoria de <strong>receita</strong> e uma de <strong>despesa</strong>{" "}
                por vínculo — é assim que Clientes e Custos Operacionais convivem. Se outra já
                ocupa este lado, o sistema recusa e diz qual é. Ao salvar, o espelho de cada
                cadastro existente é criado aqui.
              </p>
            </div>
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
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button
            disabled={!nome.trim() || salvar.isPending}
            onClick={() =>
              salvar.mutate({
                nome: nome.trim(),
                cor,
                icone,
                tipo,
                especial,
                vinculo: especial ? vinculo : null,
                ordem: categoria?.ordem ?? 99,
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
