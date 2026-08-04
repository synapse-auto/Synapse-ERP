import { describe, expect, it } from "vitest";
import {
  contar,
  data,
  dataDaApi,
  dinheiro,
  dinheiroCurto,
  iniciais,
  instante,
  intervalo,
  mesAno,
  mesCurto,
  paraApi,
  percentual,
  tempoDeCasa,
} from "@/lib/formato";

/**
 * `RNF-03` — dinheiro em `R$ 1.234,56` e data em `dd/mm/aaaa`.
 * A API transporta ISO e decimal em string; nada disso chega cru à tela.
 *
 * O `Intl` do pt-BR separa o símbolo do número com **espaço inquebrável**
 * (U+00A0), e é isso que a tela deve mostrar — quebrar "R$" do valor no fim
 * da linha ficaria feio. Nos testes o espaço é normalizado para o literal
 * ficar legível.
 */
const semNbsp = (s: string) => s.replace(/ /g, " ");

describe("dinheiro", () => {
  it("formata a string decimal da API no padrão brasileiro", () => {
    expect(semNbsp(dinheiro("1234.56"))).toBe("R$ 1.234,56");
    expect(semNbsp(dinheiro("0"))).toBe("R$ 0,00");
  });

  it("distingue ausência de zero", () => {
    // "não tem valor" e "vale zero" são coisas diferentes na tela.
    expect(dinheiro(null)).toBe("—");
    expect(dinheiro(undefined)).toBe("—");
    expect(dinheiro("")).toBe("—");
    expect(semNbsp(dinheiro("0.00"))).toBe("R$ 0,00");
  });

  it("usa o menos tipográfico no negativo", () => {
    expect(semNbsp(dinheiro("-500"))).toBe("−R$ 500,00");
  });

  it("abrevia sem perder o sinal", () => {
    expect(dinheiroCurto("12400")).toBe("R$ 12,4 mil");
    expect(dinheiroCurto("1200000")).toBe("R$ 1,2 mi");
    expect(dinheiroCurto("-2500")).toBe("−R$ 2,5 mil");
  });
});

describe("percentual", () => {
  it("devolve travessão quando a variação não existe", () => {
    // O backend manda `null` quando o período anterior é zero: "não dá para
    // calcular" é diferente de "não mudou" (contracts/consultas.md §1).
    expect(percentual(null)).toBe("—");
    expect(percentual("0")).toBe("0,0%");
  });
});

describe("datas", () => {
  it("lê a data da API no fuso local, sem perder um dia", () => {
    // `new Date("2026-07-31")` é UTC e, no Brasil, voltaria dia 30.
    const d = dataDaApi("2026-07-31");
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(6);
    expect(d.getDate()).toBe(31);
  });

  it("ida e volta com a API não muda o dia", () => {
    expect(paraApi(dataDaApi("2026-01-01"))).toBe("2026-01-01");
    expect(paraApi(dataDaApi("2026-12-31"))).toBe("2026-12-31");
  });

  it("formata dd/mm/aaaa", () => {
    expect(data("2026-07-31")).toBe("31/07/2026");
    expect(data(null)).toBe("—");
  });

  it("escreve o mês curto como o eixo dos gráficos", () => {
    expect(mesCurto("2026-07")).toBe("jul/26");
    expect(mesCurto("2026-07-01")).toBe("jul/26");
  });

  it("escreve o intervalo compacto quando é o mesmo mês", () => {
    expect(intervalo("2026-07-01", "2026-07-31")).toBe("01 a 31/07");
    expect(intervalo("2026-06-01", "2026-07-31")).toBe("01/06 a 31/07/2026");
  });

  it("formata instante com fuso", () => {
    expect(instante("2026-07-31T14:03:00-03:00")).toMatch(/^31\/07\/2026 às \d{2}:\d{2}$/);
  });
});

describe("apoio", () => {
  it("monta iniciais de avatar", () => {
    expect(iniciais("Lucas Mendes")).toBe("LM");
    expect(iniciais("Dylan")).toBe("DY");
    expect(iniciais(null)).toBe("?");
  });

  it("pluraliza contadores", () => {
    expect(contar(1, "lançamento")).toBe("1 lançamento");
    expect(contar(2, "lançamento")).toBe("2 lançamentos");
  });
});

/**
 * "Cliente desde" — o rótulo que aparece no perfil e na lista depois de o histórico
 * retroativo ser carregado. A data vem do servidor como ISO completa (o lançamento
 * mais antigo); o dia não interessa a quem lê.
 */
describe("tempo de casa", () => {
  it("escreve mês e ano, ignorando o dia", () => {
    expect(mesAno("2025-03-10")).toBe("03/2025");
    expect(mesAno("2025-03")).toBe("03/2025");
    expect(mesAno(null)).toBe("—");
  });

  it("conta meses de calendário, não dias divididos por 30", () => {
    const hoje = new Date();
    const menos = (meses: number) => {
      const d = new Date(hoje.getFullYear(), hoje.getMonth() - meses, 10);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-10`;
    };

    expect(tempoDeCasa(menos(0))).toBe("menos de 1 mês");
    expect(tempoDeCasa(menos(1))).toBe("1 mês");
    expect(tempoDeCasa(menos(6))).toBe("6 meses");
    expect(tempoDeCasa(menos(12))).toBe("1 ano");
    expect(tempoDeCasa(menos(18))).toBe("1 ano e 6 meses");
    expect(tempoDeCasa(menos(25))).toBe("2 anos e 1 mês");
    expect(tempoDeCasa(null)).toBe("—");
  });
});
