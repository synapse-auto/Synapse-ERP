/**
 * Tipos da fronteira com a API.
 *
 * Espelham `specs/001-erp-financeiro-synapse/contracts/*.md`. Divergência aqui
 * é bug de contrato, não liberdade do frontend (contracts/README.md).
 *
 * Convenções que valem para todos:
 * - dinheiro é `string` decimal (`"1234.56"`), nunca `number`;
 * - data é `string` `YYYY-MM-DD`; instante é ISO 8601 com fuso;
 * - ausência é `null` explícito, nunca campo omitido.
 */

/* ------------------------------------------------------------------ */
/* Enumerações — migração 001_extensoes_e_tipos.sql                    */
/* ------------------------------------------------------------------ */

export type Mundo = "digital" | "infra";
/** O seletor da tela tem três estados; `ambos` só existe na consulta (`RF-101`). */
export type MundoFiltro = Mundo | "ambos";
export type TipoLancamento = "receita" | "despesa";
export type StatusLancamento = "programado" | "pendente" | "efetivado" | "atrasado" | "cancelado";
export type TipoCategoria = "receita" | "despesa" | "ambas";
export type PapelUsuario = "gestor" | "operador";
export type FrequenciaRecorrencia = "semanal" | "mensal" | "anual" | "dias";
export type TipoCobranca = "pontual" | "recorrente" | "parcelada";
export type TipoContratacao = "pj" | "freelancer";
export type MoedaCodigo = "BRL" | "USD";
export type VinculoSubcategoria = "cliente" | "funcionario";
export type TipoNotificacao = "vencimento" | "inadimplencia" | "resumo_semanal" | "caixa_baixo";
export type AcaoAuditoria = "criacao" | "edicao" | "exclusao" | "restauracao";

export type AtalhoPeriodo =
  | "hoje"
  | "esta_semana"
  | "este_mes"
  | "mes_passado"
  | "ultimos_3_meses"
  | "este_ano"
  | "personalizado";

export type SituacaoCliente = "em_dia" | "atrasado";
export type Semaforo = "verde" | "amarelo" | "vermelho";
export type DirecaoVariacao = "alta" | "baixa" | "estavel";
export type EscopoSerie = "apenas_esta" | "esta_e_futuras";
export type TipoOrigem = "recorrencia" | "parcelamento" | "split" | "manual" | "importacao";
export type Tema = "claro" | "escuro" | "auto";

/* ------------------------------------------------------------------ */
/* Blocos reaproveitados                                               */
/* ------------------------------------------------------------------ */

export interface Comparativo {
  valor_anterior?: string | null;
  /** `null` — não `"0.0"` — quando o período anterior é zero (consultas.md §1). */
  variacao_percentual?: string | null;
  direcao?: DirecaoVariacao | null;
}

export interface PeriodoResolvido {
  inicio: string;
  fim: string;
  rotulo: string;
  anterior?: { inicio: string; fim: string } | null;
}

export type QuebraPorMundo = Partial<Record<Mundo, string>>;

/** Corpo de query pronto para `GET /api/lancamentos` (`FR-058`). */
export type FiltroDrilldown = Record<string, string | number | boolean | string[] | null>;

export interface PontoSerie {
  rotulo: string;
  valor: string;
}

/* ------------------------------------------------------------------ */
/* Cadastros                                                           */
/* ------------------------------------------------------------------ */

export interface CategoriaResumo {
  id: string;
  nome: string;
  cor: string | null;
  icone: string | null;
  especial: boolean;
  vinculo: VinculoSubcategoria | null;
}

export interface SubcategoriaResumo {
  id: string;
  nome: string;
  cor: string | null;
  cliente_id: string | null;
  funcionario_id?: string | null;
}

export interface Uso {
  quantidade_lancamentos: number;
  total_movimentado: string;
}

export interface Subcategoria extends SubcategoriaResumo {
  uso: Uso;
  arquivada_em?: string | null;
}

