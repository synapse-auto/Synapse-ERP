import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Provedores } from "@/componentes/comum/provedores";

/**
 * As três famílias do Synapse Design System (T145).
 * Auto-hospedadas pelo `next/font` — sem requisição ao Google em tempo de
 * renderização e sem salto de layout quando a fonte chega.
 */
const display = Plus_Jakarta_Sans({
  variable: "--fonte-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

const corpo = Inter({
  variable: "--fonte-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const mono = JetBrains_Mono({
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
      <body className={`${display.variable} ${corpo.variable} ${mono.variable} antialiased`}>
        <Provedores>{children}</Provedores>
      </body>
    </html>
  );
}
