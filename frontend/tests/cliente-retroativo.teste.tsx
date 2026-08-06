import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FormCliente } from "@/componentes/clientes/FormCliente";
import type { Cliente } from "@/lib/tipos";

/**
 * "Já era cliente antes do sistema" no cadastro de cliente.
 *
 * O que estes testes travam são as três condições que o servidor também impõe, mas
 * que a tela precisa respeitar **antes** de a pessoa preencher — errar aqui só
 * apareceria como um `400` depois do clique em Salvar:
 *
 * 1. o bloco só existe em cobrança **recorrente**;
 * 2. o bloco **não** existe na edição (o `PUT` recusa `cliente_desde`);
 * 3. o corpo enviado é `AAAA-MM`, sem dia.
 */

const CLIENTE: Cliente = {
  id: "c1",
  nome: "Estrutural Vidros",
  empresa: null,
  contato_email: null,
  contato_telefone: null,
  tipo_cobranca: "recorrente",
  valor_recorrente: "2000.00",
  dia_cobranca: 10,
  mundo_cobranca: "digital",
  servicos: [],
  situacao: "em_dia",
  dias_atraso: null,
  valor_atrasado: null,
  total_recebido_periodo: "0.00",
  total_recebido_historico: "0.00",
  total_custo_periodo: "0.00",
  total_custo_historico: "0.00",
  margem_periodo: "0.00",
  margem_historico: "0.00",
  cliente_desde: null,
  arquivado_em: null,
};

function montar(cliente: Cliente | null = null) {
  const cliente_query = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={cliente_query}>
      <FormCliente aberta cliente={cliente} aoFechar={() => {}} />
    </QueryClientProvider>,
  );
}

async function escolherRecorrente(usuario: ReturnType<typeof userEvent.setup>) {
  await usuario.click(screen.getByRole("combobox", { name: /cobrança/i }));
  await usuario.click(await screen.findByRole("option", { name: /Recorrente/ }));
}

describe("cliente retroativo no cadastro", () => {
  it("não oferece histórico em cobrança pontual", () => {
    montar();
    expect(screen.queryByText(/Já era cliente antes do sistema/)).toBeNull();
  });

  it("oferece o histórico quando a cobrança vira recorrente", async () => {
    const usuario = userEvent.setup();
    montar();
    await escolherRecorrente(usuario);
    expect(screen.getByText(/Já era cliente antes do sistema/)).toBeInTheDocument();
  });

  it("revela mês e ano só depois de o checkbox ser marcado", async () => {
    const usuario = userEvent.setup();
    montar();
    await escolherRecorrente(usuario);

    expect(screen.queryByRole("combobox", { name: "Mês de início" })).toBeNull();

    await usuario.click(screen.getByRole("checkbox", { name: /Já era cliente antes/ }));

    expect(screen.getByRole("combobox", { name: "Mês de início" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Ano de início" })).toBeInTheDocument();
  });

  it("não oferece histórico na edição — o PUT recusa", async () => {
    montar(CLIENTE);
    expect(screen.queryByText(/Já era cliente antes do sistema/)).toBeNull();
  });

  it("avisa quando o mês escolhido é o corrente, em vez de deixar o usuário achar que carregou", async () => {
    const usuario = userEvent.setup();
    const hoje = new Date();
    montar();
    await escolherRecorrente(usuario);
    await usuario.click(screen.getByRole("checkbox", { name: /Já era cliente antes/ }));

    // O padrão é o ano passado; trazendo para o ano atual e o mês atual, o aviso muda.
    await usuario.click(screen.getByRole("combobox", { name: "Ano de início" }));
    await usuario.click(await screen.findByRole("option", { name: String(hoje.getFullYear()) }));

    expect(screen.getByText(/nada de histórico é criado/)).toBeInTheDocument();
  });

  it("manda cliente_desde como AAAA-MM, sem dia", async () => {
    const usuario = userEvent.setup();
    const enviado = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, opcoes: RequestInit) => {
        enviado(JSON.parse(String(opcoes.body)));
        return new Response(JSON.stringify({ id: "novo", recorrencia: null }), {
          status: 201,
          headers: { "content-type": "application/json" },
        });
      }),
    );

    montar();
    await escolherRecorrente(usuario);
    await usuario.type(screen.getByLabelText("Nome"), "Antigo");
    await usuario.type(screen.getByLabelText("Valor mensal"), "2000");
    await usuario.click(screen.getByRole("checkbox", { name: /Já era cliente antes/ }));

    await usuario.click(screen.getByRole("combobox", { name: "Mês de início" }));
    await usuario.click(await screen.findByRole("option", { name: "Março" }));
    await usuario.click(screen.getByRole("combobox", { name: "Ano de início" }));
    await usuario.click(await screen.findByRole("option", { name: "2025" }));

    await usuario.click(screen.getByRole("button", { name: /Salvar cliente/ }));

    expect(enviado).toHaveBeenCalled();
    expect(enviado.mock.calls[0][0].cliente_desde).toBe("2025-03");

    vi.unstubAllGlobals();
  });
});
