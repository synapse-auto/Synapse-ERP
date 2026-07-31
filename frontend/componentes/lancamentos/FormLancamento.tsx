"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/componentes/ui/dialog";
import { Button } from "@/componentes/ui/button";
import { Input } from "@/componentes/ui/input";
import { Label } from "@/componentes/ui/label";
import { Textarea } from "@/componentes/ui/textarea";
import { Switch } from "@/componentes/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/componentes/ui/tabs";
import { PontoMundo } from "@/componentes/comum/BadgeMundo";
import { SeletorTags } from "./SeletorTags";
import { CamposRecorrencia } from "./CamposRecorrencia";
import { DialogoGeracaoRetroativa } from "./DialogoGeracaoRetroativa";
import { DialogoAlteracaoHistorica, DialogoSerie } from "./DialogoSerie";
import {
  useCategorias,
  useCentrosCusto,
  useConfiguracoes,
  useLancamento,
  useServicos,
} from "@/lib/consultas";
import { useEstadoGlobal } from "@/lib/estado-global";
import { ErroApi, api, mensagemDoErro, novaChaveIdempotencia } from "@/lib/api";
import { useInvalidarFinanceiro } from "@/lib/consultas";
import { useCriarLancamento, useCriarParcelamento, useEditarLancamento } from "./acoes";
import { paraApi } from "@/lib/formato";
import type { EscopoSerie, Mundo, PreviaRecorrencia } from "@/lib/tipos";

/**
 * Formulário de lançamento (T164, `FR-008`–`FR-015`; recorrência T171;
 * parcelamento T173).
 *
 * Um formulário, três destinos, porque para quem usa é o mesmo gesto:
 *
 * | Aba        | Endpoint                  |
 * |------------|---------------------------|
 * | Avulso     | `POST /api/lancamentos`   |
 * | Recorrente | `POST /api/recorrencias`  |
 * | Parcelado  | `POST /api/parcelamentos` |
 *
 * Padrões inteligentes de `FR-014`: mundo vem do seletor global, data vem
 * hoje, e `efetivar_automaticamente` vem de `configuracoes` — nunca fixo no
 * código (`RNF-02`).
 *
 * `mundo` é **obrigatório e imutável** (`RN-15`): na edição o campo aparece
 * travado, com o porquê escrito. Mandar diferente devolveria `409`.
 */

const esquema = z.object({
  modo: z.enum(["avulso", "recorrente", "parcelado"]),
  mundo: z.enum(["digital", "infra"]),
  tipo: z.enum(["receita", "despesa"]),
  descricao: z.string().trim().min(2, "Descreva o lançamento em pelo menos 2 caracteres."),
  valor: z
    .string()
    .trim()
    .min(1, "Informe o valor.")
    .refine((v) => {
      const n = Number(v.replace(",", "."));
      return Number.isFinite(n) && n > 0;
    }, "O valor é sempre positivo — o sinal vem do tipo."),
  moeda: z.enum(["BRL", "USD"]),
  cotacao_manual: z.string().optional(),
  data: z.string().min(10, "Escolha a data."),
  categoria_id: z.string().min(1, "Escolha a categoria."),
  subcategoria_id: z.string().optional(),
  servico_id: z.string().optional(),
  centro_custo_id: z.string().optional(),
  tag_ids: z.array(z.string()),
  observacoes: z.string().optional(),
  efetivar_automaticamente: z.boolean(),
  // recorrência
  frequencia: z.enum(["semanal", "mensal", "anual", "dias"]).optional(),
  intervalo_dias: z.string().optional(),
  dia_vencimento: z.string().optional(),
  data_fim: z.string().optional(),
  // parcelamento
  total_parcelas: z.string().optional(),
  intervalo: z.enum(["mensal", "semanal", "quinzenal"]).optional(),
});

export type ValoresLancamento = z.infer<typeof esquema>;

function normalizarValor(v: string): string {
  return String(Number(v.replace(/\./g, "").replace(",", "."))) === "NaN"
    ? v
    : Number(v.replace(/\s/g, "").replace(",", ".")).toFixed(2);
}

