"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/componentes/ui/button";
import { Input } from "@/componentes/ui/input";
import { Label } from "@/componentes/ui/label";
import { MarcaSynapse } from "@/componentes/comum/icones";
import { autenticacaoConfigurada, entrar, mensagemDeAutenticacao, sessaoAtual } from "@/lib/supabase";

/**
 * Tela de entrar (T155, `FR-102`).
 *
 * O login é do Supabase Auth, direto do navegador — o FastAPI nunca recebe
 * senha (contracts/plataforma.md §1). **Não existe cadastro público**: quem
 * cria conta é o gestor, em Configurações › Usuários. Por isso não há link de
 * "criar conta" nesta tela, e não é esquecimento.
 *
 * O visual segue a orientação de fundo do design system: branco com dois
 * lavados radiais roxos, sem gradiente saturado e sem foto.
 */
export function FormEntrar() {
  const router = useRouter();
  const params = useSearchParams();
  const destino = params.get("destino") || "/";

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [verificando, setVerificando] = useState(true);

  const configurado = autenticacaoConfigurada();

  useEffect(() => {
    let vivo = true;
    (async () => {
      if (!configurado) {
        if (vivo) setVerificando(false);
        return;
      }
      const sessao = await sessaoAtual();
      if (!vivo) return;
      if (sessao) router.replace(destino);
      else setVerificando(false);
    })();
    return () => {
      vivo = false;
    };
  }, [configurado, destino, router]);

  async function aoEnviar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email.trim(), senha);
      router.replace(destino);
    } catch (falha) {
      setErro(mensagemDeAutenticacao(falha));
      setEnviando(false);
    }
  }

  return (
    <div
      className="flex min-h-dvh items-center justify-center px-6 py-10"
      style={{ background: "var(--grad-hero)" }}
    >
      <div className="grid w-full max-w-[980px] overflow-hidden rounded-[28px] border border-linha-chrome bg-superficie-cartao shadow-[var(--shadow-lg)] md:grid-cols-[1.05fr_1fr]">
        {/* Painel de marca — some no celular, onde o formulário é o que importa */}
        <aside
          className="hidden flex-col justify-between p-10 md:flex"
          style={{ background: "var(--grad-brand-soft)" }}
        >
          <div className="flex items-center gap-3">
            <MarcaSynapse tamanho={36} idGradiente="marca-entrar" className="rounded-[9px]" />
            <div className="flex flex-col leading-[1.15]">
              <span className="font-[family-name:var(--font-display)] text-[16px] font-bold tracking-[-0.02em] text-forte">
                Synapse ERP
              </span>
              <span className="text-[11px] tracking-[0.03em] text-suave">Financeiro</span>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <h1 className="text-[30px] leading-[1.15] font-extrabold tracking-[-0.03em] text-forte">
              Os dois mundos da Synapse, no mesmo lugar.
            </h1>
            <p className="max-w-[38ch] text-[13.5px] leading-[1.6] text-suave">
              Digital e Infra com caixas separados, lançamentos programados que se resolvem na
              data e o resultado do mês sem planilha.
            </p>
            <div className="mt-2 flex items-center gap-2 text-[12px] text-sutil">
              <span className="size-[7px] rounded-[2px] bg-[var(--mundo-digital)]" />
              Synapse Digital
              <span className="mx-1 text-[var(--ink-300)]">·</span>
              <span className="size-[7px] rounded-[2px] bg-[var(--mundo-infra)]" />
              Synapse Infra
            </div>
          </div>

          <p className="text-[11.5px] text-sutil">Uso interno · acesso por convite do gestor</p>
        </aside>

        <div className="flex flex-col justify-center gap-6 p-8 sm:p-10">
          <div className="flex flex-col gap-1.5 md:hidden">
            <MarcaSynapse tamanho={34} idGradiente="marca-entrar-movel" className="rounded-[9px]" />
          </div>

          <div className="flex flex-col gap-1">
            <h2 className="text-[22px] font-extrabold tracking-[-0.02em] text-forte">Entrar</h2>
            <p className="text-[13px] text-suave">Use o e-mail cadastrado pelo gestor.</p>
          </div>

          {!configurado ? (
            <p
              role="alert"
              className="rounded-[10px] border px-3 py-2.5 text-[12.5px]"
              style={{
                borderColor: "var(--st-pendente-dot)",
                background: "var(--st-pendente-bg)",
                color: "var(--st-pendente-fg)",
              }}
            >
              Autenticação não configurada neste ambiente. Falta{" "}
              <code className="font-mono text-[11.5px]">NEXT_PUBLIC_SUPABASE_URL</code> e{" "}
              <code className="font-mono text-[11.5px]">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> em{" "}
              <code className="font-mono text-[11.5px]">.env.local</code>.
            </p>
          ) : null}

          <form onSubmit={aoEnviar} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">E-mail</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="voce@synapse.com.br"
                disabled={!configurado || verificando}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="senha">Senha</Label>
              <div className="relative">
                <Input
                  id="senha"
                  type={mostrarSenha ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  className="pr-10"
                  disabled={!configurado || verificando}
                />
                <button
                  type="button"
                  onClick={() => setMostrarSenha((v) => !v)}
                  aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
                  className="absolute top-1/2 right-2 -translate-y-1/2 rounded-[6px] p-1 text-sutil transition-colors hover:text-[var(--fg)]"
                >
                  {mostrarSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
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

            <Button type="submit" disabled={!configurado || enviando || verificando} className="h-10">
              {enviando ? <Loader2 className="animate-spin" size={16} /> : null}
              Entrar
            </Button>
          </form>

          <p className="text-[11.5px] text-sutil">
            Esqueceu a senha? Peça ao gestor para reenviar o convite — não há cadastro público
            neste sistema.
          </p>
        </div>
      </div>
    </div>
  );
}