export interface Categoria extends CategoriaResumo {
  tipo: TipoCategoria;
  ordem: number;
  arquivada_em: string | null;
  uso: Uso;
  subcategorias: Subcategoria[];
}

export interface Servico {
  id: string;
  nome: string;
  mundo: Mundo;
  ativo?: boolean;
  ordem?: number;
  arquivado_em?: string | null;
}

export interface CentroCusto {
  id: string;
  nome: string;
  mundo: Mundo;
  arquivado_em?: string | null;
}

export interface Tag {
  id: string;
  nome: string;
  cor: string | null;
}

export interface Cliente {
  id: string;
  nome: string;
  empresa: string | null;
  contato_email: string | null;
  contato_telefone: string | null;
  tipo_cobranca: TipoCobranca;
  valor_recorrente: string | null;
  dia_cobranca: number | null;
  /** Mundo em que a mensalidade gera lançamento. O cliente não tem mundo (D-04). */
  mundo_cobranca: Mundo | null;
  servicos: Pick<Servico, "id" | "nome">[];
  situacao: SituacaoCliente;
  /** `null`, não `0`, quando não há atraso (cadastros.md §3). */
  dias_atraso: number | null;
  valor_atrasado: string | null;
  quantidade_em_atraso?: number | null;
  tolerancia_dias?: number | null;
  total_recebido_periodo: string;
  total_recebido_historico: string;
  /** Cliente sem lançamento nenhum aparece nos três estados do seletor (D-04). */
  sem_movimentacao?: boolean;
  observacoes?: string | null;
  arquivado_em: string | null;
}

export interface RecorrenciaResumo {
  id: string;
  /** Texto pronto ("Mensal, dia 10") — a tela não monta a leitura (`RNF-02`). */
  rotulo: string;
  ativa: boolean;
  efetivar_automaticamente: boolean;
  aviso_inadimplencia?: string | null;
}

export interface ClientePerfil extends Cliente {
  quebra_por_mundo: QuebraPorMundo;
  receita_mensal: { mes: string; valor: string }[];
  lancamentos: PaginaDe<Lancamento>;
  proximos_recebimentos: {
    lancamento_id: string;
    data: string;
    valor: string;
    status: StatusLancamento;
  }[];
  recorrencia: RecorrenciaResumo | null;
}

export interface Funcionario {
  id: string;
  nome: string;
  funcao: string | null;
  tipo_contratacao: TipoContratacao;
  valor_mensal: string;
  dia_pagamento: number;
  /** Funcionário TEM mundo, obrigatório e imutável (`RN-15`). */
  mundo: Mundo;
  custo_periodo?: string;
  custo_historico?: string;
  arquivado_em: string | null;
}

/**
 * Uma linha de pagamento no perfil do funcionário.
 *
 * **Não é um `Lancamento`**, e a chave do id é `lancamento_id`, não `id`: o
 * perfil devolve o recorte que a tela mostra, apontando de volta para o
 * lançamento. `pagamentos` e `proximos_pagamentos` seguem a mesma forma — o
 * segundo sem `descricao` nem `da_folha`.
 */
export interface PagamentoDoFuncionario {
  lancamento_id: string;
  data: string;
  valor: string;
  status: StatusLancamento;
  descricao?: string;
  da_folha?: boolean;
}

export interface FuncionarioPerfil extends Funcionario {
  /**
   * Lista simples, **não** `PaginaDe<>`: o perfil não pagina os pagamentos.
   * Estava tipado como página, e `f.pagamentos.itens` derrubava a tela inteira
   * com `Cannot read properties of undefined (reading 'length')`.
   */
  pagamentos: PagamentoDoFuncionario[];
  proximos_pagamentos: PagamentoDoFuncionario[];
  recorrencia: RecorrenciaResumo | null;
}

/* ------------------------------------------------------------------ */
/* Lançamentos — contracts/lancamentos.md §1                           */
/* ------------------------------------------------------------------ */

