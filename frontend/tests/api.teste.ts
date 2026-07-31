import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroApi, mensagemDoErro, paraQueryString } from "@/lib/api";

/**
 * `RNF-02` — o texto de erro de regra de negócio vem do backend.
 * Estes testes existem para impedir que alguém volte a montar frase de
 * `RN-xx` no frontend.
 */

function respostaJson(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("paraQueryString", () => {
  it("poda vazios e repete os parâmetros de lista", () => {
    const s = paraQueryString({
      mundo: "digital",
      busca: "",
      pagina: 1,
      status: ["atrasado", "pendente"],
      nada: null,
    });
    expect(s).toBe("?mundo=digital&pagina=1&status=atrasado&status=pendente");
  });

  it("devolve string vazia quando não há nada", () => {
    expect(paraQueryString(undefined)).toBe("");
    expect(paraQueryString({})).toBe("");
  });
});

describe("ErroApi", () => {
  it("mostra a mensagem do backend, sem reescrever", async () => {
    const mensagem =
      "A soma das partes (R$ 480,00) não fecha com o valor do lançamento (R$ 500,00).";
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      respostaJson(409, {
        erro: {
          codigo: "regra_violada",
          mensagem,
          requisito: "RN-11",
          campos: { partes: "Faltam R$ 20,00." },
        },
      }),
    );

    await expect(api.post("/api/lancamentos/1/dividir")).rejects.toMatchObject({
      status: 409,
      codigo: "regra_violada",
      requisito: "RN-11",
      message: mensagem,
    });
  });

  it("reconhece o 422 de confirmação com a prévia", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      respostaJson(422, {
        erro: {
          codigo: "confirmacao_necessaria",
          mensagem: "Serão criadas 17 ocorrências.",
          requisito: "FR-027",
          previa: { total_ocorrencias: 17 },
        },
      }),
    );

    try {
      await api.post("/api/recorrencias");
      expect.unreachable("deveria ter lançado");
    } catch (e) {
      expect(e).toBeInstanceOf(ErroApi);
      const erro = e as ErroApi;
      expect(erro.pedeConfirmacao).toBe(true);
      expect(erro.previa).toEqual({ total_ocorrencias: 17 });
    }
  });

  it("marca conflito de versão", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      respostaJson(409, {
        erro: { codigo: "conflito_versao", mensagem: "Outra pessoa editou.", requisito: null },
      }),
    );
    try {
      await api.put("/api/lancamentos/1");
    } catch (e) {
      expect((e as ErroApi).conflitoDeVersao).toBe(true);
    }
  });

  it("tem texto próprio só para rede caída", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(new TypeError("fail"));
    try {
      await api.get("/api/saldo");
    } catch (e) {
      expect((e as ErroApi).codigo).toBe("sem_resposta");
      expect(mensagemDoErro(e)).toContain("Verifique a conexão");
    }
  });

  it("204 não tenta virar JSON", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.delete("/api/lancamentos/1")).resolves.toBeUndefined();
  });
});
