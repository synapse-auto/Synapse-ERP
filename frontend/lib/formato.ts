/**
 * Formatação brasileira (`RNF-03`).
 *
 * A API transporta dinheiro como string decimal (`"1234.56"`) e data como
 * ISO (`"2026-07-31"`). Nada disso é mostrado cru: aqui vira `R$ 1.234,56` e
 * `31/07/2026`. A conversão só acontece na fronteira da tela — o estado da
 * aplicação guarda o que veio da API.
 *
 * Nunca `parseFloat` em dinheiro para depois somar: contas de dinheiro são do
 * backend (`numeric(14,2)`). Aqui o `Number` existe só para o `Intl` desenhar.
 */

const LOCALE = "pt-BR";

/** Moedas que o sistema transporta hoje (`RN-12`). */
export type Moeda = "BRL" | "USD";

const formatadores = new Map<string, Intl.NumberFormat>();

function formatador(chave: string, opcoes: Intl.NumberFormatOptions): Intl.NumberFormat {
  let f = formatadores.get(chave);
  if (!f) {
    f = new Intl.NumberFormat(LOCALE, opcoes);
    formatadores.set(chave, f);
  }
  return f;
}

/**
 * `"1234.56"` → `"R$ 1.234,56"`. Aceita string (o formato da API), number ou
 * `null`/`undefined` — ausência vira travessão, não `R$ 0,00`, porque "não
 * tem valor" e "vale zero" são coisas diferentes na tela.
 */
