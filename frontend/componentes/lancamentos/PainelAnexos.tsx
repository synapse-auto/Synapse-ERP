"use client";

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Download, FileText, Loader2, Paperclip, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { EstadoVazio } from "@/componentes/comum/EstadoVazio";
import { api, mensagemDoErro } from "@/lib/api";
import { useConfiguracoes, useInvalidarFinanceiro } from "@/lib/consultas";
import type { Anexo, LancamentoDetalhe } from "@/lib/tipos";

/**
 * Anexos (T168, `FR-013`).
 *
 * Três coisas que o contrato exige e que estão aqui:
 *
 * - **Nunca falha em silêncio**: arquivo grande volta `413` e formato não
 *   permitido volta `415`, os dois com a mensagem já pronta do servidor
 *   (que inclui o limite configurado). A tela mostra o texto que veio.
 * - **Todos os arquivos são validados antes de qualquer upload** — quem faz
 *   isso é o backend; aqui mandamos os arquivos numa requisição só, que é o
 *   que permite a ele recusar o conjunto inteiro.
 * - **O download aponta para `/api/anexos/{id}`**, não para uma URL assinada
 *   guardada: o `302` é gerado no momento do clique, com validade curta.
 */
export function PainelAnexos({ lancamento }: { lancamento: LancamentoDetalhe }) {
  const entrada = useRef<HTMLInputElement>(null);
  const [arrastando, setArrastando] = useState(false);
  const invalidar = useInvalidarFinanceiro();
  const { data: configuracoes } = useConfiguracoes();

  const limiteMb = (configuracoes?.anexo_tamanho_max_mb?.valor as number | undefined) ?? null;

  const ehParteDeSplit = lancamento.origem.tipo === "split";

  const enviar = useMutation({
    mutationFn: (arquivos: FileList | File[]) => {
      const dados = new FormData();
      for (const a of Array.from(arquivos)) dados.append("arquivos", a);
      return api.post<{ itens: Anexo[] }>(`/api/lancamentos/${lancamento.id}/anexos`, {
        formulario: dados,
      });
    },
    onSuccess: (r) => {
      invalidar();
      toast.success(
        `${r.itens.length} ${r.itens.length === 1 ? "arquivo anexado" : "arquivos anexados"}.`,
      );
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  const remover = useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/anexos/${id}`),
    onSuccess: () => {
      invalidar();
      toast.success("Anexo removido.");
    },
    onError: (e) => toast.error(mensagemDoErro(e)),
  });

  if (ehParteDeSplit) {
    return (
      <p className="rounded-[10px] bg-[var(--bg-subtle)] px-3 py-2.5 text-[12px] text-suave">
        Parte de split não recebe anexo próprio: o comprovante mora no lançamento original e vale
        para todas as partes.
        {lancamento.anexos.length > 0 ? " Os arquivos abaixo são os do original." : ""}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {lancamento.anexos.length === 0 ? (
        <EstadoVazio
          titulo="Nenhum anexo"
          descricao="Nota fiscal, recibo, comprovante — o que precisar ficar junto do lançamento."
          icone={<Paperclip size={18} />}
          compacto
        />
      ) : (
        <ul className="flex flex-col gap-1.5">
          {lancamento.anexos.map((a) => (
            <li
              key={a.id}
              className="flex items-center gap-3 rounded-[10px] border border-linha-suave px-3 py-2"
            >
              <FileText size={16} className="flex-none text-suave" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12.5px] text-[var(--fg)]">
                  {a.nome_arquivo}
                </span>
                <span className="text-[10.5px] text-sutil">
                  {(a.tamanho_bytes / 1024).toFixed(0)} KB
                </span>
              </span>
              <a
                href={a.url}
                target="_blank"
                rel="noreferrer"
                aria-label={`Baixar ${a.nome_arquivo}`}
                className="rounded-[7px] p-1.5 text-suave transition-colors hover:bg-[var(--bg-subtle)]"
              >
                <Download size={15} />
              </a>
              <button
                type="button"
                aria-label={`Remover ${a.nome_arquivo}`}
                onClick={() => remover.mutate(a.id)}
                className="rounded-[7px] p-1.5 text-suave transition-colors hover:bg-[var(--st-atrasado-bg)] hover:text-[var(--st-atrasado-fg)]"
              >
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastando(false);
          if (e.dataTransfer.files.length) enviar.mutate(e.dataTransfer.files);
        }}
        className={`flex flex-col items-center gap-2 rounded-[12px] border border-dashed px-4 py-5 text-center transition-colors ${
          arrastando
            ? "border-[var(--brand)] bg-[var(--brand-tint)]"
            : "border-linha-controle bg-[var(--bg-subtle)]"
        }`}
      >
        <Upload size={18} className="text-suave" />
        <p className="text-[12px] text-suave">
          Arraste arquivos aqui ou{" "}
          <button
            type="button"
            onClick={() => entrada.current?.click()}
            className="font-semibold text-[var(--brand-hover)] underline underline-offset-2"
          >
            escolha do computador
          </button>
        </p>
        {limiteMb ? (
          <p className="text-[10.5px] text-sutil">Limite de {limiteMb} MB por arquivo.</p>
        ) : null}
        {enviar.isPending ? (
          <span className="flex items-center gap-2 text-[11.5px] text-suave">
            <Loader2 size={13} className="animate-spin" />
            Enviando…
          </span>
        ) : null}
        <input
          ref={entrada}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) enviar.mutate(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
