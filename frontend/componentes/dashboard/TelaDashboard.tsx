"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CabecalhoTela, BotaoChrome } from "@/componentes/comum/CabecalhoTela";
import { Cartao } from "@/componentes/comum/Cartao";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { IconeAjustes, IconeExportar } from "@/componentes/comum/icones";
import { CartaoNumerico } from "./CartaoNumerico";
import { ConfigurarCards } from "./ConfigurarCards";
import {
  AlertaAtrasados,
  BlocoClientes,
  BlocoCustosCliente,
  BlocoFuncionarios,
  CartaoSaudeCaixa,
  LinhaTempo7Dias,
  ReceitaPorServico,
  ResumoDoPeriodo,
  TopDespesas,
} from "./blocos";
import { ComparativoMensal, FluxoCaixa } from "@/componentes/graficos/FluxoCaixa";
import { EvolucaoSaldo } from "@/componentes/graficos/EvolucaoSaldo";
import { DespesasCategoria } from "@/componentes/graficos/DespesasCategoria";
import { PainelDetalhe } from "@/componentes/lancamentos/PainelDetalhe";
import { useDashboard, useEscopo, useSessao } from "@/lib/consultas";
import { useEstadoGlobal } from "@/lib/estado-global";
import { intervalo, mesPorExtenso } from "@/lib/formato";
import { paraQueryString } from "@/lib/api";
import type { AtalhoPeriodo, CardDashboard, CardDisponivel } from "@/lib/tipos";

/**
 * Dashboard (T175–T181).
 *
 * **A grade é montada a partir do catálogo**, não escrita no código
 * (`FR-106`, T175): a ordem e a visibilidade vêm de `cards_disponiveis`
 * (catálogo × preferências do usuário) e cada id é resolvido por um
 * componente. Um card novo no banco aparece aqui sem deploy; um id sem
 * componente é ignorado em silêncio, em vez de quebrar a tela.
 *
 * **Tudo numa requisição** (`SC-002`): `GET /api/dashboard` devolve cards,
 * séries, blocos especiais e o resumo em linguagem natural de uma vez.
 *
 * **Todo card e toda fatia levam à lista filtrada** (T181, `FR-058`), usando
 * o `filtro_drilldown` que o servidor montou.
 */
