import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Provedores } from "@/componentes/comum/provedores";

/**
 * Tipografia — Geist (T211).
 *
 * Decisão do dono do projeto no Boss 4: a interface passa a usar **Geist**, a
 * família da Vercel, no lugar do par Plus Jakarta Sans + Inter do Synapse
 * Design System. Uma família só para tudo (título e corpo), como a Vercel faz —
 * o contraste de peso e de tamanho é que separa hierarquia, não a troca de
 * família. Números em Geist são tabulares por padrão nas colunas de dinheiro
 * (`.numerico` continua forçando `tabular-nums`).
 *
 * `--fonte-display` continua existindo e apontando para Geist: assim os ~60
 * `font-[family-name:var(--font-display)]` espalhados pelas telas continuam
 * válidos sem precisar sumir um a um.
 *
 * Auto-hospedadas pelo `next/font` — sem requisição ao Google em tempo de
 * renderização e sem salto de layout quando a fonte chega.
 */
const geist = Geist({
  variable: "--fonte-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

const geistCorpo = Geist({
  variable: "--fonte-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const mono = Geist_Mono({
  variable: "--fonte-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Synapse ERP · Financeiro",
  description: "Plataforma financeira interna da Synapse — Digital e Infra.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F7F5FB" },
    { media: "(prefers-color-scheme: dark)", color: "#14102B" },
  ],
};

export default function LayoutRaiz({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body
        className={`${geist.variable} ${geistCorpo.variable} ${mono.variable} antialiased`}
      >
        {/* Pular para o conteúdo — primeiro foco tabulável da página
            (Web Interface Guidelines, Acessibilidade). Só aparece com foco. */}
        <a
          href="#conteudo-principal"
          className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:top-3 focus-visible:left-3 focus-visible:z-[100] focus-visible:rounded-[6px] focus-visible:bg-[var(--brand)] focus-visible:px-3 focus-visible:py-2 focus-visible:text-[13px] focus-visible:font-semibold focus-visible:text-[var(--fg-onbrand)]"
        >
          Pular para o conteúdo
        </a>
        <Provedores>{children}</Provedores>
      </body>
    </html>
  );
}