export function FormLancamento({
  aberto,
  aoFechar,
  rascunho,
  idParaEditar = null,
}: {
  aberto: boolean;
  aoFechar: () => void;
  rascunho?: Record<string, unknown> | null;
  idParaEditar?: string | null;
}) {
  const mundoGlobal = useEstadoGlobal((e) => e.mundo);
  const { data: configuracoes } = useConfiguracoes();
  const { data: categorias } = useCategorias();
  const invalidar = useInvalidarFinanceiro();

  const criar = useCriarLancamento();
  const editar = useEditarLancamento();
  const criarParcelamento = useCriarParcelamento();
  const { data: existente } = useLancamento(idParaEditar);

  const [enviando, setEnviando] = useState(false);
  const [previaRetroativa, setPreviaRetroativa] = useState<{
    previa: PreviaRecorrencia;
    mensagem: string;
  } | null>(null);
  const [perguntandoEscopo, setPerguntandoEscopo] = useState(false);
  const [escopoSerie, setEscopoSerie] = useState<EscopoSerie | null>(null);
  const [avisoHistorico, setAvisoHistorico] = useState<string | null>(null);

  const efetivacaoPadrao = Boolean(
    (configuracoes?.efetivacao_automatica_padrao?.valor as boolean | undefined) ?? true,
  );

  const mundoPadrao: Mundo = mundoGlobal === "ambos" ? "digital" : mundoGlobal;

  const padroes = useMemo<ValoresLancamento>(
    () => ({
      modo: "avulso",
      mundo: mundoPadrao,
      tipo: "despesa",
      descricao: "",
      valor: "",
      moeda: "BRL",
      cotacao_manual: "",
      data: paraApi(new Date()),
      categoria_id: "",
      subcategoria_id: "",
      servico_id: "",
      centro_custo_id: "",
      tag_ids: [],
      observacoes: "",
      efetivar_automaticamente: efetivacaoPadrao,
      frequencia: "mensal",
      intervalo_dias: "",
      dia_vencimento: String(new Date().getDate()),
      data_fim: "",
      total_parcelas: "3",
      intervalo: "mensal",
      ...(rascunho as Partial<ValoresLancamento> | undefined),
    }),
    [mundoPadrao, efetivacaoPadrao, rascunho],
  );

  const form = useForm<ValoresLancamento>({
    resolver: zodResolver(esquema),
    defaultValues: padroes,
  });

  const { register, handleSubmit, control, watch, reset, formState } = form;

  useEffect(() => {
    if (aberto && !idParaEditar) reset(padroes);
  }, [aberto, idParaEditar, padroes, reset]);

  useEffect(() => {
    if (!existente) return;
    reset({
      ...padroes,
      modo: "avulso",
      mundo: existente.mundo,
      tipo: existente.tipo,
      descricao: existente.descricao,
      valor: existente.valor,
      moeda: existente.moeda_origem,
      data: existente.data,
      categoria_id: existente.categoria.id,
      subcategoria_id: existente.subcategoria?.id ?? "",
      servico_id: existente.servico?.id ?? "",
      centro_custo_id: existente.centro_custo?.id ?? "",
      tag_ids: existente.tags.map((t) => t.id),
      observacoes: existente.observacoes ?? "",
      efetivar_automaticamente: existente.efetivar_automaticamente,
    });
  }, [existente, padroes, reset]);

  const modo = watch("modo");
  const mundo = watch("mundo");
  const tipo = watch("tipo");
  const moeda = watch("moeda");
  const categoriaId = watch("categoria_id");

  const { data: servicos } = useServicos(mundo);
  const { data: centros } = useCentrosCusto(mundo);

  const categoria = (categorias?.itens ?? []).find((c) => c.id === categoriaId);
  const exigeSubcategoria = Boolean(categoria?.especial);
  const categoriasDoTipo = (categorias?.itens ?? []).filter(
    (c) => c.tipo === "ambas" || c.tipo === tipo,
  );

  function corpoBase(v: ValoresLancamento) {
    return {
      mundo: v.mundo,
      tipo: v.tipo,
      descricao: v.descricao.trim(),
      data: v.data,
      moeda: v.moeda,
      valor: normalizarValor(v.valor),
      cotacao_manual: v.cotacao_manual ? normalizarValor(v.cotacao_manual) : null,
      categoria_id: v.categoria_id,
      subcategoria_id: v.subcategoria_id || null,
      servico_id: v.servico_id || null,
      centro_custo_id: v.centro_custo_id || null,
      tag_ids: v.tag_ids,
      observacoes: v.observacoes?.trim() || null,
      efetivar_automaticamente: v.efetivar_automaticamente,
    };
  }

  async function enviar(
    v: ValoresLancamento,
    criarOutro = false,
    confirmarRetroativa = false,
    escopo: EscopoSerie | null = escopoSerie,
    confirmarHistorica = false,
  ) {
    setEnviando(true);
    try {
      if (idParaEditar && existente) {
        // Lançamento vindo de recorrência exige `escopo_serie` (`RN-07`).
        // Perguntamos antes, com o contexto na tela, em vez de deixar o
        // `422` do servidor virar erro depois de a pessoa já ter salvado.
        if (existente.origem.tipo === "recorrencia" && !escopo) {
          setPerguntandoEscopo(true);
          setEnviando(false);
          return;
        }
        await editar.mutateAsync({
          id: idParaEditar,
          corpo: {
            ...corpoBase(v),
            versao: existente.versao,
            escopo_serie: escopo,
            confirmar_alteracao_historica: confirmarHistorica,
          },
        });
        toast.success("Lançamento atualizado.");
        setEscopoSerie(null);
        aoFechar();
        return;
      }

      if (v.modo === "recorrente") {
        const corpo = {
          ...corpoBase(v),
          frequencia: v.frequencia,
          intervalo_dias: v.frequencia === "dias" ? Number(v.intervalo_dias || 0) : null,
          dia_vencimento: v.frequencia === "mensal" ? Number(v.dia_vencimento || 1) : null,
          mes_vencimento: null,
          data_inicio: v.data,
          data_fim: v.data_fim || null,
          total_parcelas: null,
          confirmar_geracao_retroativa: confirmarRetroativa,
        };
        await api.post("/api/recorrencias", {
          corpo,
          chaveIdempotencia: novaChaveIdempotencia(),
        });
        invalidar();
        toast.success("Recorrência criada.");
      } else if (v.modo === "parcelado") {
        await criarParcelamento.mutateAsync({
          mundo: v.mundo,
          tipo: v.tipo,
          descricao: v.descricao.trim(),
          valor_total: normalizarValor(v.valor),
          total_parcelas: Number(v.total_parcelas || 2),
          data_primeira_parcela: v.data,
          intervalo: v.intervalo ?? "mensal",
          categoria_id: v.categoria_id,
          subcategoria_id: v.subcategoria_id || null,
          servico_id: v.servico_id || null,
          efetivar_automaticamente: v.efetivar_automaticamente,
        });
        toast.success(`Parcelamento em ${v.total_parcelas} criado.`);
      } else {
        await criar.mutateAsync(corpoBase(v));
        toast.success("Lançamento criado.");
      }

      if (criarOutro) {
        // "Salvar e criar outro" (`FR-015`): mantém mundo, tipo, categoria e
        // data — o que se repete numa sequência de digitação — e limpa o que
        // muda a cada linha.
        reset({
          ...v,
          descricao: "",
          valor: "",
          observacoes: "",
        });
      } else {
        aoFechar();
      }
    } catch (e) {
      if (e instanceof ErroApi && e.pedeConfirmacao && e.previa) {
        setPreviaRetroativa({
          previa: e.previa as unknown as PreviaRecorrencia,
          mensagem: e.message,
        });
      } else if (e instanceof ErroApi && e.pedeConfirmacao) {
        // `422` sem prévia numérica: é a confirmação de alteração histórica
        // (data-model §5.8). A frase mostrada é a do servidor.
        setAvisoHistorico(e.message);
      } else {
        const texto = mensagemDoErro(e);
        if (texto) toast.error(texto);
      }
    } finally {
      setEnviando(false);
    }
  }

  const titulo = idParaEditar
    ? "Editar lançamento"
    : modo === "recorrente"
      ? "Nova recorrência"
      : modo === "parcelado"
        ? "Novo parcelamento"
        : "Novo lançamento";

  return (
    <>
      <Dialog open={aberto} onOpenChange={(v) => (!v ? aoFechar() : undefined)}>
        <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-[720px]">
          <DialogHeader>
            <DialogTitle>{titulo}</DialogTitle>
            <DialogDescription>
              {idParaEditar
                ? "O mundo não muda depois de criado — é o que mantém os dois caixas separados."
                : "Valor sempre positivo: o sinal vem do tipo."}
            </DialogDescription>
          </DialogHeader>

          <form
            onSubmit={handleSubmit((v) => enviar(v, false))}
            className="flex flex-col gap-5"
            noValidate
          >
            {/* Tipo + modo */}
            <div className="flex flex-wrap items-center gap-3">
              <Controller
                control={control}
                name="tipo"
                render={({ field }) => (
                  <Tabs value={field.value} onValueChange={field.onChange}>
                    <TabsList>
                      <TabsTrigger value="receita">Receita</TabsTrigger>
                      <TabsTrigger value="despesa">Despesa</TabsTrigger>
                    </TabsList>
                  </Tabs>
                )}
              />

              {!idParaEditar ? (
                <Controller
                  control={control}
                  name="modo"
                  render={({ field }) => (
                    <Tabs value={field.value} onValueChange={field.onChange}>
                      <TabsList>
                        <TabsTrigger value="avulso">Avulso</TabsTrigger>
                        <TabsTrigger value="recorrente">Recorrente</TabsTrigger>
                        <TabsTrigger value="parcelado">Parcelado</TabsTrigger>
                      </TabsList>
                    </Tabs>
                  )}
                />
              ) : null}
            </div>

            {/* Mundo */}
            <div className="flex flex-col gap-1.5">
              <Label>Mundo</Label>
              <Controller
                control={control}
                name="mundo"
                render={({ field }) => (
                  <div className="flex items-center gap-2">
                    {(["digital", "infra"] as Mundo[]).map((m) => (
                      <button
                        key={m}
                        type="button"
                        disabled={Boolean(idParaEditar)}
                        onClick={() => field.onChange(m)}
                        className="flex h-9 items-center gap-2 rounded-[10px] border px-3 font-[family-name:var(--font-display)] text-[12.5px] font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                        style={
                          field.value === m
                            ? {
                                background: `var(--mundo-${m}-bg)`,
                                color: `var(--mundo-${m}-fg)`,
                                borderColor: `var(--mundo-${m})`,
                              }
                            : { borderColor: "var(--linha-controle)", color: "var(--fg-muted)" }
                        }
                      >
                        <PontoMundo mundo={m} className="size-[7px]" />
                        {m === "digital" ? "Synapse Digital" : "Synapse Infra"}
                      </button>
                    ))}
                  </div>
                )}
              />
              <p className="text-[11.5px] text-sutil">
                {idParaEditar
                  ? "O mundo é imutável depois de criado (RN-15)."
                  : mundoGlobal === "ambos"
                    ? "Padrão: Digital — o seletor global está em Ambos."
                    : `Herdado do seletor global · Synapse ${mundoGlobal === "digital" ? "Digital" : "Infra"}.`}
              </p>
            </div>

            {/* Descrição */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="descricao">Descrição</Label>
              <Input id="descricao" autoFocus {...register("descricao")} />
              {formState.errors.descricao ? (
                <Erro>{formState.errors.descricao.message}</Erro>
              ) : null}
            </div>

            {/* Valor + moeda + data */}
            <div className="grid gap-4 sm:grid-cols-[1fr_110px_170px]">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="valor">
                  {modo === "parcelado" ? "Valor total" : "Valor"}
                </Label>
                <Input
                  id="valor"
                  inputMode="decimal"
                  placeholder="0,00"
                  className="numerico"
                  {...register("valor")}
                />
                {formState.errors.valor ? <Erro>{formState.errors.valor.message}</Erro> : null}
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="moeda">Moeda</Label>
                <select
                  id="moeda"
                  {...register("moeda")}
                  className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
                >
                  <option value="BRL">BRL</option>
                  <option value="USD">USD</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="data">
                  {modo === "recorrente"
                    ? "Início"
                    : modo === "parcelado"
                      ? "1ª parcela"
                      : "Data"}
                </Label>
                <Input id="data" type="date" {...register("data")} />
              </div>
            </div>

            {moeda === "USD" ? (
              <p className="rounded-[10px] bg-[var(--st-programado-bg)] px-3 py-2 text-[12px] text-[var(--st-programado-fg)]">
                O servidor busca a cotação da <strong>data do lançamento</strong> e grava o valor
                em reais, o valor original e a cotação usada. Se as duas fontes falharem, ele pede
                a cotação manual.
              </p>
            ) : null}

            {/* Classificação */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="categoria_id">Categoria</Label>
                <select
                  id="categoria_id"
                  {...register("categoria_id")}
                  className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
                >
                  <option value="">Escolha…</option>
                  {categoriasDoTipo.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome}
                    </option>
                  ))}
                </select>
                {formState.errors.categoria_id ? (
                  <Erro>{formState.errors.categoria_id.message}</Erro>
                ) : null}
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="subcategoria_id">
                  Subcategoria{exigeSubcategoria ? "" : " (opcional)"}
                </Label>
                <select
                  id="subcategoria_id"
                  {...register("subcategoria_id")}
                  disabled={!categoria}
                  className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none disabled:opacity-50"
                >
                  <option value="">{exigeSubcategoria ? "Escolha…" : "Nenhuma"}</option>
                  {(categoria?.subcategorias ?? []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nome}
                    </option>
                  ))}
                </select>
                {exigeSubcategoria ? (
                  <p className="text-[11.5px] text-sutil">
                    {categoria?.nome} é categoria especial: a subcategoria diz de qual{" "}
                    {categoria?.vinculo === "cliente" ? "cliente" : "funcionário"} é o lançamento.
                  </p>
                ) : null}
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="servico_id">Serviço vinculado (opcional)</Label>
                <select
                  id="servico_id"
                  {...register("servico_id")}
                  className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
                >
                  <option value="">Nenhum</option>
                  {(servicos?.itens ?? []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nome}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="centro_custo_id">Centro de custo (opcional)</Label>
                <select
                  id="centro_custo_id"
                  {...register("centro_custo_id")}
                  className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
                >
                  <option value="">Geral</option>
                  {(centros?.itens ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome}
                    </option>
                  ))}
                </select>
                <p className="text-[11.5px] text-sutil">
                  Sem centro significa “geral” — não existe um centro chamado Geral.
                </p>
              </div>
            </div>

            {/* Recorrência / parcelamento */}
            {modo === "recorrente" ? <CamposRecorrencia form={form} /> : null}

            {modo === "parcelado" ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="total_parcelas">Parcelas</Label>
                  <Input
                    id="total_parcelas"
                    type="number"
                    min={2}
                    max={360}
                    {...register("total_parcelas")}
                  />
                  <p className="text-[11.5px] text-sutil">
                    A última parcela absorve a diferença de arredondamento — a soma fecha exata.
                  </p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="intervalo">Intervalo</Label>
                  <select
                    id="intervalo"
                    {...register("intervalo")}
                    className="h-9 rounded-[10px] border border-linha-controle bg-superficie-cartao px-2 text-[13px] outline-none"
                  >
                    <option value="mensal">Mensal</option>
                    <option value="quinzenal">Quinzenal</option>
                    <option value="semanal">Semanal</option>
                  </select>
                </div>
              </div>
            ) : null}

            {/* Tags e observações */}
            <div className="flex flex-col gap-1.5">
              <Label>Tags</Label>
              <Controller
                control={control}
                name="tag_ids"
                render={({ field }) => (
                  <SeletorTags selecionadas={field.value} aoMudar={field.onChange} />
                )}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="observacoes">Observações (opcional)</Label>
              <Textarea id="observacoes" rows={2} {...register("observacoes")} />
            </div>

            {/* Efetivação */}
            <label className="flex items-start justify-between gap-4 rounded-[12px] border border-linha-suave bg-[var(--bg-subtle)] px-4 py-3">
              <span className="flex flex-col gap-0.5">
                <span className="text-[13px] font-semibold text-[var(--fg)]">
                  Efetivar automaticamente na data
                </span>
                <span className="text-[11.5px] text-suave">
                  Ligado, o lançamento se efetiva sozinho e nunca vence. Desligado, ele fica
                  pendente até alguém confirmar — e só assim pode virar atrasado e gerar alerta.
                </span>
              </span>
              <Controller
                control={control}
                name="efetivar_automaticamente"
                render={({ field }) => (
                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                )}
              />
            </label>

            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={aoFechar}>
                Cancelar
              </Button>
              {!idParaEditar ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={enviando}
                  onClick={handleSubmit((v) => enviar(v, true))}
                >
                  Salvar e criar outro
                </Button>
              ) : null}
              <Button type="submit" disabled={enviando}>
                {enviando ? <Loader2 className="animate-spin" size={16} /> : null}
                {idParaEditar ? "Salvar" : "Criar"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <DialogoGeracaoRetroativa
        dados={previaRetroativa}
        aoCancelar={() => setPreviaRetroativa(null)}
        aoConfirmar={() => {
          setPreviaRetroativa(null);
          void handleSubmit((v) => enviar(v, false, true))();
        }}
      />

      <DialogoSerie
        aberto={perguntandoEscopo}
        rotuloDaSerie={existente?.origem.rotulo}
        aoCancelar={() => setPerguntandoEscopo(false)}
        aoEscolher={(escopo) => {
          setPerguntandoEscopo(false);
          setEscopoSerie(escopo);
          void handleSubmit((v) => enviar(v, false, false, escopo))();
        }}
      />

      <DialogoAlteracaoHistorica
        mensagem={avisoHistorico}
        aoCancelar={() => setAvisoHistorico(null)}
        aoConfirmar={() => {
          setAvisoHistorico(null);
          void handleSubmit((v) => enviar(v, false, false, escopoSerie, true))();
        }}
      />
    </>
  );
}

function Erro({ children }: { children?: React.ReactNode }) {
  return (
    <p role="alert" className="text-[11.5px] text-[var(--danger-500)]">
      {children}
    </p>
  );
}