export function TelaDashboard() {
  const router = useRouter();
  const escopo = useEscopo();
  const definirPeriodo = useEstadoGlobal((e) => e.definirPeriodo);
  const { data: sessao } = useSessao();
  const { data, isLoading, isError, error } = useDashboard();
  const [configurando, setConfigurando] = useState(false);
  const [lancamentoAberto, setLancamentoAberto] = useState<string | null>(null);

  const catalogo: CardDisponivel[] = useMemo(
    () => [...(data?.cards_disponiveis ?? [])].sort((a, b) => a.ordem - b.ordem),
    [data?.cards_disponiveis],
  );

  const numericosPorId = useMemo(
    () => new Map((data?.cards ?? []).map((c) => [c.id, c])),
    [data?.cards],
  );

  function irParaLista(drilldown: Record<string, unknown> | null | undefined) {
    const consulta = { ...escopo.parametros, ...(drilldown ?? {}) };

    // Cards que alcançam o vencido (A pagar, A receber, alerta de atrasados)
    // mandam a janela junto, alargada até a conta vencida mais antiga. Ela
    // precisa entrar **na loja**, não só na URL: o espelho de URL reescreve a
    // query a partir do estado global logo depois da navegação, e o recorte do
    // link se perderia — a lista abriria com menos linhas do que o card somou.
    // Passando pela loja, o seletor do cabeçalho também passa a dizer a verdade
    // sobre o que a lista está mostrando.
    const periodo = drilldown?.periodo;
    if (typeof periodo === "string" && periodo !== escopo.periodo) {
      definirPeriodo(
        periodo as AtalhoPeriodo,
        typeof drilldown?.data_inicio === "string" ? drilldown.data_inicio : null,
        typeof drilldown?.data_fim === "string" ? drilldown.data_fim : null,
      );
    }

    router.push(`/lancamentos${paraQueryString(consulta as never)}`);
  }

  if (isLoading) return <EsqueletoDashboard />;

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-[var(--conteudo-largura-max)] px-4 pt-5 sm:px-[30px] sm:pt-[26px]">
        <Cartao>
          <EstadoVazio
            titulo="Não foi possível carregar o painel"
            descricao={error instanceof Error ? error.message : undefined}
          />
        </Cartao>
      </div>
    );
  }

  const visiveis = catalogo.filter((c) => c.visivel ?? true);
  const nome = sessao?.usuario.nome?.split(" ")[0] ?? "";

  /** Renderiza um id do catálogo. Id sem componente é ignorado (não quebra). */
  function renderizar(c: CardDisponivel, cardsNumericos: CardDashboard[]): React.ReactNode {
    switch (c.id) {
      case "alerta_atrasados":
        return data!.alerta_atrasados ? (
          <AlertaAtrasados
            key={c.id}
            alerta={data!.alerta_atrasados}
            aoAbrir={() => irParaLista(data!.alerta_atrasados!.filtro_drilldown)}
          />
        ) : null;

      case "saude_caixa":
        return data!.saude_caixa ? (
          <CartaoSaudeCaixa key={c.id} saude={data!.saude_caixa} rotulo={c.rotulo} />
        ) : null;

      case "resumo_periodo":
        return (
          <ResumoDoPeriodo
            key={c.id}
            texto={data!.resumo_linguagem_natural}
            rotulo={c.rotulo}
          />
        );

      case "fluxo_caixa_12m":
        return (
          <Cartao key={c.id} className="flex flex-col gap-1">
            <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
              {c.rotulo}
            </span>
            <span className="mb-2 text-[12px] text-sutil">
              Realizado e projeção a partir de recorrentes e programados
            </span>
            <FluxoCaixa dados={data!.fluxo_caixa_mensal} />
          </Cartao>
        );

      case "evolucao_saldo":
        return (
          <Cartao key={c.id} className="flex flex-col gap-1">
            <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
              {c.rotulo}
            </span>
            <span className="mb-2 text-[12px] text-sutil">Saldo em caixa ao fim de cada mês</span>
            <EvolucaoSaldo dados={data!.evolucao_saldo} />
          </Cartao>
        );

      case "comparativo_mensal":
        return data!.comparativo_mes ? (
          <Cartao key={c.id} className="flex flex-col gap-1">
            <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
              {c.rotulo}
            </span>
            <span className="mb-2 text-[12px] text-sutil">Período atual contra o anterior</span>
            <ComparativoMensal
              atual={data!.comparativo_mes.atual}
              anterior={data!.comparativo_mes.anterior}
            />
          </Cartao>
        ) : null;

      case "despesas_categoria":
        return (
          <Cartao key={c.id} className="flex flex-col gap-1">
            <span className="font-[family-name:var(--font-display)] text-[15px] font-bold text-forte">
              {c.rotulo}
            </span>
            <span className="mb-3 text-[12px] text-sutil">Clique para filtrar a lista</span>
            <DespesasCategoria
              fatias={data!.despesas_por_categoria}
              total={data!.cards.find((x) => x.id === "despesas_periodo")?.valor ?? "0"}
              aoEscolher={(f) => irParaLista(f.filtro_drilldown)}
            />
          </Cartao>
        );

      case "top_despesas":
        return (
          <TopDespesas
            key={c.id}
            itens={data!.top_despesas}
            rotulo={c.rotulo}
            aoAbrir={setLancamentoAberto}
          />
        );

      case "receita_servico":
        // `FR-064`. A entrada no catálogo entrou na migração `013` (2026-08-03) —
        // até lá o bloco existia aqui e nunca era desenhado, porque a grade só
        // desenha id que o catálogo declara.
        return <ReceitaPorServico key={c.id} itens={data!.receita_por_servico} rotulo={c.rotulo} />;

      case "bloco_clientes":
        return data!.card_clientes ? (
          <BlocoClientes key={c.id} bloco={data!.card_clientes} rotulo={c.rotulo} />
        ) : null;

      case "bloco_custos_cliente":
        // `RF-58`. A entrada no catálogo veio na migração `015` — sem ela a
        // grade ignoraria este id em silêncio, como fez com `receita_servico`
        // até a `013`.
        return data!.card_custos_cliente ? (
          <BlocoCustosCliente key={c.id} bloco={data!.card_custos_cliente} rotulo={c.rotulo} />
        ) : null;

      case "bloco_funcionarios":
        return data!.card_funcionarios ? (
          <BlocoFuncionarios key={c.id} bloco={data!.card_funcionarios} rotulo={c.rotulo} />
        ) : null;

      case "linha_tempo_7_dias":
        return (
          <LinhaTempo7Dias
            key={c.id}
            dias={data!.proximos_7_dias}
            rotulo={c.rotulo}
            aoAbrir={setLancamentoAberto}
          />
        );

      default: {
        const card = numericosPorId.get(c.id);
        if (!card) return null;
        const hero = cardsNumericos[0]?.id === c.id;
        return (
          <CartaoNumerico
            key={c.id}
            card={card}
            hero={hero}
            mundo={data!.mundo}
            aoAbrirFiltro={(x) => irParaLista(x.filtro_drilldown)}
            className={hero ? "md:col-span-2 xl:row-span-1" : undefined}
          />
        );
      }
    }
  }

  const numericos = visiveis.filter((c) => c.grupo === "numerico");
  const cardsNumericos = numericos
    .map((c) => numericosPorId.get(c.id))
    .filter(Boolean) as CardDashboard[];

  /**
   * A grade (T217).
   *
   * **Uma grade só, de duas colunas**, e cada bloco declara quanto ocupa. Até
   * 2026-08-03 cada bloco ganhava um `<div class="grid lg:grid-cols-2">`
   * **próprio, com um filho só**: o card ficava com metade da largura e a outra
   * metade sobrava vazia, com o card seguinte na linha de baixo. Dois cards de
   * meia largura nunca chegavam a ficar lado a lado.
   *
   * A largura vem do servidor (`largura`), que resolve preferência do usuário →
   * `largura_padrao` do catálogo → padrão do grupo. Nenhum id de card decide
   * layout aqui dentro.
   *
   * Os `numerico` consecutivos continuam entrando numa faixa só de quatro
   * colunas, como no mockup — eles têm grade própria e ignoram `largura`.
   */
  const blocos: React.ReactNode[] = [];
  let acumuladorNumerico: React.ReactNode[] = [];

  function despejarNumericos() {
    if (acumuladorNumerico.length === 0) return;
    blocos.push(
      <div
        key={`num-${blocos.length}`}
        className="col-span-full grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        {acumuladorNumerico}
      </div>,
    );
    acumuladorNumerico = [];
  }

  for (const c of visiveis) {
    if (c.grupo === "numerico") {
      const no = renderizar(c, cardsNumericos);
      if (no) acumuladorNumerico.push(no);
      continue;
    }
    despejarNumericos();
    const no = renderizar(c, cardsNumericos);
    if (!no) continue;
    blocos.push(
      <div
        key={c.id}
        className={
          // `[&>*]:flex-1` estica o cartão até o pé da célula: dois cards lado a
          // lado terminam na mesma linha mesmo com conteúdo de alturas diferentes.
          c.largura === "inteira"
            ? "col-span-full flex flex-col [&>*]:flex-1"
            : "flex flex-col [&>*]:flex-1"
        }
      >
        {no}
      </div>,
    );
  }
  despejarNumericos();

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha={`${mesPorExtenso(data.periodo.inicio)} · ${intervalo(data.periodo.inicio, data.periodo.fim)}`}
        titulo={nome ? `${saudacao()}, ${nome}` : saudacao()}
        apoio={data.resumo_linguagem_natural}
        acoes={
          <>
            <BotaoChrome onClick={() => setConfigurando(true)}>
              <IconeAjustes />
              Configurar cards
            </BotaoChrome>
            <BotaoChrome onClick={() => router.push("/relatorios")}>
              <IconeExportar />
              Exportar
            </BotaoChrome>
          </>
        }
      />

      {data.periodo_vazio ? (
        <Cartao>
          <EstadoVazio
            titulo="Nenhum lançamento neste período"
            descricao="Os números abaixo ficam zerados até entrar movimentação. Enquanto o histórico não estiver carregado, o caixa mostra menos do que a realidade."
          />
        </Cartao>
      ) : null}

      {/* A grade de duas colunas do painel. Um bloco de `largura: "inteira"`
          atravessa com `col-span-full`; dois de `"metade"` seguidos caem lado a
          lado sozinhos, que é o que a grade existe para fazer. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{blocos}</div>

      <ConfigurarCards
        catalogo={catalogo}
        aberto={configurando}
        aoFechar={() => setConfigurando(false)}
      />

      <PainelDetalhe
        id={lancamentoAberto}
        aoFechar={() => setLancamentoAberto(null)}
        aoEditar={(id) => router.push(`/lancamentos?selecionado=${id}`)}
      />
    </div>
  );
}

function saudacao(): string {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function EsqueletoDashboard() {
  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <div className="h-16 w-1/3 animate-pulse rounded-[10px] bg-[var(--bg-subtle)]" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[168px] animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
        ))}
      </div>
      <div className="h-[320px] animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-[280px] animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
        <div className="h-[280px] animate-pulse rounded-[12px] bg-[var(--bg-subtle)]" />
      </div>
    </div>
  );
}
