"use client";

import { Suspense, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { BarraLateral } from "./BarraLateral";
import { CabecalhoGlobal } from "./CabecalhoGlobal";
import { BarraLateralMovel } from "./BarraLateralMovel";
import { MarcaSynapse } from "@/componentes/comum/icones";
import { FormLancamento } from "@/componentes/lancamentos/FormLancamento";
import { autenticacaoConfigurada, sessaoAtual } from "@/lib/supabase";
import { useSessao } from "@/lib/consultas";
import { useEstadoUi } from "@/lib/estado-global";
import { ErroApi } from "@/lib/api";

/**
 * Casca da aplicação: barra lateral fixa + cabeçalho de 64px + conteúdo
 * rolável, exatamente o esqueleto do mockup (`display:flex; height:100vh;
 * overflow:hidden`).
 *
 * Também é o portão de sessão. Sem token, vai para `/entrar` guardando o
 * destino. **Isso é conveniência, não segurança**: quem protege o dado é o
 * `401`/`403` do backend em cada endpoint (`SC-010`).
 */
export function CascaApp({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [verificando, setVerificando] = useState(true);
  const { error } = useSessao({ retry: false });
  const novoAberto = useEstadoUi((e) => e.novoLancamentoAberto);
  const fecharNovo = useEstadoUi((e) => e.fecharNovoLancamento);
  const rascunho = useEstadoUi((e) => e.rascunhoNovoLancamento);

  useEffect(() => {
    let vivo = true;
    (async () => {
      if (!autenticacaoConfigurada()) {
        // Ambiente sem Supabase configurado (desenvolvimento local, testes):
        // deixa passar e quem recusa é o backend.
        if (vivo) setVerificando(false);
        return;
      }
      const sessao = await sessaoAtual();
      if (!vivo) return;
      if (!sessao) {
        const destino = encodeURIComponent(window.location.pathname + window.location.search);
        router.replace(`/entrar?destino=${destino}`);
        return;
      }
      setVerificando(false);
    })();
    return () => {
      vivo = false;
    };
  }, [router]);

  if (verificando) return <TelaDeEspera />;

  if (error instanceof ErroApi && error.naoAutenticado) return <TelaDeEspera />;

  return (
    <div className="flex h-dvh overflow-hidden bg-superficie-app">
      <BarraLateral className="hidden md:flex" />

      <div className="flex h-dvh min-w-0 flex-1 flex-col">
        <Suspense fallback={<div className="h-[var(--cabecalho-altura)] flex-none border-b border-linha-chrome bg-superficie-cartao" />}>
          {/* O `md:flex-none` não é enfeite: sem ele o cabeçalho tem 285px em vez de 64.
              Abaixo de `md` esta div é uma faixa flex em linha, e o `flex-1` faz o
              cabeçalho ocupar a largura que sobra ao lado do botão do menu — que é o que
              se quer. De `md` para cima ela vira `contents` e some do layout, então o
              cabeçalho passa a ser filho direto da coluna `h-dvh flex-col` acima: ali
              `flex-1` cresce na **vertical** e atropela o `h-[--cabecalho-altura]`
              (o `cn` ainda descarta o `flex-none` do próprio componente, porque esta
              classe vem depois). O `md:flex-none` devolve os 64px do design. */}
          <div className="flex items-center gap-2 md:contents">
            <BarraLateralMovel />
            <CabecalhoGlobal className="min-w-0 flex-1 md:flex-none" />
          </div>
        </Suspense>

        <main className="flex-1 overflow-y-auto bg-superficie-app">{children}</main>
      </div>

      <FormLancamento aberto={novoAberto} aoFechar={fecharNovo} rascunho={rascunho} />
    </div>
  );
}

function TelaDeEspera() {
  return (
    <div className="flex h-dvh items-center justify-center bg-superficie-app">
      <div className="flex flex-col items-center gap-3">
        <MarcaSynapse tamanho={40} idGradiente="marca-espera" className="animate-pulse rounded-[9px]" />
        <span className="text-[12.5px] text-sutil">Carregando…</span>
      </div>
    </div>
  );
}
