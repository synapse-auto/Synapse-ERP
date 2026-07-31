/**
 * Supabase — **só login** (T149, research.md D-03a).
 *
 * O frontend nunca fala com o banco. A chave `anon` que vive no navegador
 * recebe negação por RLS em todas as tabelas financeiras (migração `006`),
 * então mesmo que alguém tentasse `supabase.from('lancamentos')` daqui não
 * viria nada. O papel deste cliente é um só: autenticar e entregar o JWT que
 * o `lib/api.ts` põe no `Authorization` de cada chamada ao FastAPI.
 *
 * Por isso não há helper de query aqui. Se aparecer um, é bug de arquitetura.
 */

import { createBrowserClient } from "@supabase/ssr";
import type { Session, SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const chaveAnon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let cliente: SupabaseClient | null = null;

/**
 * Cliente de navegador. Devolve `null` quando as variáveis não estão
 * configuradas — assim o build e os testes de componente não quebram por
 * causa de ambiente, e a tela de entrar sabe dizer o que falta.
 */
export function supabase(): SupabaseClient | null {
  if (!url || !chaveAnon) return null;
  if (!cliente) cliente = createBrowserClient(url, chaveAnon);
  return cliente;
}

export function autenticacaoConfigurada(): boolean {
  return Boolean(url && chaveAnon);
}

/** Sessão vigente, ou `null`. Usada pelo `lib/api.ts` a cada chamada. */
export async function sessaoAtual(): Promise<Session | null> {
  const c = supabase();
  if (!c) return null;
  const { data } = await c.auth.getSession();
  return data.session ?? null;
}

/** Entrar com e-mail e senha. Não existe cadastro público (`FR-102`). */
export async function entrar(email: string, senha: string): Promise<Session> {
  const c = supabase();
  if (!c) throw new Error("Autenticação não configurada neste ambiente.");
  const { data, error } = await c.auth.signInWithPassword({ email, password: senha });
  if (error) throw error;
  if (!data.session) throw new Error("O servidor de login não devolveu uma sessão.");
  return data.session;
}

export async function sair(): Promise<void> {
  const c = supabase();
  if (!c) return;
  await c.auth.signOut();
}

/** Recuperação de senha — o gestor convida, mas a pessoa troca a própria senha. */
export async function pedirTrocaDeSenha(email: string, redirecionarPara: string): Promise<void> {
  const c = supabase();
  if (!c) throw new Error("Autenticação não configurada neste ambiente.");
  const { error } = await c.auth.resetPasswordForEmail(email, { redirectTo: redirecionarPara });
  if (error) throw error;
}

/**
 * Traduz o erro do Supabase Auth. É a única exceção à regra de "o texto vem
 * do backend": o Supabase responde em inglês e não é o nosso FastAPI.
 */
export function mensagemDeAutenticacao(e: unknown): string {
  const bruto = e instanceof Error ? e.message : String(e ?? "");
  const m = bruto.toLowerCase();
  if (m.includes("invalid login credentials")) return "E-mail ou senha incorretos.";
  if (m.includes("email not confirmed")) return "Este e-mail ainda não foi confirmado.";
  if (m.includes("too many requests") || m.includes("rate limit")) {
    return "Muitas tentativas seguidas. Espere um minuto e tente de novo.";
  }
  if (m.includes("failed to fetch") || m.includes("network")) {
    return "Não foi possível falar com o servidor de login. Verifique a conexão.";
  }
  if (m.includes("não configurada")) return bruto;
  return "Não foi possível entrar. Tente de novo.";
}
