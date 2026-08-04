import { describe, expect, it } from "vitest";
import {
  daUrl,
  deDrilldown,
  FILTROS_VAZIOS,
  paraConsulta,
  paraUrl,
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

describe("paraUrl", () => {
  it("não escreve nada quando nenhum filtro está ligado", () => {
    const base = new URLSearchParams("mundo=ambos&periodo=este_mes");
    expect(paraUrl(FILTROS_VAZIOS, base).toString()).toBe("mundo=ambos&periodo=este_mes");
  });

  it("preserva mundo, período e o lançamento aberto", () => {
    const base = new URLSearchParams("mundo=infra&periodo=este_ano&selecionado=abc");
    const url = paraUrl({ ...FILTROS_VAZIOS, tipo: "despesa" }, base);
    expect(url.get("mundo")).toBe("infra");
    expect(url.get("periodo")).toBe("este_ano");
    expect(url.get("selecionado")).toBe("abc");
    expect(url.get("tipo")).toBe("despesa");
  });

  it("manda o mundo da lista como `mundo_lista`, sem atropelar o mundo global", () => {
    const base = new URLSearchParams("mundo=ambos");
    const url = paraUrl({ ...FILTROS_VAZIOS, mundoDaLista: "digital" }, base);
    expect(url.get("mundo")).toBe("ambos");
    expect(url.get("mundo_lista")).toBe("digital");
  });

  it("dá a volta completa: filtros → URL → filtros", () => {
    const filtros = {
      ...FILTROS_VAZIOS,
      busca: "nota fiscal",
      tipo: "receita" as const,
      status: ["atrasado" as const, "pendente" as const],
      categoria_id: ["c1", "c2"],
      tag_id: ["t1"],
      valor_min: "100.00",
      valor_max: "5000.00",
      mundoDaLista: "infra" as const,
      ordenar: "valor" as const,
      direcao: "asc" as const,
      pagina: 3,
    };
    const url = paraUrl(filtros, new URLSearchParams("mundo=ambos"));
    expect({ ...FILTROS_VAZIOS, ...daUrl(url) }).toEqual(filtros);
  });

  it("limpa da URL o filtro que foi desligado", () => {
    const comFiltro = paraUrl({ ...FILTROS_VAZIOS, tipo: "receita" }, new URLSearchParams());
    const semFiltro = paraUrl(FILTROS_VAZIOS, comFiltro);
    expect(semFiltro.get("tipo")).toBeNull();
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
