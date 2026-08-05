import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Categoria } from "@/lib/tipos";

/**
 * Ícone da categoria (`FR-072`) — 2026-08-05.
 *
 * O bug que motivou o teste: o formulário mandava `icone: null`, a coluna é
 * `text not null` e o `CategoriaEntrada` exige string, então **criar categoria
 * respondia `400 validacao`** ("Alguns campos precisam de correção.") sem dizer
 * na tela qual campo era. O que está travado aqui:
 *
 * 1. o corpo enviado tem sempre um nome de ícone do catálogo — nunca `null`;
 * 2. a escolha pela busca em português chega ao corpo (`solar` → `sun`);
 * 3. o ícone de uma categoria existente é o que abre no formulário, e nenhum
 *    dos nove do seed cai no padrão — abrir e salvar não troca o ícone à toa.
 */

type OpcoesDoPedido = { corpo?: Record<string, unknown> };

type Pedido = (rota: string, opcoes?: OpcoesDoPedido) => Promise<{ id: string }>;

const post = vi.fn<Pedido>();
const put = vi.fn<Pedido>();

/** O corpo do primeiro pedido — é ele que o `400` recusava. */
const corpoEnviado = (espia: typeof post | typeof put) => espia.mock.calls[0]![1]!.corpo!;

vi.mock("@/lib/api", async (importarOriginal) => {
  const real = await importarOriginal<typeof import("@/lib/api")>();
  return { ...real, api: { ...real.api, post, put } };
});

const { FormCategoria } = await import("@/componentes/categorias/FormCategoria");
const { CATALOGO_ICONES, ICONE_PADRAO, filtraIcones, iconeDoCatalogo } = await import(
  "@/componentes/comum/catalogo-icones"
);

const CATEGORIA: Categoria = {
  id: "c1",
  nome: "Infraestrutura",
  cor: "#4FA8E0",
  icone: "server",
  tipo: "despesa",
  especial: false,
  vinculo: null,
  ordem: 3,
  arquivada_em: null,
  uso: { quantidade_lancamentos: 0, total_movimentado: "0.00" },
  subcategorias: [],
};

function montar(categoria: Categoria | null = null) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={cliente}>
      <FormCategoria aberta categoria={categoria} aoFechar={() => {}} />
    </QueryClientProvider>,
  );
}

const nomesDoCatalogo = CATALOGO_ICONES.flatMap((g) => g.itens.map((i) => i.nome));

/** Os nomes que `migracoes/008_seed_dominio.sql` grava nas nove categorias. */
const DO_SEED = [
  "users",
  "briefcase",
  "server",
  "wrench",
  "landmark",
  "megaphone",
  "laptop",
  "truck",
  "ellipsis",
];

beforeEach(() => {
  post.mockReset().mockResolvedValue({ id: "nova" });
  put.mockReset().mockResolvedValue({ id: "c1" });
});

describe("catálogo de ícones", () => {
  it("reconhece os nove ícones que o seed já gravou", () => {
    for (const nome of DO_SEED) {
      expect(iconeDoCatalogo(nome).nome, `${nome} fora do catálogo`).toBe(nome);
    }
  });

  it("não repete nome", () => {
    expect(new Set(nomesDoCatalogo).size).toBe(nomesDoCatalogo.length);
  });

  it("cai no padrão quando o nome é desconhecido ou vazio", () => {
    expect(iconeDoCatalogo("nao-existe").nome).toBe(ICONE_PADRAO);
    expect(iconeDoCatalogo(null).nome).toBe(ICONE_PADRAO);
  });

  it("busca em português, sem acento e sem caixa", () => {
    const achados = (termo: string) =>
      filtraIcones(termo).flatMap((g) => g.itens.map((i) => i.nome));

    expect(achados("solar")).toContain("sun");
    expect(achados("ELETRICA")).toContain("plug-zap");
    expect(achados("ar condicionado")).toContain("air-vent");
    // O nome técnico também vale, para quem conhece o Lucide.
    expect(achados("cctv")).toContain("cctv");
    expect(filtraIcones("xyzw")).toHaveLength(0);
  });
});

describe("ícone no formulário de categoria", () => {
  it("manda um ícone do catálogo ao criar — nunca `null`", async () => {
    const usuario = userEvent.setup();
    montar();

    await usuario.type(screen.getByLabelText("Nome"), "Custos Operacionais");
    await usuario.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const corpo = corpoEnviado(post);
    expect(typeof corpo.icone).toBe("string");
    expect(nomesDoCatalogo).toContain(corpo.icone);
  });

  it("leva ao corpo o ícone escolhido pela busca em português", async () => {
    const usuario = userEvent.setup();
    montar();

    await usuario.type(screen.getByLabelText("Nome"), "Energia");
    await usuario.click(screen.getByRole("button", { name: /^Ícone:/ }));
    await usuario.type(await screen.findByLabelText("Buscar ícone"), "solar");
    await usuario.click(screen.getByRole("button", { name: "Energia solar" }));
    await usuario.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(corpoEnviado(post).icone).toBe("sun");
  });

  it("abre com o ícone da categoria em edição e o mantém ao salvar", async () => {
    const usuario = userEvent.setup();
    montar(CATEGORIA);

    // O rótulo PT-BR do `server` é "Servidor" — é o que o gestor lê no controle.
    expect(screen.getByRole("button", { name: /^Ícone: Servidor/ })).toBeInTheDocument();

    await usuario.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    expect(corpoEnviado(put).icone).toBe("server");
  });
});