export interface Origem {
  tipo: TipoOrigem;
  id: string | null;
  rotulo: string | null;
}

export interface Lancamento {
  id: string;
  mundo: Mundo;
  tipo: TipoLancamento;
  descricao: string;
  valor: string;
  data: string;
  status: StatusLancamento;
  efetivar_automaticamente: boolean;
  categoria: CategoriaResumo;
  subcategoria: SubcategoriaResumo | null;
  servico: Servico | null;
  centro_custo: CentroCusto | null;
  tags: Tag[];
  moeda_origem: MoedaCodigo;
  valor_origem: string | null;
  cotacao: string | null;
  cotacao_manual?: boolean;
  origem: Origem;
  tem_anexos: boolean;
  quantidade_anexos: number;
  versao: number;
  observacoes?: string | null;
  parcela_numero?: number | null;
  parcela_total?: number | null;
  /** Só na lixeira (`FR-017`). */
  dias_restantes?: number;
  excluido_em?: string | null;
}

export interface Anexo {
  id: string;
  nome_arquivo: string;
  mime_type: string;
  tamanho_bytes: number;
  criado_em: string;
  /** É o endpoint `/api/anexos/{id}`, não a URL assinada (lancamentos.md §1). */
  url: string;
}

export interface EventoAuditoria {
  id?: number;
  entidade?: string;
  entidade_id?: string;
  acao: AcaoAuditoria;
  usuario: { id: string; nome: string } | null;
  criado_em: string;
  alteracoes: Record<string, { de: unknown; para: unknown }> | null;
  alteracao_historica: boolean;
}

export type AcaoDisponivel =
  | "editar"
  | "duplicar"
  | "dividir"
  | "excluir"
  | "confirmar_efetivacao"
  | "cancelar"
  | "restaurar";

export interface LancamentoDetalhe extends Lancamento {
  anexos: Anexo[];
  partes_split: Lancamento[];
  lancamento_pai: Lancamento | null;
  historico: EventoAuditoria[];
  /** Calculado no servidor a partir do status e do papel (`FR-042`). */
  acoes_disponiveis: AcaoDisponivel[];
}

export interface ResumoFiltrado {
  total_receitas: string;
  total_despesas: string;
  resultado: string;
  quantidade: number;
}

export interface PaginacaoApi {
  pagina: number;
  por_pagina: number;
  total: number;
  total_paginas: number;
}

export interface PaginaDe<T> {
  itens: T[];
  paginacao: PaginacaoApi;
}

export interface ListaLancamentos extends PaginaDe<Lancamento> {
  resumo_filtrado: ResumoFiltrado;
  /** Só vem quando `mundo=ambos` (`FR-003`). */
  quebra_por_mundo?: QuebraPorMundo | null;
}

export interface CorpoLancamento {
  mundo: Mundo;
  tipo: TipoLancamento;
  descricao: string;
  data: string;
  moeda: MoedaCodigo;
  valor: string;
  cotacao_manual?: string | null;
  categoria_id: string;
  subcategoria_id?: string | null;
  servico_id?: string | null;
  centro_custo_id?: string | null;
  tag_ids?: string[];
  observacoes?: string | null;
  efetivar_automaticamente: boolean;
}

export interface CorpoEdicaoLancamento extends CorpoLancamento {
  versao: number;
  escopo_serie?: EscopoSerie | null;
  confirmar_alteracao_historica?: boolean;
}

export interface ParteSplit {
  descricao: string;
  valor: string;
  categoria_id: string;
  subcategoria_id?: string | null;
  centro_custo_id?: string | null;
}

export type AcaoEmMassa =
  | "excluir"
  | "mudar_categoria"
  | "mudar_status"
  | "adicionar_tags"
  | "remover_tags";

export interface RespostaLote {
  criados: number;
  erros: {
    indice: number;
    codigo: string;
    requisito: string | null;
    mensagem: string;
    campos: Record<string, string> | null;
  }[];
  itens: Lancamento[];
}

