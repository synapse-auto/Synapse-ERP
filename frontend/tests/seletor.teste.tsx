import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Seletor } from "@/componentes/comum/Seletor";

/**
 * Seletor (T219).
 *
 * O caso que estes testes existem para travar é o **valor vazio**: o Radix
 * proíbe `value=""` num item e derruba o componente em tempo de execução, mas
 * metade dos seletores do sistema tem uma opção "todos"/"nenhum" que vale `""`
 * na API. O sentinela interno tem de ser invisível para quem chama.
 */

const OPCOES = [
  { valor: "", rotulo: "Todos" },
  { valor: "receita", rotulo: "Receita" },
  { valor: "despesa", rotulo: "Despesa" },
];

describe("Seletor", () => {
  it("mostra o rótulo da opção escolhida, não o valor", () => {
    render(
      <Seletor valor="despesa" aoMudar={() => {}} opcoes={OPCOES} rotuloAcessivel="Tipo" />,
    );
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent("Despesa");
  });

  it("aceita opção de valor vazio e devolve string vazia ao escolher", async () => {
    const usuario = userEvent.setup();
    const aoMudar = vi.fn();
    render(<Seletor valor="receita" aoMudar={aoMudar} opcoes={OPCOES} rotuloAcessivel="Tipo" />);

    await usuario.click(screen.getByRole("combobox", { name: "Tipo" }));
    await usuario.click(await screen.findByRole("option", { name: "Todos" }));

    // O sentinela é detalhe interno: quem chama recebe `""`, como a API espera.
    expect(aoMudar).toHaveBeenCalledWith("");
  });

  it("devolve o valor cru das demais opções", async () => {
    const usuario = userEvent.setup();
    const aoMudar = vi.fn();
    render(<Seletor valor="" aoMudar={aoMudar} opcoes={OPCOES} rotuloAcessivel="Tipo" />);

    await usuario.click(screen.getByRole("combobox", { name: "Tipo" }));
    await usuario.click(await screen.findByRole("option", { name: "Despesa" }));

    expect(aoMudar).toHaveBeenCalledWith("despesa");
  });

  it("com valor vazio e sem opção vazia, mostra o placeholder", () => {
    render(
      <Seletor
        valor=""
        aoMudar={() => {}}
        rotuloAcessivel="Categoria"
        placeholder="Escolha…"
        opcoes={[{ valor: "a", rotulo: "Aluguel" }]}
      />,
    );
    expect(screen.getByRole("combobox", { name: "Categoria" })).toHaveTextContent("Escolha…");
  });

  it("desabilitado não abre", async () => {
    const usuario = userEvent.setup();
    render(
      <Seletor
        valor=""
        aoMudar={() => {}}
        desabilitado
        opcoes={OPCOES}
        rotuloAcessivel="Tipo"
      />,
    );
    const campo = screen.getByRole("combobox", { name: "Tipo" });
    expect(campo).toBeDisabled();
    await usuario.click(campo);
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });
});
