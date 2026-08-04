import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ResultadoBusca } from "@/lib/tipos";

/**
 * Busca global — o comportamento que o Boss 4 pediu (T212, T213).
 *
 * O que estes testes travam:
 * 1. a busca é um **campo**, não uma janela que abre;
 * 2. funcionário aparece no resultado;
 * 3. clicar leva para a tela do registro, já selecionado.
 */

const empurrar = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: empurrar, replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// `next/link` fora do App Router não tem contexto de roteador; o `<a>` basta,
// porque quem navega aqui é o `onClick` do componente.
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...resto
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...resto}>
      {children}
    </a>
  ),
}));

const resultado: ResultadoBusca = {
  lancamentos: [
    {
      id: "l1",
      descricao: "Mensalidade Estrutural Vidros",
      valor: "2000.00",
      data: "2026-06-10",
      mundo: "digital",
    },
  ],
  clientes: [{ id: "c1", nome: "Estrutural Vidros", empresa: "Estrutural Ltda" }],
  funcionarios: [{ id: "f1", nome: "Marcondes", funcao: "Designer", mundo: "digital" }],
  categorias: [{ id: "cat1", nome: "Estrutura", cor: "#8B6CF0" }],
};

vi.mock("@/lib/consultas", () => ({
  useBusca: (termo: string) => ({
    data: termo.length >= 2 ? resultado : undefined,
    isFetching: false,
  }),
}));

const { BuscaGlobal } = await import("@/componentes/layout/BuscaGlobal");

beforeEach(() => {
  empurrar.mockClear();
});

describe("BuscaGlobal", () => {
  it("é um campo no cabeçalho, não uma janela que abre", () => {
    render(<BuscaGlobal />);
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("com o campo vazio, o dropdown oferece as telas", async () => {
    const usuario = userEvent.setup();
    render(<BuscaGlobal />);
    await usuario.click(screen.getByRole("combobox"));
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Ir para Funcionários" })).toBeInTheDocument();
  });

  it("mostra funcionário no resultado e leva para a tela dele", async () => {
    const usuario = userEvent.setup();
    render(<BuscaGlobal />);
    await usuario.type(screen.getByRole("combobox"), "marcondes");

    const opcao = await screen.findByRole(
      "option",
      { name: "Funcionário Marcondes" },
      { timeout: 2000 },
    );
    expect(opcao).toHaveAttribute("href", "/funcionarios/f1");

    await usuario.click(opcao);
    expect(empurrar).toHaveBeenCalledWith("/funcionarios/f1");
  });

  it("cobre lançamento, cliente, funcionário e categoria no mesmo dropdown", async () => {
    const usuario = userEvent.setup();
    render(<BuscaGlobal />);
    await usuario.type(screen.getByRole("combobox"), "estrutural");

    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(4), { timeout: 2000 });
    expect(screen.getByText("Lançamentos")).toBeInTheDocument();
    expect(screen.getByText("Clientes")).toBeInTheDocument();
    expect(screen.getByText("Funcionários")).toBeInTheDocument();
    expect(screen.getByText("Categorias")).toBeInTheDocument();
  });

  it("navega pelo teclado: seta escolhe, Enter abre", async () => {
    const usuario = userEvent.setup();
    render(<BuscaGlobal />);
    const campo = screen.getByRole("combobox");
    await usuario.type(campo, "estrutural");
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(4), { timeout: 2000 });

    // A primeira opção já nasce ativa; uma seta para baixo vai para a segunda.
    await usuario.keyboard("{ArrowDown}");
    await usuario.keyboard("{Enter}");
    expect(empurrar).toHaveBeenCalledWith("/clientes/c1");
  });

  it("Esc limpa o que foi digitado", async () => {
    const usuario = userEvent.setup();
    render(<BuscaGlobal />);
    const campo = screen.getByRole("combobox");
    await usuario.type(campo, "estrutural");
    await usuario.keyboard("{Escape}");
    expect(campo).toHaveValue("");
  });
});
