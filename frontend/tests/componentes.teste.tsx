import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Moeda } from "@/componentes/comum/Moeda";
import { BadgeStatus, rotuloDoStatus } from "@/componentes/comum/BadgeStatus";
import { BadgeMundo } from "@/componentes/comum/BadgeMundo";
import { Delta } from "@/componentes/comum/Delta";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { DataBR } from "@/componentes/comum/DataBR";

describe("Moeda", () => {
  it("pinta receita e despesa com cores diferentes", () => {
    const { container: receita } = render(<Moeda valor="100" tipo="receita" status="efetivado" />);
    const { container: despesa } = render(<Moeda valor="100" tipo="despesa" status="efetivado" />);
    expect(receita.firstChild).toHaveClass("text-[var(--receita-fg)]");
    expect(despesa.firstChild).toHaveClass("text-[var(--despesa-fg)]");
  });

  it("mostra valor não efetivado em cinza, mesmo sendo receita (RN-05)", () => {
    const { container } = render(<Moeda valor="100" tipo="receita" status="programado" />);
    expect(container.firstChild).toHaveClass("text-[var(--valor-previsto-fg)]");
  });

  it("põe o sinal quando pedido", () => {
    render(<Moeda valor="100" tipo="despesa" comSinal />);
    // O `Intl` do pt-BR usa espaço inquebrável entre "R$" e o número.
    expect(screen.getByText(/^−\s*R\$\s*100,00$/)).toBeInTheDocument();
  });
});

describe("BadgeStatus", () => {
  it("usa os cinco rótulos do enum do banco", () => {
    expect(rotuloDoStatus("efetivado")).toBe("Efetivado");
    expect(rotuloDoStatus("atrasado")).toBe("Atrasado");
    render(<BadgeStatus status="pendente" />);
    expect(screen.getByText("Pendente")).toBeInTheDocument();
  });
});

describe("BadgeMundo", () => {
  it("mostra o nome completo do mundo no título", () => {
    render(<BadgeMundo mundo="infra" />);
    expect(screen.getByTitle("Synapse Infra")).toBeInTheDocument();
  });
});

describe("Delta", () => {
  it("escreve “novo” quando a variação é nula", () => {
    // `variacao_percentual: null` significa que não há período anterior
    // comparável — não zero (contracts/consultas.md §1).
    render(<Delta comparativo={{ variacao_percentual: null }} />);
    expect(screen.getByText("novo")).toBeInTheDocument();
  });

  it("usa a direção que veio do servidor, não o sinal", () => {
    render(<Delta comparativo={{ variacao_percentual: "-3.4", direcao: "baixa" }} inverso />);
    expect(screen.getByText(/3,4%/)).toBeInTheDocument();
  });
});

describe("EstadoVazio", () => {
  it("explica em vez de sumir", () => {
    render(<EstadoVazio descricao="Nenhum lançamento no mundo Infra neste período." />);
    expect(screen.getByText("Nada previsto")).toBeInTheDocument();
    expect(
      screen.getByText("Nenhum lançamento no mundo Infra neste período."),
    ).toBeInTheDocument();
  });
});

describe("DataBR", () => {
  it("empilha dia/mês e ano na coluna estreita da tabela", () => {
    render(<DataBR valor="2026-07-31" formato="empilhada" />);
    expect(screen.getByText("31/07")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
  });
});
