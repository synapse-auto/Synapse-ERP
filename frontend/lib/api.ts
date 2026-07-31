/**
 * Cliente HTTP tipado (T148).
 *
 * Duas regras que este arquivo existe para garantir:
 *
 * 1. **O texto de erro de regra de negócio vem do backend** (`RNF-02`,
 *    Princípio VII). Aqui nunca se monta frase de `RN-xx`. O que chega em
 *    `erro.mensagem` já está em PT-BR pronto para a tela; a tela mostra.
 *    Só há texto próprio para o que o backend não pode responder: rede caída
 *    e resposta que não é JSON.
 * 2. **Mesma origem, sem CORS**: as chamadas vão para `/api/...` e o
 *    `next.config.ts` reescreve para o backend (research.md D-02).
 */

import { sessaoAtual } from "./supabase";

export type CodigoErro =
  | "validacao"
  | "nao_autenticado"
  | "sem_permissao"
  | "nao_encontrado"
  | "conflito_versao"
  | "regra_violada"
  | "arquivo_grande"
  | "formato_nao_suportado"
  | "confirmacao_necessaria"
  | "fonte_externa_indisponivel"
  | "sem_resposta"
  | "resposta_invalida";

/** O corpo de erro único de contracts/README.md §Erros. */
export interface CorpoErro {
  codigo: CodigoErro | string;
  mensagem: string;
  requisito?: string | null;
  campos?: Record<string, string> | null;
  /** Presente só no `422 confirmacao_necessaria` (`FR-027`). */
  previa?: Record<string, unknown> | null;
}

/**
 * Erro de API. `mensagem` é a do backend — a tela mostra sem reescrever.
 */
export class ErroApi extends Error {
  readonly status: number;
  readonly codigo: string;
  readonly requisito: string | null;
  readonly campos: Record<string, string> | null;
  readonly previa: Record<string, unknown> | null;

  constructor(status: number, corpo: CorpoErro) {
    super(corpo.mensagem);
    this.name = "ErroApi";
    this.status = status;
    this.codigo = corpo.codigo;
    this.requisito = corpo.requisito ?? null;
    this.campos = corpo.campos ?? null;
    this.previa = corpo.previa ?? null;
  }

  /** `422` pedindo confirmação explícita (contracts/README.md §Confirmação). */
  get pedeConfirmacao(): boolean {
    return this.status === 422 && this.codigo === "confirmacao_necessaria";
  }

  /** `409` de edição concorrente (data-model §5.6). */
  get conflitoDeVersao(): boolean {
    return this.status === 409 && this.codigo === "conflito_versao";
  }

  get semPermissao(): boolean {
    return this.status === 403;
  }

  get naoAutenticado(): boolean {
    return this.status === 401;
  }
}

export interface Paginacao {
  pagina: number;
  por_pagina: number;
  total: number;
  total_paginas: number;
}

export interface Pagina<T> {
  itens: T[];
  paginacao: Paginacao;
}

/** Valores aceitos numa query string. `undefined` e `null` somem. */
export type Consulta = Record<
  string,
  string | number | boolean | null | undefined | Array<string | number>
>;

export interface OpcoesPedido {
  consulta?: Consulta;
  corpo?: unknown;
  /** `Idempotency-Key` — só nos POST que o contrato aceita. */
  chaveIdempotencia?: string;
  sinal?: AbortSignal;
  /** Para upload de anexo: manda `FormData` sem `Content-Type` próprio. */
  formulario?: FormData;
  /** Quando a resposta é arquivo (CSV, PDF, ZIP). */
  binario?: boolean;
  cabecalhos?: Record<string, string>;
}