/* ------------------------------------------------------------------ */
/* Recorrências e parcelamentos                                        */
/* ------------------------------------------------------------------ */

export interface Recorrencia {
  id: string;
  mundo: Mundo;
  tipo: TipoLancamento;
  descricao: string;
  valor: string;
  categoria: CategoriaResumo;
  subcategoria: SubcategoriaResumo | null;
  servico: Servico | null;
  frequencia: FrequenciaRecorrencia;
  intervalo_dias: number | null;
  dia_vencimento: number | null;
  mes_vencimento: number | null;
  data_inicio: string;
  data_fim: string | null;
  total_parcelas: number | null;
  efetivar_automaticamente: boolean;
  ativa: boolean;
  rotulo: string;
  proxima_ocorrencia: string | null;
  ocorrencias_geradas: number;
  cliente_id?: string | null;
  funcionario_id?: string | null;
}

export interface PreviaRecorrencia {
  total_ocorrencias: number;
  retroativas_efetivadas: number;
  primeira: string;
  ultima: string;
  valor_total_retroativo?: string | null;
}

export interface RespostaPrevia {
  previa: PreviaRecorrencia;
  limiar_de_confirmacao: number;
  horizonte: string;
}

/** Geração longa em lotes com cursor (research.md D-02a). */
export interface EstadoGeracao {
  concluida: boolean;
  cursor: string | null;
  geradas: number;
  total: number;
}

export interface RespostaRecorrencia extends Recorrencia {
  geracao?: EstadoGeracao | null;
  ocorrencias_futuras_regeradas?: number;
  ocorrencias_futuras_removidas?: number;
}

export interface Parcelamento {
  id: string;
  mundo: Mundo;
  descricao: string;
  valor_total: string;
  total_parcelas: number;
  /** Soma só as parcelas `efetivado` (`RN-05`). */
  pago: string;
  a_pagar: string;
  criado_em: string;
  parcelas: {
    id: string;
    numero: number;
    total: number;
    rotulo: string;
    descricao: string;
    valor: string;
    data: string;
    status: StatusLancamento;
  }[];
}

/* ------------------------------------------------------------------ */
/* Dashboard — contracts/consultas.md §1                               */
/* ------------------------------------------------------------------ */

export interface CardDisponivel {
  id: string;
  rotulo: string;
  grupo: string;
  ordem: number;
  visivel?: boolean;
  descricao?: string | null;
}

export interface CardDashboard {
  id: string;
  rotulo: string;
  grupo: string;
  ordem: number;
  valor: string;
  unidade?: "moeda" | "percentual" | "quantidade";
  comparativo: Comparativo;
  quebra_por_mundo?: QuebraPorMundo | null;
  tendencia?: PontoSerie[] | null;
  composicao?: { situacao: StatusLancamento; quantidade: number; valor: string }[] | null;
  filtro_drilldown: FiltroDrilldown | null;
}

export interface SaudeCaixa {
  semaforo: Semaforo;
  /** `null` quando não há despesa fixa no horizonte — nunca "∞×". */
  cobertura: string | null;
  saldo: string;
  despesas_fixas_horizonte: string;
  horizonte_dias: number;
  multiplicadores: { minimo: number; folga: number };
  explicacao: string;
}

export interface PontoFluxo {
  mes: string;
  receitas: string;
  despesas: string;
  resultado: string;
  /** Mês futuro — desenhado distinto (`FR-059`, `RN-05`). */
  projetado: boolean;
}

export interface PontoSaldo {
  mes: string;
  saldo_final: string;
  projetado: boolean;
}

export interface FatiaCategoria {
  categoria_id: string;
  nome: string;
  cor: string | null;
  valor: string;
  percentual: string | null;
  filtro_drilldown: FiltroDrilldown | null;
}

