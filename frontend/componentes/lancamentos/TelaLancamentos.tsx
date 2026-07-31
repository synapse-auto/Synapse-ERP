"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { RowSelectionState } from "@tanstack/react-table";
import { Trash2 } from "lucide-react";
import { CabecalhoTela, BotaoChrome, Quadro } from "@/componentes/comum/CabecalhoTela";
import { Paginacao } from "@/componentes/comum/Paginacao";
import { IconeExportar } from "@/componentes/comum/icones";
import { BarraFiltros } from "./BarraFiltros";
import { BarraAcoesEmMassa } from "./BarraAcoesEmMassa";
import { TabelaLancamentos } from "./TabelaLancamentos";
import { PainelDetalhe } from "./PainelDetalhe";
import { FormLancamento } from "./FormLancamento";
import { TabelaLote } from "./TabelaLote";
import { AssistenteImportacao } from "@/componentes/importacao/AssistenteImportacao";
import { useEscopo, useLancamentos } from "@/lib/consultas";
import { useAtalhos } from "@/lib/atalhos";
import { FILTROS_VAZIOS, daUrl, paraConsulta, type FiltrosLancamento } from "./filtros";
import { montarUrlExportacao } from "./acoes";

/**
 * Tela de Lançamentos (T162–T170).
 *
 * O comportamento que o mockup escreve na linha de apoio: **um clique abre o
 * detalhe, duplo clique edita, `N` cria um novo**.
 *
 * A tela aceita filtros pela URL — é assim que o drill-down do Dashboard
 * chega aqui (`FR-058`): o card manda o `filtro_drilldown` que o servidor
 * montou, a tela só lê.
 */
export function TelaLancamentos() {
  const params = useSearchParams();
  const escopo = useEscopo();

  const [filtros, setFiltros] = useState<FiltrosLancamento>(() => ({
    ...FILTROS_VAZIOS,
    ...daUrl(new URLSearchParams(params.toString())),
  }));
  const [marcados, setMarcados] = useState<RowSelectionState>({});
  const [selecionadoId, setSelecionadoId] = useState<string | null>(
    params.get("selecionado") ?? null,
  );
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [loteAberto, setLoteAberto] = useState(false);
  const [importacaoAberta, setImportacaoAberta] = useState(false);

  // Trocar de mundo ou de período reinicia a paginação e limpa a seleção:
  // manter marcados de outro recorte agiria sobre linhas que sumiram da tela.
  useEffect(() => {
    setFiltros((f) => ({ ...f, pagina: 1 }));
    setMarcados({});
  }, [escopo.mundo, escopo.periodo, escopo.dataInicio, escopo.dataFim]);

  const consulta = useMemo(() => paraConsulta(filtros), [filtros]);
  const { data, isFetching } = useLancamentos(consulta);

  const idsMarcados = Object.keys(marcados).filter((id) => marcados[id]);

  function aplicar(parcial: Partial<FiltrosLancamento>) {
    setFiltros((f) => ({ ...f, ...parcial }));
  }

  function ordenarPor(coluna: FiltrosLancamento["ordenar"]) {
    setFiltros((f) => ({
      ...f,
      ordenar: coluna,
      direcao: f.ordenar === coluna && f.direcao === "desc" ? "asc" : "desc",
      pagina: 1,
    }));
  }

  function exportar() {
    window.location.assign(
      montarUrlExportacao({ ...escopo.parametros, ...consulta, pagina: undefined, por_pagina: undefined }),
    );
  }

  useAtalhos([
    {
      tecla: "escape",
      valeDigitando: true,
      grupo: "Tela",
      descricao: "Fechar painel ou limpar seleção",
      aoDisparar: () => {
        if (selecionadoId) setSelecionadoId(null);
        else if (idsMarcados.length) setMarcados({});
      },
    },
  ]);

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-[30px] pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Gestão · núcleo operacional"
        titulo="Lançamentos"
        apoio={
          <>
            Um clique abre o detalhe · duplo clique edita ·{" "}
            <strong className="font-semibold text-[var(--ink-600)] dark:text-[var(--fg)]">N</strong>{" "}
            cria um novo
          </>
        }
        acoes={
          <>
            <BotaoChrome onClick={() => setImportacaoAberta(true)}>
              <IconeExportar className="rotate-180" />
              Importar CSV / OFX
            </BotaoChrome>
            <BotaoChrome onClick={exportar}>
              <IconeExportar />
              Exportar
            </BotaoChrome>
            <BotaoChrome onClick={() => setLoteAberto(true)}>Criar em lote</BotaoChrome>
            <Link href="/lancamentos/lixeira">
              <BotaoChrome>
                <Trash2 size={14} />
                Lixeira
              </BotaoChrome>
            </Link>
          </>
        }
      />

      <Quadro>
        <BarraFiltros filtros={filtros} aoMudar={aplicar} resumo={data?.resumo_filtrado} />

        <BarraAcoesEmMassa
          ids={idsMarcados}
          aoLimpar={() => setMarcados({})}
          aoExportar={exportar}
        />

        <TabelaLancamentos
          itens={data?.itens ?? []}
          carregando={isFetching}
          selecionadoId={selecionadoId}
          marcados={marcados}
          aoMudarMarcados={setMarcados}
          aoAbrir={setSelecionadoId}
          aoEditar={setEditandoId}
          filtros={filtros}
          aoOrdenar={ordenarPor}
        />

        <Paginacao
          paginacao={data?.paginacao}
          aoIr={(p) => setFiltros((f) => ({ ...f, pagina: p }))}
        />
      </Quadro>

      {data?.quebra_por_mundo ? (
        <p className="px-1 text-[11.5px] text-sutil">
          Resultado por mundo neste recorte:{" "}
          {Object.entries(data.quebra_por_mundo).map(([m, v], i) => (
            <span key={m}>
              {i > 0 ? " · " : ""}
              <span
                className="font-semibold"
                style={{ color: `var(--mundo-${m})` }}
              >
                {m === "digital" ? "Digital" : "Infra"}
              </span>{" "}
              <span className="numerico">{v}</span>
            </span>
          ))}
        </p>
      ) : null}

      <PainelDetalhe
        id={selecionadoId}
        aoFechar={() => setSelecionadoId(null)}
        aoEditar={(id) => {
          setSelecionadoId(null);
          setEditandoId(id);
        }}
      />

      <FormLancamento
        aberto={Boolean(editandoId)}
        idParaEditar={editandoId}
        aoFechar={() => setEditandoId(null)}
      />

      <TabelaLote aberta={loteAberto} aoFechar={() => setLoteAberto(false)} />

      <AssistenteImportacao aberto={importacaoAberta} aoFechar={() => setImportacaoAberta(false)} />
    </div>
  );
}
