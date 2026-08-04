"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Quadro } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { Seletor } from "@/componentes/comum/Seletor";
import { Button } from "@/componentes/ui/button";
import { Input } from "@/componentes/ui/input";
import { Label } from "@/componentes/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/componentes/ui/dialog";
import { api, ErroApi, mensagemDoErro } from "@/lib/api";
import { chaves, useSessao, useUsuarios } from "@/lib/consultas";
import { iniciais } from "@/lib/formato";
import type { PapelUsuario, Usuario } from "@/lib/tipos";

/**
 * Usuários (T197, `FR-102`, `SC-010`).
 *
 * **Não existe cadastro público**: o gestor convida, e o backend cria a conta
 * no Supabase Auth junto com a linha em `usuarios`.
 *
 * **Não existe exclusão**: usuário desativado precisa continuar existindo
 * para a auditoria apontar para ele. Por isso as ações são desativar e
 * reativar.
 *
 * O servidor tem uma trava que recusa rebaixar ou desativar o **último gestor
 * ativo** — senão o sistema ficaria sem ninguém que possa entrar aqui. A tela
 * não reimplementa a trava; ela mostra o `409` que vier.
 */
export function SecaoUsuarios() {
  const cliente = useQueryClient();
  const { data: sessao } = useSessao();
  const { data, isLoading } = useUsuarios(true);
  const [convidando, setConvidando] = useState(false);
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [papel, setPapel] = useState<PapelUsuario>("operador");
  const [erro, setErro] = useState<string | null>(null);

  function invalidar() {
    cliente.invalidateQueries({ queryKey: chaves.usuarios });
    cliente.invalidateQueries({ queryKey: chaves.sessao });
  }

  const convidar = useMutation({
    mutationFn: () =>
      api.post("/api/usuarios", { corpo: { nome: nome.trim(), email: email.trim(), papel } }),
    onSuccess: () => {
      invalidar();
      setConvidando(false);
      setNome("");
      setEmail("");
      toast.success("Convite enviado.", {
        description: "A pessoa define a própria senha pelo e-mail do Supabase.",
      });
    },
    onError: (e) => setErro(e instanceof ErroApi ? e.message : mensagemDoErro(e)),
  });

  const mudarPapel = useMutation({
    mutationFn: ({ id, u, novo }: { id: string; u: Usuario; novo: PapelUsuario }) =>
      api.put(`/api/usuarios/${id}`, { corpo: { nome: u.nome, papel: novo } }),
    onSuccess: () => {
      invalidar();
      toast.success("Papel atualizado.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const alternarAtivo = useMutation({
    mutationFn: ({ id, ativo }: { id: string; ativo: boolean }) =>
      api.post(`/api/usuarios/${id}/${ativo ? "desativar" : "reativar"}`),
    onSuccess: () => {
      invalidar();
      toast.success("Situação do usuário atualizada.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const itens = (data as { itens?: Usuario[] } | undefined)?.itens ?? [];

  return (
    <>
      <Quadro>
        <div className="flex items-center justify-between gap-3 border-b border-linha-suave px-4 py-3">
          <div className="flex flex-col">
            <span className="font-[family-name:var(--font-display)] text-[14px] font-bold text-forte">
              Usuários
            </span>
            <span className="text-[12px] text-suave">
              Gestor faz tudo; operador cria e edita lançamentos e lê o resto.
            </span>
          </div>
          <Button size="sm" onClick={() => setConvidando(true)}>
            <Plus size={15} />
            Convidar
          </Button>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-2 p-4">
            {[0, 1].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-[8px] bg-[var(--bg-subtle)]" />
            ))}
          </div>
        ) : itens.length === 0 ? (
          <EstadoVazio titulo="Nenhum usuário listado" compacto />
        ) : (
          <ul>
            {itens.map((u) => (
              <li
                key={u.id}
                className="flex flex-wrap items-center gap-3 border-b border-[var(--linha-suave)] px-4 py-3 last:border-b-0"
              >
                <span className="flex size-8 flex-none items-center justify-center rounded-[6px] bg-[var(--brand-tint-2)] font-[family-name:var(--font-display)] text-[11px] font-extrabold text-[var(--lateral-ativo-fg)]">
                  {iniciais(u.nome)}
                </span>
                <span className="flex min-w-[200px] flex-1 flex-col">
                  <span className="text-[13px] font-semibold text-[var(--fg)]">
                    {u.nome}
                    {u.id === sessao?.usuario.id ? (
                      <span className="ml-2 text-[11px] font-normal text-sutil">você</span>
                    ) : null}
                  </span>
                  <span className="text-[12px] text-sutil">{u.email}</span>
                </span>

                <Seletor
                  rotuloAcessivel={`Papel de ${u.nome}`}
                  valor={u.papel}
                  aoMudar={(v) => mudarPapel.mutate({ id: u.id, u, novo: v as PapelUsuario })}
                  compacto
                  className="w-auto rounded-[6px]"
                  opcoes={[
                    { valor: "gestor", rotulo: "Gestor" },
                    { valor: "operador", rotulo: "Operador" },
                  ]}
                />

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => alternarAtivo.mutate({ id: u.id, ativo: u.ativo })}
                >
                  {u.ativo ? "Desativar" : "Reativar"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Quadro>

      <p className="px-1 text-[12px] text-sutil">
        Esconder o menu de Configurações do operador é conveniência. A autorização é o `403` que
        o backend devolve em cada endpoint — e há teste cobrindo isso.
      </p>

      <Dialog open={convidando} onOpenChange={setConvidando}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Convidar usuário</DialogTitle>
            <DialogDescription>
              A conta é criada no Supabase Auth e a pessoa define a própria senha.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="nome-usr">Nome</Label>
              <Input id="nome-usr" value={nome} onChange={(e) => setNome(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email-usr">E-mail</Label>
              <Input
                id="email-usr"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="papel-usr">Papel</Label>
              <Seletor
                id="papel-usr"
                nome="papel"
                valor={papel}
                aoMudar={(v) => setPapel(v as PapelUsuario)}
                opcoes={[
                  { valor: "operador", rotulo: "Operador" },
                  { valor: "gestor", rotulo: "Gestor" },
                ]}
              />
            </div>
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
            <Button variant="outline" onClick={() => setConvidando(false)}>
              Cancelar
            </Button>
            <Button
              disabled={!nome.trim() || !email.trim() || convidar.isPending}
              onClick={() => convidar.mutate()}
            >
              Convidar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
