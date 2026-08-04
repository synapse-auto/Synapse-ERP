import { describe, expect, it } from "vitest";
import { moverNaLista } from "@/componentes/dashboard/ConfigurarCards";

/**
 * Reordenação do "Configurar cards" (T217).
 *
 * A distinção que estes testes travam: arrastar **insere**, não troca. Com
 * troca, puxar o primeiro card para o fim jogaria o último para o começo — e
 * quem arrasta não espera isso.
 */
describe("moverNaLista", () => {
  const base = ["a", "b", "c", "d"];

  it("insere no destino em vez de trocar de lugar", () => {
    expect(moverNaLista(base, 0, 3)).toEqual(["b", "c", "d", "a"]);
    expect(moverNaLista(base, 3, 0)).toEqual(["d", "a", "b", "c"]);
  });

  it("com passo de 1 vale como as setas ↑↓", () => {
    expect(moverNaLista(base, 1, 0)).toEqual(["b", "a", "c", "d"]);
    expect(moverNaLista(base, 1, 2)).toEqual(["a", "c", "b", "d"]);
  });

  it("não sai da lista nem altera o original", () => {
    expect(moverNaLista(base, 0, -1)).toBe(base);
    expect(moverNaLista(base, 0, 4)).toBe(base);
    expect(moverNaLista(base, 2, 2)).toBe(base);
    expect(base).toEqual(["a", "b", "c", "d"]);
  });
});
