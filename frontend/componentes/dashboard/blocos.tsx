"use client";

import Link from "next/link";
import { Receipt } from "lucide-react";
import { cn } from "@/lib/utils";
import { Cartao, RotuloCartao } from "@/componentes/comum/Cartao";
import { Delta } from "@/componentes/comum/Delta";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { IconeAlerta, IconeClientes, IconeFuncionarios, IconeSetaDireita } from "@/componentes/comum/icones";
import { dinheiro, dataCurta, iniciais, percentual } from "@/lib/formato";
import { rotuloDoStatus } from "@/componentes/comum/BadgeStatus";
import type { Dashboard } from "@/lib/tipos";

/**
 * Os blocos não numéricos do Dashboard: alerta, saúde do caixa, resumo em
 * linguagem natural, Clientes, Funcionários, maiores despesas, receita por
 * serviço e a linha do tempo de 7 dias.
 *
 * Clientes, Custos por cliente e Funcionários existem porque
 * `categorias.vinculo` + `categorias.tipo` dizem que existem — não porque
 * alguém escreveu `if nome == 'Clientes'` (`FR-079`). A resposta traz
 * `card_clientes` / `card_custos_cliente` / `card_funcionarios` já
 * resolvidos; se o vínculo não existir, o campo vem nulo e o bloco
 * simplesmente não aparece.
 */

/* ------------------------------------------------------------------ */

export function AlertaAtrasados({
  alerta,
  aoAbrir,
}: {
  alerta: NonNullable<Dashboard["alerta_atrasados"]>;
  aoAbrir: () => void;
}) {
  if (alerta.quantidade === 0) return null;
  return (
    <button
      type="button"
      onClick={aoAbrir}
      className="flex w-full items-center gap-[14px] rounded-[10px] border border-[#F3CFCF] px-[18px] py-[14px] text-left shadow-[0_1px_3px_rgba(214,69,69,0.07)] transition-colors hover:border-[#E9AFAF] dark:border-[var(--st-atrasado-dot)]/40"
      style={{
        background:
          "linear-gradient(90deg, var(--st-atrasado-bg) 0%, var(--st-atrasado-bg) 60%, var(--superficie-cartao) 100%)",
      }}
    >
      <span
        className="flex size-[34px] flex-none items-center justify-center rounded-[8px]"
        style={{ background: "var(--st-atrasado-bg)", color: "var(--st-atrasado-fg)" }}
      >
        <IconeAlerta />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span
          className="font-[family-name:var(--font-display)] text-[14px] font-bold tracking-[-0.01em]"
          style={{ color: "var(--st-atrasado-fg)" }}
        >
          {alerta.quantidade}{" "}
          {alerta.quantidade === 1 ? "lançamento vencido" : "lançamentos vencidos"} ·{" "}
          {dinheiro(alerta.valor_total)} parados
        </span>
        <span className="text-[13px] text-suave">
          Contas que passaram da data e ainda esperam confirmação.
        </span>
      </span>
      <span
        className="flex items-center gap-1.5 font-[family-name:var(--font-display)] text-[13px] font-bold whitespace-nowrap"
        style={{ color: "var(--danger-500)" }}
      >
        Ver atrasados <IconeSetaDireita />
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ */

export function CartaoSaudeCaixa({
  saude,
  rotulo,
}: {
  saude: NonNullable<Dashboard["saude_caixa"]>;
  rotulo: string;
}) {
  const cor =
    saude.semaforo === "verde"
      ? { bg: "var(--st-efetivado-bg)", fg: "var(--st-efetivado-fg)", dot: "var(--st-efetivado-dot)" }
      : saude.semaforo === "amarelo"
        ? { bg: "var(--st-pendente-bg)", fg: "var(--st-pendente-fg)", dot: "var(--st-pendente-dot)" }
        : { bg: "var(--st-atrasado-bg)", fg: "var(--st-atrasado-fg)", dot: "var(--st-atrasado-dot)" };

  const acesas = saude.semaforo === "verde" ? 3 : saude.semaforo === "amarelo" ? 2 : 1;
  const titulo =
    saude.semaforo === "verde" ? "Saudável" : saude.semaforo === "amarelo" ? "Atenção" : "Crítico";

  return (
    <Cartao className="flex flex-col" style={{ background: cor.bg, borderColor: cor.dot }}>
      <div className="flex items-center justify-between gap-3">
        <RotuloCartao>{rotulo}</RotuloCartao>
        <span className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              aria-hidden
              className="size-[7px] rounded-full"
              style={{ background: i < acesas ? cor.dot : "var(--bg-muted)" }}
            />
          ))}
        </span>
      </div>
      <span
        className="mt-2 font-[family-name:var(--font-display)] text-[24px] leading-none font-extrabold tracking-[-0.03em]"
        style={{ color: cor.fg }}
      >
        {titulo}
      </span>
      {/* `explicacao` é texto de negócio, gerado no servidor (`FR-069`) */}
      <p className="mt-2 text-[13px] leading-[1.5] text-suave">{saude.explicacao}</p>
      {saude.cobertura === null ? (
        <p className="mt-1 text-[11px] text-sutil">
          Sem despesa fixa nos próximos {saude.horizonte_dias} dias — não dá para calcular
          cobertura.
        </p>
      ) : null}
    </Cartao>
  );
}