export function paraQueryString(consulta: Consulta | undefined): string {
  if (!consulta) return "";
  const p = new URLSearchParams();
  for (const [chave, valor] of Object.entries(consulta)) {
    if (valor === null || valor === undefined || valor === "") continue;
    if (Array.isArray(valor)) {
      for (const v of valor) p.append(chave, String(v));
    } else {
      p.append(chave, String(valor));
    }
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

const ERRO_SEM_RESPOSTA: CorpoErro = {
  codigo: "sem_resposta",
  mensagem: "Não foi possível falar com o servidor. Verifique a conexão e tente de novo.",
  requisito: null,
};

const ERRO_RESPOSTA_INVALIDA: CorpoErro = {
  codigo: "resposta_invalida",
  mensagem: "O servidor respondeu em um formato que não era esperado.",
  requisito: null,
};

/**
 * Quem lida com o `401`. Definido uma vez pelo provedor de sessão para que
 * qualquer chamada expirada mande para a tela de entrar, em vez de cada
 * componente tratar por conta.
 */
let aoPerderSessao: (() => void) | null = null;

export function registrarPerdaDeSessao(fn: (() => void) | null): void {
  aoPerderSessao = fn;
}

async function pedido<T>(metodo: string, rota: string, opcoes: OpcoesPedido = {}): Promise<T> {
  const url = `${rota}${paraQueryString(opcoes.consulta)}`;

  const cabecalhos: Record<string, string> = { ...opcoes.cabecalhos };
  const sessao = await sessaoAtual();
  if (sessao?.access_token) cabecalhos.Authorization = `Bearer ${sessao.access_token}`;
  if (opcoes.chaveIdempotencia) cabecalhos["Idempotency-Key"] = opcoes.chaveIdempotencia;

  let body: BodyInit | undefined;
  if (opcoes.formulario) {
    // Sem `Content-Type`: o navegador põe o boundary do multipart.
    body = opcoes.formulario;
  } else if (opcoes.corpo !== undefined) {
    cabecalhos["Content-Type"] = "application/json";
    body = JSON.stringify(opcoes.corpo);
  }

  let resposta: Response;
  try {
    resposta = await fetch(url, {
      method: metodo,
      headers: cabecalhos,
      body,
      signal: opcoes.sinal,
      credentials: "same-origin",
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ErroApi(0, ERRO_SEM_RESPOSTA);
  }

  if (resposta.status === 401 && aoPerderSessao) aoPerderSessao();

  if (resposta.status === 204) return undefined as T;

  if (opcoes.binario && resposta.ok) {
    return (await resposta.blob()) as T;
  }

  const texto = await resposta.text();
  let dados: unknown = null;
  if (texto) {
    try {
      dados = JSON.parse(texto);
    } catch {
      if (!resposta.ok) throw new ErroApi(resposta.status, ERRO_RESPOSTA_INVALIDA);
      throw new ErroApi(resposta.status, ERRO_RESPOSTA_INVALIDA);
    }
  }

  if (!resposta.ok) {
    const corpo = (dados as { erro?: CorpoErro } | null)?.erro;
    // Um erro sem o envelope acordado é bug de contrato, não caso de uso:
    // mostramos o genérico e o status fica no objeto para o relato.
    throw new ErroApi(resposta.status, corpo ?? ERRO_RESPOSTA_INVALIDA);
  }

  return dados as T;
}

export const api = {
  get: <T>(rota: string, opcoes?: OpcoesPedido) => pedido<T>("GET", rota, opcoes),
  post: <T>(rota: string, opcoes?: OpcoesPedido) => pedido<T>("POST", rota, opcoes),
  put: <T>(rota: string, opcoes?: OpcoesPedido) => pedido<T>("PUT", rota, opcoes),
  patch: <T>(rota: string, opcoes?: OpcoesPedido) => pedido<T>("PATCH", rota, opcoes),
  delete: <T>(rota: string, opcoes?: OpcoesPedido) => pedido<T>("DELETE", rota, opcoes),
};

/**
 * Texto de erro pronto para a tela. Vem do backend sempre que o backend
 * respondeu; o texto local existe só para "não deu para perguntar".
 */
export function mensagemDoErro(e: unknown): string {
  if (e instanceof ErroApi) return e.message;
  if (e instanceof Error && e.name === "AbortError") return "";
  return ERRO_SEM_RESPOSTA.mensagem;
}

/** Baixa um arquivo devolvido pela API sem sair da página. */
export async function baixarArquivo(
  rota: string,
  nomeSugerido: string,
  opcoes: OpcoesPedido = {},
): Promise<void> {
  const blob = await pedido<Blob>(opcoes.corpo !== undefined ? "POST" : "GET", rota, {
    ...opcoes,
    binario: true,
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeSugerido;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Chave de idempotência para os POST de criação (contracts/README.md). */
export function novaChaveIdempotencia(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
