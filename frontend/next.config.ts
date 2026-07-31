import type { NextConfig } from "next";

/**
 * `/api/*` é reescrito para o backend FastAPI (T152, research.md D-02).
 *
 * O navegador só conhece a origem do Next.js, então não há CORS, não há
 * `OPTIONS` de preflight e o token não precisa atravessar origem. O preço é
 * um salto de rede a mais, que é barato perto de manter CORS certo em dois
 * projetos Vercel.
 *
 * `BACKEND_URL` é variável de ambiente **do servidor** (Princípio VII) — não
 * tem `NEXT_PUBLIC_`, e por isso nunca chega ao pacote do navegador.
 */
const backend = process.env.BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  async rewrites() {
    return [
      {
        source: "/api/:caminho*",
        destination: `${backend}/api/:caminho*`,
      },
    ];
  },

  async headers() {
    return [
      {
        source: "/:caminho*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
