import { describe, expect, it } from "vitest";
import {
  daUrl,
  deDrilldown,
  FILTROS_VAZIOS,
  paraConsulta,
  quantidadeAtiva,
} from "@/componentes/lancamentos/filtros";

describe("paraConsulta", () => {
  it("omite tudo que está vazio", () => {
    const c = paraConsulta(FILTROS_VAZIOS);
    expect(c.busca).toBeUndefined();
    expect(c.tipo).toBeUndefined();
    expect(c.status).toBeUndefined();
    expect(c.mundo).toBeUndefined();
    expect(c.ordenar).toBe("data");
  });

  it("manda o mundo da lista só quando ele existe", () => {
    // O seletor global manda por padrão; o filtro da lista sobrepõe.
    expect(paraConsulta({ ...FILTROS_VAZIOS, mundoDaLista: "infra" }).mundo).toBe("infra");
  });
});

describe("deDrilldown", () => {
  it("aceita o corpo pronto que o Dashboard manda", () => {
    // `FR-058`: o filtro vem montado do servidor; a tela só acomoda.
    const f = deDrilldown({ tipo: "receita", status: ["programado", "pendente", "atrasado"] });
    expect(f.tipo).toBe("receita");
    expect(f.status).toEqual(["programado", "pendente", "atrasado"]);
    expect(f.pagina).toBe(1);
  });

  it("aceita valor único onde o contrato usa lista", () => {
    expect(deDrilldown({ categoria_id: "abc" }).categoria_id).toEqual(["abc"]);
  });

  it("não inventa filtro quando não vem nada", () => {
    expect(deDrilldown(null)).toEqual({});
  });
});

describe("daUrl", () => {
  it("lê filtros repetidos da query string", () => {
    const p = new URLSearchParams("status=atrasado&status=pendente&categoria_id=x");
    const f = daUrl(p);
    expect(f.status).toEqual(["atrasado", "pendente"]);
    expect(f.categoria_id).toEqual(["x"]);
  });
});

describe("quantidadeAtiva", () => {
  it("conta cada marcador removível separadamente", () => {
    expect(quantidadeAtiva(FILTROS_VAZIOS)).toBe(0);
    expect(
      quantidadeAtiva({
        ...FILTROS_VAZIOS,
        busca: "nota",
        tipo: "despesa",
        status: ["atrasado", "pendente"],
        tag_id: ["a"],
      }),
    ).toBe(5);
  });

  it("não conta espaço em branco como busca", () => {
    expect(quantidadeAtiva({ ...FILTROS_VAZIOS, busca: "   " })).toBe(0);
  });
});
