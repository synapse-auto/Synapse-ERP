/**
 * Ícones da navegação — SVGs próprios, extraídos do mockup (T146).
 *
 * O design system usa Lucide para o resto da interface, mas os oito itens de
 * menu do mockup têm desenhos próprios (`stroke-width: 1.9`, cantos
 * arredondados, 17px). Copiar o `d` de cada um mantém a barra lateral
 * idêntica ao desenho aprovado; trocar por Lucide mudaria o peso do traço e
 * o espaçamento interno de todos ao mesmo tempo.
 *
 * Os `path` abaixo são cópia literal de `Synapse ERP Financeiro.dc.html`.
 * Tudo que não é navegação usa `lucide-react`.
 */

import Image from "next/image";
import type { SVGProps } from "react";
import { cn } from "@/lib/utils";

type PropsIcone = Omit<SVGProps<SVGSVGElement>, "children"> & { tamanho?: number };

function Traco({ tamanho = 17, ...props }: PropsIcone & { d: string }) {
  const { d, ...resto } = props;
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...resto}
    >
      <path d={d} />
    </svg>
  );
}

export const IconeDashboard = (p: PropsIcone) => (
  <Traco {...p} d="M4 4h6.5v7H4zM13.5 4H20v4.5h-6.5zM13.5 11.5H20V20h-6.5zM4 14h6.5v6H4z" />
);

export const IconeLancamentos = (p: PropsIcone) => (
  <Traco {...p} d="M7 20V5M7 5 3.5 8.5M7 5l3.5 3.5M17 4v15M17 19l3.5-3.5M17 19l-3.5-3.5" />
);

export const IconeExtrato = (p: PropsIcone) => (
  <Traco
    {...p}
    d="M5 3.5h14v17l-2.4-1.5-2.3 1.5-2.3-1.5L9.7 20.5 7.4 19 5 20.5zM8.8 8.5h6.4M8.8 12.5h6.4"
  />
);

export const IconeCategorias = (p: PropsIcone) => (
  <Traco
    {...p}
    d="M4 6.5A2.5 2.5 0 0 1 6.5 4h2.8l2 2.6H18a2.5 2.5 0 0 1 2.5 2.5v8.4A2.5 2.5 0 0 1 18 20H6.5A2.5 2.5 0 0 1 4 17.5z"
  />
);

export const IconeClientes = (p: PropsIcone) => (
  <Traco
    {...p}
    d="M15.5 20v-1.8a3.7 3.7 0 0 0-3.7-3.7H7a3.7 3.7 0 0 0-3.7 3.7V20M9.4 4.2a3.4 3.4 0 1 1 0 6.8 3.4 3.4 0 0 1 0-6.8M16.6 4.4a3.4 3.4 0 0 1 0 6.4M20.7 20v-1.8a3.7 3.7 0 0 0-2.8-3.6"
  />
);

export const IconeFuncionarios = (p: PropsIcone) => (
  <Traco
    {...p}
    d="M4.5 7.5h15a1.5 1.5 0 0 1 1.5 1.5v8.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a1.5 1.5 0 0 1 1.5-1.5zM9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5M3 12.5h18"
  />
);

export const IconeRelatorios = (p: PropsIcone) => (
  <Traco {...p} d="M3.5 20h17M7 20v-6.5M12 20V6M17 20v-9.5" />
);

export const IconeConfiguracoes = (p: PropsIcone) => (
  <Traco {...p} d="M4 7.5h8M16.5 7.5H20M4 16.5h3.5M12 16.5h8M14.2 5.3v4.4M9.8 14.3v4.4" />
);

/* ---- ícones de chrome que o mockup também desenha à mão ---- */

export const IconeBusca = ({ tamanho = 15, ...props }: PropsIcone) => (
  <svg
    width={tamanho}
    height={tamanho}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    aria-hidden="true"
    {...props}
  >
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.6-3.6" />
  </svg>
);

export const IconeSino = (p: PropsIcone) => (
  <Traco {...p} d="M18 8.5a6 6 0 1 0-12 0c0 6-2.2 7.5-2.2 7.5h16.4S18 14.5 18 8.5M13.7 19.5a2 2 0 0 1-3.4 0" />
);

export const IconeMais = ({ tamanho = 16, ...props }: PropsIcone) => (
  <svg
    width={tamanho}
    height={tamanho}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2.4}
    strokeLinecap="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M12 5.5v13M5.5 12h13" />
  </svg>
);

export const IconeAlerta = ({ tamanho = 18, ...props }: PropsIcone) => (
  <svg
    width={tamanho}
    height={tamanho}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M12 4.5 2.8 20h18.4zM12 10v4.2M12 17.2h.01" />
  </svg>
);

export const IconeSetaDireita = ({ tamanho = 15, ...props }: PropsIcone) => (
  <svg
    width={tamanho}
    height={tamanho}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2.2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="m9 5 7 7-7 7" />
  </svg>
);

export const IconeAjustes = ({ tamanho = 14, ...props }: PropsIcone) => (
  <svg
    width={tamanho}
    height={tamanho}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M4 6h16M7 12h10M10 18h4" />
  </svg>
);

export const IconeExportar = ({ tamanho = 14, ...props }: PropsIcone) => (
  <svg
    width={tamanho}
    height={tamanho}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M12 4v11M12 15l-4-4M12 15l4-4M4 19h16" />
  </svg>
);

/**
 * Marca da Synapse — a **mesma arte do favicon**, redonda (T218).
 *
 * Até 2026-08-03 isto era um "S" desenhado à mão em SVG, herdado do design
 * system, que não era o logotipo da empresa. A marca de verdade mora em
 * `public/marca-synapse.png`, recortada em círculo, e é o mesmo arquivo que
 * `app/icon.png` serve como ícone da aba — assim a aba do navegador e o canto
 * da tela mostram a mesma coisa, que é o mínimo que se espera de uma marca.
 *
 * `next/image` com `width`/`height` explícitos: sem eles a imagem empurraria o
 * layout ao carregar (Web Interface Guidelines § Images). `priority` porque a
 * marca está sempre acima da dobra — na barra lateral, na tela de entrar e na
 * tela de espera.
 */
export function MarcaSynapse({
  tamanho = 31,
  className,
  prioridade = true,
}: {
  tamanho?: number;
  className?: string;
  /** Desligue em marca que não aparece de primeira. */
  prioridade?: boolean;
}) {
  return (
    <Image
      src="/marca-synapse.png"
      alt="Synapse"
      width={tamanho}
      height={tamanho}
      priority={prioridade}
      className={cn("rounded-full object-contain", className)}
    />
  );
}
