"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { CabecalhoTela } from "@/componentes/comum/CabecalhoTela";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { SecaoParametros } from "./SecaoParametros";
import { SecaoCadastroSimples } from "./SecaoCadastroSimples";
import { SecaoUsuarios } from "./SecaoUsuarios";
import { SecaoDados } from "./SecaoDados";
import { SecaoAuditoria } from "./SecaoAuditoria";
import { useSessao } from "@/lib/consultas";

/**
 * Configurações (T196, T197, T199, `FR-102`–`FR-106`).
 *
 * As sete seções do mockup. A de **Parâmetros** é montada inteira a partir de
 * `GET /api/configuracoes` — inclusive os textos de ajuda, que vêm do banco
 * (`FR-106`). Nenhum rótulo, limite ou explicação está escrito aqui.
 *
 * **Leitura é de operador também**: o frontend precisa de
 * `anexo_tamanho_max_mb`, `alerta_vencimento_dias` e dos rótulos de card para
 * montar as telas. **Escrita é só de gestor** — e a garantia disso é o `403`
 * do backend, não o botão desabilitado (`SC-010`). O botão desabilitado é
 * cortesia; a fechadura é o endpoint.
 */

type Secao =
  | "parametros"
  | "servicos"
  | "centros"
  | "tags"
  | "usuarios"
  | "dados"
  | "auditoria";

const SECOES: { valor: Secao; rotulo: string; soGestor?: boolean }[] = [
  { valor: "parametros", rotulo: "Parâmetros" },
  { valor: "servicos", rotulo: "Serviços" },
  { valor: "centros", rotulo: "Centros de custo" },
  { valor: "tags", rotulo: "Tags" },
  { valor: "usuarios", rotulo: "Usuários", soGestor: true },
  { valor: "dados", rotulo: "Dados e backup", soGestor: true },
  { valor: "auditoria", rotulo: "Auditoria" },
];

const SECOES_VALIDAS = new Set<string>(SECOES.map((s) => s.valor));

export function TelaConfiguracoes() {
  const { data: sessao } = useSessao();
  const params = useSearchParams();
  const router = useRouter();
  const caminho = usePathname();
  const paramsTexto = params.toString();

  // A seção mora na URL (T214) — "olha a auditoria" vira um link.
  const daUrl = params.get("secao");
  const [secao, setSecao] = useState<Secao>(
    daUrl && SECOES_VALIDAS.has(daUrl) ? (daUrl as Secao) : "parametros",
  );

  useEffect(() => {
    const p = new URLSearchParams(paramsTexto);
    const naUrl = p.get("secao");
    if (naUrl && SECOES_VALIDAS.has(naUrl) && naUrl !== secao) setSecao(naUrl as Secao);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsTexto]);

  useEffect(() => {
    const atual = new URLSearchParams(paramsTexto);
    const alvo = new URLSearchParams(paramsTexto);
    if (secao === "parametros") alvo.delete("secao");
    else alvo.set("secao", secao);
    if (alvo.toString() === atual.toString()) return;
    router.replace(`${caminho}?${alvo.toString()}`, { scroll: false });
  }, [secao, paramsTexto, caminho, router]);

  const ehGestor = sessao?.usuario.papel === "gestor";
  const visiveis = SECOES.filter((s) => !s.soGestor || ehGestor);

  return (
    <div className="mx-auto flex max-w-[var(--conteudo-largura-max)] animate-entrada flex-col gap-4 px-4 pt-5 sm:px-[30px] sm:pt-[26px] pb-11">
      <CabecalhoTela
        sobrancelha="Sistema"
        titulo="Configurações"
        apoio={
          ehGestor
            ? "Limites, prazos e cadastros que o sistema usa. Mudar aqui muda o comportamento sem precisar de deploy."
            : "Você pode ver os parâmetros; alterá-los é do gestor. A regra vale no servidor, não só neste menu."
        }
      />

      <div
        role="group"
        aria-label="Seção de configurações"
        className="flex flex-wrap items-center gap-[2px] self-start rounded-[6px] border border-linha-suave bg-segmento p-[3px]"
      >
        {visiveis.map((s) => (
          <button
            key={s.valor}
            type="button"
            aria-pressed={secao === s.valor}
            onClick={() => setSecao(s.valor)}
            className={cn(
              "rounded-[6px] px-[13px] py-[7px] font-[family-name:var(--font-display)] text-[13px] font-semibold transition-colors",
              secao === s.valor
                ? "bg-superficie-cartao text-[var(--ink-700)] shadow-[0_1px_2px_rgba(30,22,51,0.08)] dark:text-[var(--fg-strong)]"
                : "text-suave hover:text-[var(--fg)]",
            )}
          >
            {s.rotulo}
          </button>
        ))}
      </div>

      {secao === "parametros" ? <SecaoParametros podeEscrever={ehGestor} /> : null}

      {secao === "servicos" ? (
        <SecaoCadastroSimples
          titulo="Serviços da Synapse"
          descricao="Alimentam o campo “serviço vinculado” do lançamento. Cada serviço pertence a um mundo."
          recurso="servicos"
          comMundo
          podeEscrever={ehGestor}
        />
      ) : null}

      {secao === "centros" ? (
        <SecaoCadastroSimples
          titulo="Centros de custo"
          descricao="Não existe um centro chamado “Geral”: ausência de centro já significa geral."
          recurso="centros-custo"
          comMundo
          podeEscrever={ehGestor}
        />
      ) : null}

      {secao === "tags" ? (
        <SecaoCadastroSimples
          titulo="Tags"
          descricao="Livres, sem mundo e sem hierarquia. Operador pode criar; renomear e excluir é do gestor, porque afeta os lançamentos de todos."
          recurso="tags"
          comCor
          podeCriarSendoOperador
          podeEscrever={ehGestor}
        />
      ) : null}

      {secao === "usuarios" ? (
        ehGestor ? (
          <SecaoUsuarios />
        ) : (
          <EstadoVazio titulo="Seção de gestor" />
        )
      ) : null}

      {secao === "dados" ? (ehGestor ? <SecaoDados /> : <EstadoVazio titulo="Seção de gestor" />) : null}

      {secao === "auditoria" ? <SecaoAuditoria ehGestor={ehGestor} /> : null}
    </div>
  );
}