export interface Dashboard {
  periodo: PeriodoResolvido;
  mundo: MundoFiltro;
  periodo_vazio?: boolean;
  alerta_atrasados: {
    quantidade: number;
    valor_total: string;
    filtro_drilldown: FiltroDrilldown | null;
  } | null;
  cards: CardDashboard[];
  cards_disponiveis: CardDisponivel[];
  saude_caixa: SaudeCaixa | null;
  fluxo_caixa_mensal: PontoFluxo[];
  evolucao_saldo: PontoSaldo[];
  comparativo_mes: {
    atual: Record<string, string>;
    anterior: Record<string, string>;
  } | null;
  despesas_por_categoria: FatiaCategoria[];
  top_despesas: { lancamento_id: string; descricao: string; valor: string; data: string }[];
  receita_por_servico: {
    servico_id: string;
    nome: string;
    mundo: Mundo;
    valor: string;
    percentual: string | null;
  }[];
  card_clientes: {
    total_recebido: string;
    comparativo: Comparativo;
    clientes_ativos: number;
    top_clientes: { cliente_id: string; nome: string; valor: string }[];
    inadimplentes: {
      cliente_id: string;
      nome: string;
      valor_atrasado: string;
      dias_atraso: number;
    }[];
  } | null;
  card_funcionarios: {
    custo_total: string;
    comparativo: Comparativo;
    percentual_sobre_despesas: string | null;
    por_funcionario: { funcionario_id: string; nome: string; valor: string }[];
    proximos_pagamentos: {
      lancamento_id: string;
      funcionario: string;
      data: string;
      valor: string;
    }[];
  } | null;
  proximos_7_dias: {
    data: string;
    a_pagar: { lancamento_id: string; descricao: string; valor: string; status: StatusLancamento }[];
    a_receber: {
      lancamento_id: string;
      descricao: string;
      valor: string;
      status: StatusLancamento;
    }[];
  }[];
  resumo_linguagem_natural: string;
}

/* ------------------------------------------------------------------ */
/* Extrato — contracts/consultas.md §2                                 */
/* ------------------------------------------------------------------ */

export type Agrupamento = "dia" | "semana" | "mes";

export interface GrupoExtrato {
  rotulo: string;
  inicio: string;
  fim: string;
  /** Grupo futuro: não entra no `saldo_acumulado` (`FR-052`, `RN-05`). */
  previsto: boolean;
  lancamentos: Lancamento[];
  totais: { receitas: string; despesas: string };
  saldo_acumulado: string;
}

export interface Pendencia {
  lancamento_id: string;
  descricao: string;
  valor: string;
  data: string;
  status: StatusLancamento;
  vencido: boolean;
}

export interface Extrato {
  periodo: PeriodoResolvido;
  resumo: {
    total_receitas: string;
    total_despesas: string;
    resultado: string;
    saldo_final: string;
    comparativos: Record<string, Comparativo>;
  };
  grafico: { rotulo: string; receitas: string; despesas: string }[];
  grupos: GrupoExtrato[];
  pendencias: { a_pagar: Pendencia[]; a_receber: Pendencia[] };
}

/* ------------------------------------------------------------------ */
/* Relatórios — contracts/consultas.md §3                              */
/* ------------------------------------------------------------------ */

export interface LinhaDre {
  categoria_id: string;
  nome: string;
  valor: string;
  subcategorias: { nome: string; valor: string }[];
}

export interface Dre {
  periodo: PeriodoResolvido;
  acumulado_ano: {
    receita_bruta: string;
    despesa_total: string;
    resultado: string;
    margem_percentual: string | null;
  };
  receitas: LinhaDre[];
  despesas: LinhaDre[];
  receita_bruta: string;
  despesa_total: string;
  resultado: string;
  margem_percentual: string | null;
  comparativo_periodo_anterior: Record<string, Comparativo>;
  leitura_linguagem_natural: string;
}

export interface RelatorioClientes {
  faturamento_total: string;
  clientes: {
    cliente_id: string;
    nome: string;
    total_recebido: string;
    percentual_faturamento: string | null;
    situacao: SituacaoCliente;
    evolucao_mensal: { mes: string; valor: string }[];
    quebra_por_mundo: QuebraPorMundo;
  }[];
}