/* ------------------------------------------------------------------ */

export function ResumoDoPeriodo({ texto, rotulo }: { texto: string; rotulo: string }) {
  if (!texto) return null;
  return (
    <Cartao className="flex flex-col gap-2">
      <RotuloCartao cor="marca">{rotulo}</RotuloCartao>
      <p className="text-[14px] leading-[1.6] text-[var(--fg)]">{texto}</p>
    </Cartao>
  );
}

/* ------------------------------------------------------------------ */

export function BlocoClientes({
  bloco,
  rotulo,
}: {
  bloco: NonNullable<Dashboard["card_clientes"]>;
  rotulo: string;
}) {
  return (
    <Cartao className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-[8px] bg-[var(--brand-tint-2)] text-[var(--lateral-ativo-fg)]">
            <IconeClientes tamanho={16} />
          </span>
          <div className="flex flex-col">
            <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
              {rotulo}
            </span>
            <span className="rotulo-seccao text-[10px]">Categoria especial</span>
          </div>
        </div>
        <Link
          href="/clientes"
          className="flex items-center gap-1 rounded-[6px] px-1.5 py-1 font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--brand-hover)] no-underline transition-colors duration-[var(--dur-fast)] hover:bg-[var(--brand-tint)] hover:text-[var(--brand-press)]"
        >
          Ver todos <IconeSetaDireita tamanho={13} />
        </Link>
      </div>

      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[12px] text-sutil">Recebido no período</span>
          <span className="flex items-center gap-2">
            <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-forte">
              {dinheiro(bloco.total_recebido)}
            </span>
            <Delta comparativo={bloco.comparativo} />
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[12px] text-sutil">Clientes ativos</span>
          <span className="numerico font-[family-name:var(--font-display)] text-[20px] font-extrabold text-forte">
            {bloco.clientes_ativos}
          </span>
        </div>
      </div>

      {bloco.inadimplentes.length > 0 ? (
        <div className="flex flex-col gap-1.5 rounded-[8px] border border-[var(--st-atrasado-dot)]/30 bg-[var(--st-atrasado-bg)] px-3 py-2.5">
          <span
            className="font-[family-name:var(--font-display)] text-[12px] font-bold"
            style={{ color: "var(--st-atrasado-fg)" }}
          >
            {bloco.inadimplentes.length}{" "}
            {bloco.inadimplentes.length === 1 ? "cliente em atraso" : "clientes em atraso"}
          </span>
          {bloco.inadimplentes.map((c) => (
            <Link
              key={c.cliente_id}
              href={`/clientes/${c.cliente_id}`}
              className="-mx-1.5 flex items-center justify-between gap-3 rounded-[4px] px-1.5 py-0.5 text-[12px] no-underline transition-colors duration-[var(--dur-fast)] hover:bg-[var(--st-atrasado-dot)]/15"
            >
              <span className="min-w-0 flex-1 truncate text-[var(--fg)]">{c.nome}</span>
              <span className="numerico" style={{ color: "var(--st-atrasado-fg)" }}>
                {dinheiro(c.valor_atrasado)}
              </span>
              <span className="text-[11px] text-suave">{c.dias_atraso}d</span>
            </Link>
          ))}
        </div>
      ) : null}

      {bloco.top_clientes.length === 0 ? (
        <EstadoVazio titulo="Nenhum recebimento no período" compacto />
      ) : (
        <ul className="flex flex-col">
          {bloco.top_clientes.map((c) => (
            <li key={c.cliente_id}>
              <Link
                href={`/clientes/${c.cliente_id}`}
                className="-mx-2 flex items-center gap-2.5 rounded-[6px] border-b border-linha-suave px-2 py-2 no-underline transition-colors duration-[var(--dur-fast)] last:border-b-0 hover:bg-[var(--bg-subtle)]"
              >
                <span className="flex size-6 flex-none items-center justify-center rounded-[6px] bg-[var(--brand-tint-2)] font-[family-name:var(--font-display)] text-[10px] font-extrabold text-[var(--lateral-ativo-fg)]">
                  {iniciais(c.nome)}
                </span>
                <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--fg)]">
                  {c.nome}
                </span>
                <span className="numerico text-[13px] font-semibold text-[var(--receita-fg)]">
                  {dinheiro(c.valor)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Cartao>
  );
}

/* ------------------------------------------------------------------ */

/**
 * Custos por cliente (`RF-58`).
 *
 * O outro lado de `BlocoClientes`: mesma mecânica de categoria especial, do
 * lado da despesa. O servidor já mandou custo, receita e margem de cada
 * cliente — aqui não se soma nem se calcula percentual, só se pinta.
 */
export function BlocoCustosCliente({
  bloco,
  rotulo,
}: {
  bloco: NonNullable<Dashboard["card_custos_cliente"]>;
  rotulo: string;
}) {
  const margemNegativa = Number(bloco.margem_total) < 0;

  return (
    <Cartao className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-[8px] bg-[var(--st-atrasado-bg)] text-[var(--st-atrasado-fg)]">
            <Receipt size={16} />
          </span>
          <div className="flex flex-col">
            <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
              {rotulo}
            </span>
            <span className="rotulo-seccao text-[10px]">Categoria especial</span>
          </div>
        </div>
        <Link
          href="/clientes"
          className="flex items-center gap-1 rounded-[6px] px-1.5 py-1 font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--brand-hover)] no-underline transition-colors duration-[var(--dur-fast)] hover:bg-[var(--brand-tint)] hover:text-[var(--brand-press)]"
        >
          Ver clientes <IconeSetaDireita tamanho={13} />
        </Link>
      </div>

      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[12px] text-sutil">Custo no período</span>
          <span className="flex items-center gap-2">
            <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-forte">
              {dinheiro(bloco.custo_total)}
            </span>
            {/* Custo que sobe é notícia ruim — daí o `inverso`. */}
            <Delta comparativo={bloco.comparativo} inverso />
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[12px] text-sutil">Margem no período</span>
          <span
            className="numerico font-[family-name:var(--font-display)] text-[20px] font-extrabold"
            style={{ color: margemNegativa ? "var(--despesa-fg)" : "var(--receita-fg)" }}
          >
            {dinheiro(bloco.margem_total)}
          </span>
        </div>
      </div>

      {bloco.por_cliente.length === 0 ? (
        <EstadoVazio
          titulo="Nenhum custo lançado no período"
          descricao="Lançamentos de despesa na categoria de custo do cliente aparecem aqui, um por cliente."
          compacto
        />
      ) : (
        <ul className="flex flex-col">
          {bloco.por_cliente.map((c) => {
            const negativa = Number(c.margem) < 0;
            return (
              <li key={c.cliente_id}>
                <Link
                  href={`/clientes/${c.cliente_id}`}
                  className="-mx-2 flex items-center gap-2.5 rounded-[6px] border-b border-linha-suave px-2 py-2 no-underline transition-colors duration-[var(--dur-fast)] last:border-b-0 hover:bg-[var(--bg-subtle)]"
                >
                  <span className="flex size-6 flex-none items-center justify-center rounded-[6px] bg-[var(--st-atrasado-bg)] font-[family-name:var(--font-display)] text-[10px] font-extrabold text-[var(--st-atrasado-fg)]">
                    {iniciais(c.nome)}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--fg)]">
                    {c.nome}
                  </span>
                  <span className="numerico text-[13px] font-semibold text-[var(--despesa-fg)]">
                    − {dinheiro(c.custo)}
                  </span>
                  {/* `margem_percentual` vem nulo quando o cliente não faturou no
                      período: sem receita não há percentual, e "0,0%" seria mentira. */}
                  <span
                    className="numerico w-[62px] text-right text-[12px]"
                    style={{
                      color: negativa ? "var(--despesa-fg)" : "var(--receita-fg)",
                    }}
                    title={`Margem: ${dinheiro(c.margem)} sobre ${dinheiro(c.receita)} de receita`}
                  >
                    {percentual(c.margem_percentual, { vazio: "—" })}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      <p className="text-[11px] text-sutil">
        {bloco.clientes_com_custo}{" "}
        {bloco.clientes_com_custo === 1 ? "cliente com custo" : "clientes com custo"} ·{" "}
        {percentual(bloco.percentual_sobre_despesas)} da despesa total do período
      </p>
    </Cartao>
  );
}

/* ------------------------------------------------------------------ */

export function BlocoFuncionarios({
  bloco,
  rotulo,
}: {
  bloco: NonNullable<Dashboard["card_funcionarios"]>;
  rotulo: string;
}) {
  return (
    <Cartao className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-[8px] bg-[var(--st-programado-bg)] text-[var(--st-programado-fg)]">
            <IconeFuncionarios tamanho={16} />
          </span>
          <div className="flex flex-col">
            <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
              {rotulo}
            </span>
            <span className="rotulo-seccao text-[10px]">Categoria especial</span>
          </div>
        </div>
        <Link
          href="/funcionarios"
          className="flex items-center gap-1 rounded-[6px] px-1.5 py-1 font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--brand-hover)] no-underline transition-colors duration-[var(--dur-fast)] hover:bg-[var(--brand-tint)] hover:text-[var(--brand-press)]"
        >
          Ver todos <IconeSetaDireita tamanho={13} />
        </Link>
      </div>

      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[12px] text-sutil">Folha do período</span>
          <span className="flex items-center gap-2">
            <span className="numerico font-[family-name:var(--font-display)] text-[24px] font-extrabold tracking-[-0.03em] text-forte">
              {dinheiro(bloco.custo_total)}
            </span>
            <Delta comparativo={bloco.comparativo} inverso />
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[12px] text-sutil">Da despesa total</span>
          <span className="numerico font-[family-name:var(--font-display)] text-[20px] font-extrabold text-forte">
            {percentual(bloco.percentual_sobre_despesas)}
          </span>
        </div>
      </div>

      {bloco.por_funcionario.length === 0 ? (
        <EstadoVazio titulo="Nenhum pagamento no período" compacto />
      ) : (
        <ul className="flex flex-col">
          {bloco.por_funcionario.map((f) => (
            <li key={f.funcionario_id}>
              <Link
                href={`/funcionarios/${f.funcionario_id}`}
                className="-mx-2 flex items-center gap-2.5 rounded-[6px] border-b border-linha-suave px-2 py-2 no-underline transition-colors duration-[var(--dur-fast)] last:border-b-0 hover:bg-[var(--bg-subtle)]"
              >
                <span className="flex size-6 flex-none items-center justify-center rounded-[6px] bg-[var(--st-programado-bg)] font-[family-name:var(--font-display)] text-[10px] font-extrabold text-[var(--st-programado-fg)]">
                  {iniciais(f.nome)}
                </span>
                <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--fg)]">
                  {f.nome}
                </span>
                <span className="numerico text-[13px] font-semibold text-[var(--despesa-fg)]">
                  {dinheiro(f.valor)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {bloco.proximos_pagamentos.length > 0 ? (
        <p className="rounded-[8px] bg-[var(--st-efetivado-bg)] px-3 py-2 text-[12px] text-[var(--st-efetivado-fg)]">
          Próxima folha: {dataCurta(bloco.proximos_pagamentos[0].data)} ·{" "}
          {dinheiro(
            bloco.proximos_pagamentos.reduce((a, p) => a + Number(p.valor), 0).toFixed(2),
          )}{" "}
          — geração automática
        </p>
      ) : null}
    </Cartao>
  );
}

/* ------------------------------------------------------------------ */

export function TopDespesas({
  itens,
  rotulo,
  aoAbrir,
}: {
  itens: Dashboard["top_despesas"];
  rotulo: string;
  aoAbrir: (id: string) => void;
}) {
  return (
    <Cartao className="flex flex-col gap-3">
      <div className="flex flex-col">
        <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
          {rotulo}
        </span>
        <span className="text-[12px] text-sutil">Clique para abrir o lançamento</span>
      </div>
      {itens.length === 0 ? (
        <EstadoVazio titulo="Nenhuma despesa no período" compacto />
      ) : (
        <ol className="flex flex-col">
          {itens.map((d, i) => (
            <li key={d.lancamento_id}>
              <button
                type="button"
                onClick={() => aoAbrir(d.lancamento_id)}
                className="flex w-full items-center gap-3 border-b border-linha-suave py-2.5 text-left last:border-b-0"
              >
                <span className="flex size-[22px] flex-none items-center justify-center rounded-[6px] bg-[var(--bg-subtle)] font-mono text-[11px] text-suave">
                  {i + 1}
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-[13px] text-[var(--fg)]">{d.descricao}</span>
                  <span className="text-[11px] text-sutil">{dataCurta(d.data)}</span>
                </span>
                <span className="numerico text-[13px] font-semibold text-[var(--despesa-fg)]">
                  − {dinheiro(d.valor)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </Cartao>
  );
}

/* ------------------------------------------------------------------ */

export function ReceitaPorServico({
  itens,
  rotulo,
}: {
  itens: Dashboard["receita_por_servico"];
  rotulo: string;
}) {
  const maior = Math.max(...itens.map((i) => Number(i.valor)), 1);
  return (
    <Cartao className="flex flex-col gap-3">
      <div className="flex flex-col">
        <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
          {rotulo}
        </span>
        <span className="text-[12px] text-sutil">
          Quais linhas de negócio pagaram as contas no período
        </span>
      </div>
      {itens.length === 0 ? (
        <EstadoVazio titulo="Nenhuma receita com serviço vinculado" compacto />
      ) : (
        <ul className="flex flex-col gap-3">
          {itens.map((s) => (
            <li key={s.servico_id} className="flex flex-col gap-1.5">
              <span className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate text-[13px] text-[var(--fg)]">{s.nome}</span>
                <span className="flex items-baseline gap-2 whitespace-nowrap">
                  <span className="numerico text-[13px] font-semibold text-forte">
                    {dinheiro(s.valor)}
                  </span>
                  <span className="numerico text-[12px] text-sutil">
                    {percentual(s.percentual)}
                  </span>
                </span>
              </span>
              <span className="h-[6px] w-full overflow-hidden rounded-full bg-[var(--bg-subtle)]">
                <span
                  className="block h-full rounded-full"
                  style={{
                    width: `${(Number(s.valor) / maior) * 100}%`,
                    background: `var(--mundo-${s.mundo})`,
                  }}
                />
              </span>
            </li>
          ))}
        </ul>
      )}
    </Cartao>
  );
}

/* ------------------------------------------------------------------ */

const DIA_DA_SEMANA = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"];

export function LinhaTempo7Dias({
  dias,
  rotulo,
  aoAbrir,
}: {
  dias: Dashboard["proximos_7_dias"];
  rotulo: string;
  aoAbrir: (id: string) => void;
}) {
  const totalReceber = dias
    .flatMap((d) => d.a_receber)
    .reduce((a, l) => a + Number(l.valor), 0);
  const totalPagar = dias.flatMap((d) => d.a_pagar).reduce((a, l) => a + Number(l.valor), 0);

  return (
    <Cartao className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col">
          <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
            {rotulo}
          </span>
          <span className="text-[12px] text-sutil">O que precisa de atenção esta semana</span>
        </div>
        <div className="flex gap-6">
          <span className="flex flex-col items-end">
            <span className="text-[11px] text-sutil">A receber</span>
            <span className="numerico font-[family-name:var(--font-display)] text-[14px] font-bold text-[var(--receita-fg)]">
              {dinheiro(totalReceber)}
            </span>
          </span>
          <span className="flex flex-col items-end">
            <span className="text-[11px] text-sutil">A pagar</span>
            <span className="numerico font-[family-name:var(--font-display)] text-[14px] font-bold text-[var(--despesa-fg)]">
              {dinheiro(totalPagar)}
            </span>
          </span>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-4 xl:grid-cols-7">
        {dias.map((d) => {
          const [ano, mes, dia] = d.data.split("-").map(Number);
          const semana = DIA_DA_SEMANA[new Date(ano, mes - 1, dia).getDay()];
          const itens = [
            ...d.a_receber.map((l) => ({ ...l, receita: true })),
            ...d.a_pagar.map((l) => ({ ...l, receita: false })),
          ];
          return (
            <div
              key={d.data}
              className={cn(
                "flex min-h-[104px] flex-col gap-2 rounded-[10px] border border-linha-suave p-2.5",
                itens.length === 0 ? "bg-[var(--bg-subtle)]" : "bg-superficie-cartao",
              )}
            >
              <span className="flex items-baseline justify-between">
                <span className="numerico font-[family-name:var(--font-display)] text-[13px] font-bold text-forte">
                  {String(dia).padStart(2, "0")}/{String(mes).padStart(2, "0")}
                </span>
                <span className="text-[10px] tracking-[0.06em] text-sutil">{semana}</span>
              </span>
              {itens.length === 0 ? (
                <span className="mt-2 text-[11px] text-sutil">Nada previsto</span>
              ) : (
                itens.map((l) => (
                  <button
                    key={l.lancamento_id}
                    type="button"
                    onClick={() => aoAbrir(l.lancamento_id)}
                    className="flex flex-col gap-1 text-left"
                  >
                    <span className="line-clamp-2 text-[11px] text-suave">{l.descricao}</span>
                    <span className="flex items-center gap-1.5">
                      <span
                        className="numerico text-[12px] font-semibold"
                        style={{
                          color: l.receita ? "var(--receita-fg)" : "var(--despesa-fg)",
                        }}
                      >
                        {l.receita ? "+ " : "− "}
                        {dinheiro(l.valor)}
                      </span>
                      <span
                        className="rounded-full px-1.5 py-[1px] text-[9px] font-bold"
                        style={{
                          background: `var(--st-${l.status}-bg)`,
                          color: `var(--st-${l.status}-fg)`,
                        }}
                      >
                        {rotuloDoStatus(l.status)}
                      </span>
                    </span>
                  </button>
                ))
              )}
            </div>
          );
        })}
      </div>
    </Cartao>
  );
}
