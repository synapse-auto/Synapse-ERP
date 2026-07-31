"use client";

import { cn } from "@/lib/utils";
import { Cartao, RotuloCartao } from "@/componentes/comum/Cartao";
import { Delta } from "@/componentes/comum/Delta";
import { Sparkline } from "@/componentes/graficos/EvolucaoSaldo";
import { COR } from "@/componentes/graficos/base";
import { rotuloDoStatus } from "@/componentes/comum/BadgeStatus";
import { dinheiro, percentual } from "@/lib/formato";
import type { CardDashboard, MundoFiltro } from "@/lib/tipos";
import { ROTULO_MUNDO } from "@/componentes/comum/BadgeMundo";

/**
 * Card numérico do Dashboard (T176, `FR-054`–`FR-057`).
 *
 * Um componente só para os sete cards, porque a diferença entre eles é
 * **dado**, não código: o rótulo vem de `configuracoes`, a unidade vem no
 * próprio card (`unidade: "percentual"`), a tendência vem em `tendencia` e o
 * destino do clique vem em `filtro_drilldown`. Escrever sete componentes
 * quase iguais criaria sete lugares para o rótulo divergir do banco.
 *
 * `hero` é o formato do cartão maior à esquerda no mockup: 40px de número,
 * fundo em degradê lilás e sparkline com área.
 */
export function CartaoNumerico({
  card,
  hero = false,
  mundo,
  aoAbrirFiltro,
  className,
}: {
  card: CardDashboard;
  hero?: boolean;
  mundo?: MundoFiltro;
  aoAbrirFiltro?: (card: CardDashboard) => void;
  className?: string;
}) {
  const ehPercentual = card.unidade === "percentual";
  const valor = ehPercentual ? percentual(card.valor) : dinheiro(card.valor);

  // Despesa: cair é bom. É a única inversão, e ela vem do id do card, que é
  // dado do catálogo — não de comparar o rótulo.
  const inverso = card.id.startsWith("despesas") || card.id === "a_pagar";

  const clicavel = Boolean(card.filtro_drilldown && aoAbrirFiltro);
  const Elemento = clicavel ? "button" : "div";

  return (
    <Cartao
      destaque={hero}
      className={cn("flex flex-col", hero ? "p-[20px_22px]" : "px-5 py-[18px]", className)}
    >
      <Elemento
        {...(clicavel
          ? { type: "button" as const, onClick: () => aoAbrirFiltro!(card) }
          : {})}
        className={cn(
          "flex flex-1 flex-col text-left",
          clicavel && "cursor-pointer rounded-[10px] outline-none",
        )}
      >
        <div className="flex items-center justify-between gap-3">
          <RotuloCartao cor={hero ? "marca" : "sutil"}>{card.rotulo}</RotuloCartao>
          {card.comparativo && Object.keys(card.comparativo).length > 0 ? (
            <Delta comparativo={card.comparativo} inverso={inverso} />
          ) : null}
        </div>

        <span
          className={cn(
            "numerico mt-2 font-[family-name:var(--font-display)] leading-none font-extrabold tracking-[-0.035em]",
            hero ? "text-[40px]" : "text-[26px]",
          )}
          style={{
            color:
              hero && !ehPercentual
                ? Number(card.valor) >= 0
                  ? "var(--receita-fg)"
                  : "var(--despesa-fg)"
                : "var(--fg-strong)",
          }}
        >
          {valor}
        </span>

        {/* Quebra por mundo — só faz sentido no consolidado (`FR-003`) */}
        {card.quebra_por_mundo && mundo === "ambos" ? (
          <div className="mt-[10px] flex flex-col gap-[5px] border-t border-linha-suave pt-[10px]">
            {Object.entries(card.quebra_por_mundo).map(([m, v]) => (
              <span key={m} className="flex items-center gap-[7px] text-[11.5px] text-suave">
                <span
                  aria-hidden
                  className="size-[7px] flex-none rounded-[2.5px]"
                  style={{ background: `var(--mundo-${m})` }}
                />
                <span className="flex-1">{ROTULO_MUNDO[m as MundoFiltro]}</span>
                <span className="numerico font-[family-name:var(--font-display)] font-bold text-[var(--ink-700)] dark:text-[var(--fg)]">
                  {dinheiro(v)}
                </span>
              </span>
            ))}
          </div>
        ) : null}

        {/* Composição: as três situações, sempre, mesmo zeradas */}
        {card.composicao?.length ? (
          <ul className="mt-2.5 flex flex-col gap-1">
            {card.composicao
              .filter((c) => Number(c.valor) !== 0 || c.quantidade > 0)
              .map((c) => (
                <li
                  key={c.situacao}
                  className="flex items-center gap-2 text-[11.5px] text-suave"
                >
                  <span
                    aria-hidden
                    className="size-[6px] flex-none rounded-full"
                    style={{ background: `var(--st-${c.situacao}-dot)` }}
                  />
                  <span className="flex-1">{rotuloDoStatus(c.situacao)}</span>
                  <span className="numerico font-semibold text-[var(--fg)]">
                    {dinheiro(c.valor)}
                  </span>
                </li>
              ))}
          </ul>
        ) : null}

        {/* Barra da margem — o mockup desenha o percentual como preenchimento */}
        {ehPercentual ? (
          <div className="mt-3 h-[6px] w-full overflow-hidden rounded-full bg-[var(--bg-muted)]">
            <div
              className="h-full rounded-full bg-[var(--brand)]"
              style={{ width: `${Math.min(Math.max(Number(card.valor), 0), 100)}%` }}
            />
          </div>
        ) : null}

        {card.tendencia && card.tendencia.length > 1 ? (
          <div className="mt-auto pt-3">
            <Sparkline
              pontos={card.tendencia}
              comArea={hero}
              altura={hero ? 46 : 34}
              cor={
                card.id.startsWith("receitas")
                  ? COR.receita
                  : card.id.startsWith("despesas")
                    ? COR.despesa
                    : card.id === "lucro_liquido"
                      ? COR.receita
                      : COR.saldo
              }
            />
          </div>
        ) : null}
      </Elemento>
    </Cartao>
  );
}