export interface RelatorioVariacao {
  meses: string[];
  linhas: {
    categoria_id: string;
    nome: string;
    valores: {
      mes: string;
      valor: string;
      variacao_percentual: string | null;
      destacar: boolean;
    }[];
  }[];
  /** Vem do servidor; o número não aparece no frontend (`FR-092`, `RNF-02`). */
  limiar_destaque_percentual: number;
}

export interface MatrizMensal {
  meses: string[];
  linhas: {
    categoria_id: string;
    nome: string;
    cor: string | null;
    valores: Record<string, string>;
    total: string;
  }[];
  totais_por_mes: Record<string, string>;
}

/* ------------------------------------------------------------------ */
/* Plataforma — contracts/plataforma.md                                */
/* ------------------------------------------------------------------ */

export interface PreferenciaCard {
  id: string;
  visivel: boolean;
  ordem: number;
}

export interface Sessao {
  usuario: { id: string; nome: string; email: string; papel: PapelUsuario };
  /** Booleano explícito, do servidor. Esconder o menu não é autorizar (`RF-02`). */
  permissoes: {
    configuracoes: boolean;
    usuarios: boolean;
    cadastros: boolean;
    lancamentos: boolean;
  };
  preferencias: { tema: Tema; dashboard_cards: PreferenciaCard[] };
  notificacoes_nao_lidas: number;
}

export interface Usuario {
  id: string;
  nome: string;
  email: string;
  papel: PapelUsuario;
  ativo: boolean;
  criado_em?: string;
}

export interface ValorConfiguracao<T = unknown> {
  valor: T;
  /** Texto de ajuda da tela de Configurações — vem do banco (`FR-106`). */
  descricao: string;
}

export type Configuracoes = Record<string, ValorConfiguracao>;

export interface RespostaConfiguracoes {
  atualizadas: string[];
  efeitos?: Record<string, number> | null;
}

export interface Notificacao {
  id: string;
  tipo: TipoNotificacao;
  titulo: string;
  corpo: string;
  mundo: Mundo | null;
  lancamento_id: string | null;
  cliente_id: string | null;
  lida_em: string | null;
  criado_em: string;
}

export interface ListaNotificacoes extends PaginaDe<Notificacao> {
  nao_lidas: number;
}

export interface Saldo {
  saldo: string;
  quebra_por_mundo: QuebraPorMundo;
  calculado_em: string;
}

export interface ResultadoBusca {
  lancamentos: { id: string; descricao: string; valor: string; data: string; mundo: Mundo }[];
  clientes: { id: string; nome: string; empresa: string | null }[];
  categorias: { id: string; nome: string; cor: string | null }[];
}

export interface EstadoRotina {
  ultima_execucao: string | null;
  ultima_data_processada: string | null;
  ultimo_resultado: Record<string, unknown> | null;
}

/* ------------------------------------------------------------------ */
/* Importação — contracts/lancamentos.md §6                            */
/* ------------------------------------------------------------------ */

export interface Importacao {
  importacao_id: string;
  nome_arquivo: string;
  formato: "csv" | "ofx";
  colunas_detectadas: string[];
  expira_em: string;
  previa: Record<string, string>[];
  total_linhas: number;
}

export interface PreviaMapeamento {
  linhas: {
    indice: number;
    data: string | null;
    descricao: string | null;
    valor: string | null;
    tipo: TipoLancamento | null;
    categoria_texto: string | null;
    categoria_sugerida_id: string | null;
    categoria_sugerida_nome: string | null;
    erros: string[];
  }[];
  resumo: {
    total: number;
    validas: number;
    invalidas: number;
    categorias_nao_reconhecidas: {
      texto: string;
      sugestao_id: string | null;
      sugestao_nome: string | null;
    }[];
  };
}

export interface ProgressoImportacao {
  concluida: boolean;
  cursor: string | null;
  gravadas: number;
  total: number;
}