export function dinheiro(
  valor: string | number | null | undefined,
  opcoes: { moeda?: Moeda; sinal?: boolean; semSimbolo?: boolean; vazio?: string } = {},
): string {
  const { moeda = "BRL", sinal = false, semSimbolo = false, vazio = "—" } = opcoes;
  if (valor === null || valor === undefined || valor === "") return vazio;

  const n = typeof valor === "number" ? valor : Number(valor);
  if (!Number.isFinite(n)) return vazio;

  const texto = semSimbolo
    ? formatador("decimal2", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(Math.abs(n))
    : formatador(`moeda-${moeda}`, {
        style: "currency",
        currency: moeda,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(Math.abs(n));

  if (n < 0) return `−${texto}`;
  if (sinal && n > 0) return `+${texto}`;
  return texto;
}

/**
 * Versão curta para eixo de gráfico e card apertado: `R$ 12,4 mil`,
 * `R$ 1,2 mi`. Só onde o número exato já está em outro lugar da tela.
 */
export function dinheiroCurto(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = typeof valor === "number" ? valor : Number(valor);
  if (!Number.isFinite(n)) return "—";

  const abs = Math.abs(n);
  const sinal = n < 0 ? "−" : "";
  const um = (v: number) => formatador("um", { maximumFractionDigits: 1 }).format(v);

  if (abs >= 1_000_000) return `${sinal}R$ ${um(abs / 1_000_000)} mi`;
  if (abs >= 1_000) return `${sinal}R$ ${um(abs / 1_000)} mil`;
  return `${sinal}R$ ${formatador("zero", { maximumFractionDigits: 0 }).format(abs)}`;
}

/** `"12.5"` → `"12,5%"`. `null` vira `"—"` — que é o que a API manda quando o
 * período anterior é zero e o percentual não existe (contracts/consultas.md §1). */
export function percentual(
  valor: string | number | null | undefined,
  opcoes: { casas?: number; sinal?: boolean; vazio?: string } = {},
): string {
  const { casas = 1, sinal = false, vazio = "—" } = opcoes;
  if (valor === null || valor === undefined || valor === "") return vazio;
  const n = typeof valor === "number" ? valor : Number(valor);
  if (!Number.isFinite(n)) return vazio;

  const texto = formatador(`pct-${casas}`, {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(Math.abs(n));

  if (n < 0) return `−${texto}%`;
  if (sinal && n > 0) return `+${texto}%`;
  return `${texto}%`;
}

/** Inteiro com separador de milhar: `1234` → `"1.234"`. */
export function inteiro(valor: number | string | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = typeof valor === "number" ? valor : Number(valor);
  if (!Number.isFinite(n)) return "—";
  return formatador("inteiro", { maximumFractionDigits: 0 }).format(n);
}

/**
 * Converte `"2026-07-31"` em `Date` **local**, sem passar pelo fuso.
 * `new Date("2026-07-31")` é interpretado como UTC e, no Brasil (UTC−3),
 * volta como dia 30. Esse bug de um dia é o mais fácil de cometer aqui.
 */
export function dataDaApi(iso: string): Date {
  const [ano, mes, dia] = iso.slice(0, 10).split("-").map(Number);
  return new Date(ano, mes - 1, dia);
}

/** `Date` → `"YYYY-MM-DD"` no fuso local, para mandar de volta à API. */
export function paraApi(data: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${data.getFullYear()}-${p(data.getMonth() + 1)}-${p(data.getDate())}`;
}

/** `"2026-07-31"` → `"31/07/2026"` (`RNF-03`). */
export function data(iso: string | null | undefined, vazio = "—"): string {
  if (!iso) return vazio;
  return new Intl.DateTimeFormat(LOCALE, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(dataDaApi(iso));
}

/** `"2026-07-31"` → `"31 jul"` — para eixo e linha do tempo. */
export function dataCurta(iso: string | null | undefined, vazio = "—"): string {
  if (!iso) return vazio;
  return new Intl.DateTimeFormat(LOCALE, { day: "2-digit", month: "short" })
    .format(dataDaApi(iso))
    .replace(".", "");
}

/** `"2026-07-31"` → `"sexta-feira, 31 de julho de 2026"` — cabeçalho de grupo. */
export function dataPorExtenso(iso: string | null | undefined, vazio = "—"): string {
  if (!iso) return vazio;
  return new Intl.DateTimeFormat(LOCALE, {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(dataDaApi(iso));
}

/** `"2026-07"` ou `"2026-07-01"` → `"jul/26"` — eixo de série mensal. */
export function mesCurto(iso: string | null | undefined, vazio = "—"): string {
  if (!iso) return vazio;
  const d = iso.length === 7 ? dataDaApi(`${iso}-01`) : dataDaApi(iso);
  const mes = new Intl.DateTimeFormat(LOCALE, { month: "short" }).format(d).replace(".", "");
  return `${mes}/${String(d.getFullYear()).slice(2)}`;
}

/** `"2026-07-01"` → `"Julho de 2026"` — título de período. */
export function mesPorExtenso(iso: string | null | undefined, vazio = "—"): string {
  if (!iso) return vazio;
  const d = iso.length === 7 ? dataDaApi(`${iso}-01`) : dataDaApi(iso);
  const texto = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric" }).format(d);
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** Instante ISO com fuso → `"31/07/2026 às 14:03"` — linha do tempo de auditoria. */
export function instante(iso: string | null | undefined, vazio = "—"): string {
  if (!iso) return vazio;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return vazio;
  const dia = new Intl.DateTimeFormat(LOCALE, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);
  const hora = new Intl.DateTimeFormat(LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
  return `${dia} às ${hora}`;
}

/** `"há 3 dias"`, `"em 2 meses"` — usado no `dias_restantes` da lixeira e nos avisos. */
export function relativo(dias: number): string {
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  if (Math.abs(dias) >= 30) return rtf.format(Math.trunc(dias / 30), "month");
  return rtf.format(dias, "day");
}

/**
 * Intervalo de datas como o cabeçalho do mockup escreve:
 * `"01 a 31/07"` quando é o mesmo mês, `"01/06 a 31/07/2026"` quando não é.
 */
export function intervalo(inicio: string, fim: string): string {
  const a = dataDaApi(inicio);
  const b = dataDaApi(fim);
  const p = (n: number) => String(n).padStart(2, "0");
  if (a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()) {
    return `${p(a.getDate())} a ${p(b.getDate())}/${p(b.getMonth() + 1)}`;
  }
  if (a.getFullYear() === b.getFullYear()) {
    return `${p(a.getDate())}/${p(a.getMonth() + 1)} a ${p(b.getDate())}/${p(b.getMonth() + 1)}/${b.getFullYear()}`;
  }
  return `${data(inicio)} a ${data(fim)}`;
}

/** Iniciais para avatar: `"Lucas Mendes"` → `"LM"`. */
export function iniciais(nome: string | null | undefined): string {
  if (!nome) return "?";
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

/** Plural simples em PT-BR, para contadores: `contar(1, "lançamento")`. */
export function contar(n: number, singular: string, plural = `${singular}s`): string {
  return `${inteiro(n)} ${n === 1 ? singular : plural}`;
}
