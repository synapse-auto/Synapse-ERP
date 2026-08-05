"use client";

import {
  // Dinheiro e finanças
  BadgeDollarSign,
  Banknote,
  Calculator,
  ChartColumn,
  ChartLine,
  ChartPie,
  CircleDollarSign,
  Coins,
  CreditCard,
  HandCoins,
  Landmark,
  Percent,
  PiggyBank,
  Receipt,
  TrendingDown,
  TrendingUp,
  Wallet,
  // Pessoas e equipe
  Baby,
  Briefcase,
  Contact,
  GraduationCap,
  Handshake,
  HeartHandshake,
  IdCard,
  UserPlus,
  UserRound,
  Users,
  // Tecnologia e infraestrutura
  Antenna,
  Bug,
  Cable,
  Cloud,
  Code,
  Cpu,
  Database,
  Globe,
  HardDrive,
  Key,
  Laptop,
  Lock,
  Monitor,
  Network,
  Printer,
  Router,
  SatelliteDish,
  Server,
  Shield,
  Smartphone,
  Terminal,
  Usb,
  Wifi,
  // Obra, energia e clima
  AirVent,
  BatteryCharging,
  Building,
  Camera,
  Cctv,
  Construction,
  Drill,
  Fan,
  Factory,
  Hammer,
  HardHat,
  Lightbulb,
  Plug,
  PlugZap,
  Ruler,
  Snowflake,
  Sun,
  Thermometer,
  Warehouse,
  Wrench,
  Zap,
  // Marketing e vendas
  Gift,
  Image,
  Mail,
  Megaphone,
  MessageCircle,
  Palette,
  PenTool,
  Rocket,
  Share2,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Speaker,
  Store,
  Tag,
  Tags,
  Target,
  ThumbsUp,
  Video,
  // Transporte e logística
  Bike,
  Boxes,
  Car,
  Forklift,
  Fuel,
  MapPin,
  Package,
  Plane,
  Route,
  Ship,
  TrainFront,
  Truck,
  // Documentos e escritório
  Archive,
  BookOpen,
  Calendar,
  ClipboardList,
  Clock,
  FileText,
  Folder,
  Paperclip,
  Pencil,
  Scale,
  Signature,
  Stamp,
  // Gerais
  Bookmark,
  Box,
  Circle,
  Coffee,
  Droplet,
  Dumbbell,
  Ellipsis,
  Flag,
  Flame,
  Heart,
  House,
  Layers,
  Leaf,
  Pill,
  Puzzle,
  Recycle,
  Settings,
  Star,
  Trophy,
  Utensils,
  Wind,
  type LucideIcon,
} from "lucide-react";

/**
 * Catálogo de ícones de categoria (`FR-072`).
 *
 * O banco guarda **o nome do ícone Lucide** em `categorias.icone`
 * (`migracoes/003_cadastros.sql`, `text not null`) — nunca um SVG. Este arquivo
 * é a única ponte entre esse nome e o componente que desenha, nos dois sentidos:
 * o seletor lê a lista daqui e a tela resolve o nome daqui.
 *
 * ## Pesquisa antes de escrever (Princípio II)
 *
 * - shadcn/ui **não tem** icon picker oficial — nada a instalar.
 * - `alan-crts/shadcn-iconpicker` (github) resolve o caso geral: os ~1600 ícones
 *   do Lucide, busca difusa e virtualização com TanStack Virtual. Descartado por
 *   tamanho: exige uma dependência nova e carrega o pacote inteiro de ícones
 *   para escolher entre nove categorias. Também é em inglês, e a interface aqui
 *   é 100% PT-BR.
 * - O que ficou: `Popover` + `Input` do shadcn, **já no projeto**, sobre esta
 *   lista curada. Cada ícone entra por `import` nomeado, então o bundle leva só
 *   os 135 — não os 1600.
 *
 * ## Por que uma lista no código e não em `configuracoes`
 *
 * `RNF-02` proíbe hardcodear **dado editável** — rótulo de card, cor, limite,
 * prazo. Aqui o que está fixo é o inverso: o vocabulário de componentes que o
 * bundle sabe desenhar. Um nome numa tabela não vira SVG sem um `import`
 * correspondente, e importar por nome dinâmico é justamente o que o descarte
 * acima evita. A **escolha** continua sendo dado: mora em `categorias.icone`,
 * editável pelo gestor pela tela, sem deploy.
 *
 * ## O rótulo é em português
 *
 * Os nomes do Lucide são em inglês (`sun`, `air-vent`, `hard-hat`). Quem cadastra
 * digita "solar", "ar condicionado", "obra" — então cada ícone carrega um rótulo
 * PT-BR, e a busca do seletor casa com o rótulo **e** com o nome técnico.
 */

export interface IconeDoCatalogo {
  /** Nome Lucide em kebab-case — o que vai para `categorias.icone`. */
  nome: string;
  /** Rótulo PT-BR mostrado e pesquisado. */
  rotulo: string;
  Componente: LucideIcon;
}

export interface GrupoDeIcones {
  rotulo: string;
  itens: IconeDoCatalogo[];
}

/** Usado quando a categoria não tem ícone ou tem um nome fora do catálogo. */
export const ICONE_PADRAO = "tag";

export const CATALOGO_ICONES: GrupoDeIcones[] = [
  {
    rotulo: "Dinheiro e finanças",
    itens: [
      { nome: "wallet", rotulo: "Carteira", Componente: Wallet },
      { nome: "banknote", rotulo: "Nota", Componente: Banknote },
      { nome: "coins", rotulo: "Moedas", Componente: Coins },
      { nome: "circle-dollar-sign", rotulo: "Valor", Componente: CircleDollarSign },
      { nome: "badge-dollar-sign", rotulo: "Selo de valor", Componente: BadgeDollarSign },
      { nome: "credit-card", rotulo: "Cartão", Componente: CreditCard },
      { nome: "piggy-bank", rotulo: "Reserva", Componente: PiggyBank },
      { nome: "receipt", rotulo: "Recibo", Componente: Receipt },
      { nome: "landmark", rotulo: "Imposto", Componente: Landmark },
      { nome: "calculator", rotulo: "Calculadora", Componente: Calculator },
      { nome: "percent", rotulo: "Percentual", Componente: Percent },
      { nome: "hand-coins", rotulo: "Pagamento", Componente: HandCoins },
      { nome: "chart-line", rotulo: "Gráfico de linha", Componente: ChartLine },
      { nome: "chart-column", rotulo: "Gráfico de barras", Componente: ChartColumn },
      { nome: "chart-pie", rotulo: "Gráfico de pizza", Componente: ChartPie },
      { nome: "trending-up", rotulo: "Em alta", Componente: TrendingUp },
      { nome: "trending-down", rotulo: "Em queda", Componente: TrendingDown },
    ],
  },
  {
    rotulo: "Pessoas e equipe",
    itens: [
      { nome: "users", rotulo: "Clientes", Componente: Users },
      { nome: "user-round", rotulo: "Pessoa", Componente: UserRound },
      { nome: "user-plus", rotulo: "Novo cadastro", Componente: UserPlus },
      { nome: "briefcase", rotulo: "Funcionários", Componente: Briefcase },
      { nome: "handshake", rotulo: "Parceria", Componente: Handshake },
      { nome: "heart-handshake", rotulo: "Apoio", Componente: HeartHandshake },
      { nome: "id-card", rotulo: "Crachá", Componente: IdCard },
      { nome: "contact", rotulo: "Contato", Componente: Contact },
      { nome: "graduation-cap", rotulo: "Treinamento", Componente: GraduationCap },
      { nome: "baby", rotulo: "Dependente", Componente: Baby },
    ],
  },
  {
    rotulo: "Tecnologia e infraestrutura",
    itens: [
      { nome: "server", rotulo: "Servidor", Componente: Server },
      { nome: "database", rotulo: "Banco de dados", Componente: Database },
      { nome: "cloud", rotulo: "Nuvem", Componente: Cloud },
      { nome: "network", rotulo: "Rede", Componente: Network },
      { nome: "wifi", rotulo: "Wi-Fi", Componente: Wifi },
      { nome: "router", rotulo: "Roteador", Componente: Router },
      { nome: "cable", rotulo: "Cabeamento", Componente: Cable },
      { nome: "antenna", rotulo: "Antena", Componente: Antenna },
      { nome: "satellite-dish", rotulo: "Antena parabólica", Componente: SatelliteDish },
      { nome: "cpu", rotulo: "Processador", Componente: Cpu },
      { nome: "hard-drive", rotulo: "Disco", Componente: HardDrive },
      { nome: "usb", rotulo: "Pendrive", Componente: Usb },
      { nome: "monitor", rotulo: "Monitor", Componente: Monitor },
      { nome: "laptop", rotulo: "Notebook", Componente: Laptop },
      { nome: "smartphone", rotulo: "Celular", Componente: Smartphone },
      { nome: "printer", rotulo: "Impressora", Componente: Printer },
      { nome: "code", rotulo: "Código", Componente: Code },
      { nome: "terminal", rotulo: "Terminal", Componente: Terminal },
      { nome: "bug", rotulo: "Correção", Componente: Bug },
      { nome: "globe", rotulo: "Internet", Componente: Globe },
      { nome: "shield", rotulo: "Segurança", Componente: Shield },
      { nome: "lock", rotulo: "Bloqueio", Componente: Lock },
      { nome: "key", rotulo: "Licença", Componente: Key },
    ],
  },
  {
    rotulo: "Obra, energia e clima",
    itens: [
      { nome: "wrench", rotulo: "Ferramenta", Componente: Wrench },
      { nome: "hammer", rotulo: "Martelo", Componente: Hammer },
      { nome: "drill", rotulo: "Furadeira", Componente: Drill },
      { nome: "ruler", rotulo: "Medição", Componente: Ruler },
      { nome: "hard-hat", rotulo: "Obra", Componente: HardHat },
      { nome: "construction", rotulo: "Instalação", Componente: Construction },
      { nome: "lightbulb", rotulo: "Iluminação e LED", Componente: Lightbulb },
      { nome: "sun", rotulo: "Energia solar", Componente: Sun },
      { nome: "zap", rotulo: "Energia", Componente: Zap },
      { nome: "plug", rotulo: "Tomada", Componente: Plug },
      { nome: "plug-zap", rotulo: "Elétrica", Componente: PlugZap },
      { nome: "battery-charging", rotulo: "Bateria", Componente: BatteryCharging },
      { nome: "air-vent", rotulo: "Ar condicionado", Componente: AirVent },
      { nome: "fan", rotulo: "Ventilação", Componente: Fan },
      { nome: "snowflake", rotulo: "Refrigeração", Componente: Snowflake },
      { nome: "thermometer", rotulo: "Temperatura", Componente: Thermometer },
      { nome: "camera", rotulo: "Câmera", Componente: Camera },
      { nome: "cctv", rotulo: "Monitoramento", Componente: Cctv },
      { nome: "building", rotulo: "Prédio", Componente: Building },
      { nome: "warehouse", rotulo: "Galpão", Componente: Warehouse },
      { nome: "factory", rotulo: "Indústria", Componente: Factory },
    ],
  },
  {
    rotulo: "Marketing e vendas",
    itens: [
      { nome: "megaphone", rotulo: "Divulgação", Componente: Megaphone },
      { nome: "target", rotulo: "Meta", Componente: Target },
      { nome: "rocket", rotulo: "Lançamento", Componente: Rocket },
      { nome: "sparkles", rotulo: "Destaque", Componente: Sparkles },
      { nome: "speaker", rotulo: "Som", Componente: Speaker },
      { nome: "gift", rotulo: "Brinde", Componente: Gift },
      { nome: "tag", rotulo: "Etiqueta", Componente: Tag },
      { nome: "tags", rotulo: "Etiquetas", Componente: Tags },
      { nome: "shopping-cart", rotulo: "Carrinho", Componente: ShoppingCart },
      { nome: "shopping-bag", rotulo: "Compra", Componente: ShoppingBag },
      { nome: "store", rotulo: "Loja", Componente: Store },
      { nome: "mail", rotulo: "E-mail", Componente: Mail },
      { nome: "message-circle", rotulo: "Mensagem", Componente: MessageCircle },
      { nome: "share-2", rotulo: "Compartilhamento", Componente: Share2 },
      { nome: "thumbs-up", rotulo: "Aprovação", Componente: ThumbsUp },
      { nome: "palette", rotulo: "Design", Componente: Palette },
      { nome: "pen-tool", rotulo: "Criação", Componente: PenTool },
      { nome: "image", rotulo: "Imagem", Componente: Image },
      { nome: "video", rotulo: "Vídeo", Componente: Video },
    ],
  },
  {
    rotulo: "Transporte e logística",
    itens: [
      { nome: "truck", rotulo: "Caminhão", Componente: Truck },
      { nome: "car", rotulo: "Carro", Componente: Car },
      { nome: "bike", rotulo: "Bicicleta", Componente: Bike },
      { nome: "plane", rotulo: "Avião", Componente: Plane },
      { nome: "ship", rotulo: "Navio", Componente: Ship },
      { nome: "train-front", rotulo: "Trem", Componente: TrainFront },
      { nome: "fuel", rotulo: "Combustível", Componente: Fuel },
      { nome: "route", rotulo: "Rota", Componente: Route },
      { nome: "map-pin", rotulo: "Local", Componente: MapPin },
      { nome: "package", rotulo: "Encomenda", Componente: Package },
      { nome: "boxes", rotulo: "Estoque", Componente: Boxes },
      { nome: "forklift", rotulo: "Empilhadeira", Componente: Forklift },
    ],
  },
  {
    rotulo: "Documentos e escritório",
    itens: [
      { nome: "file-text", rotulo: "Documento", Componente: FileText },
      { nome: "folder", rotulo: "Pasta", Componente: Folder },
      { nome: "clipboard-list", rotulo: "Checklist", Componente: ClipboardList },
      { nome: "book-open", rotulo: "Manual", Componente: BookOpen },
      { nome: "calendar", rotulo: "Agenda", Componente: Calendar },
      { nome: "clock", rotulo: "Hora", Componente: Clock },
      { nome: "pencil", rotulo: "Anotação", Componente: Pencil },
      { nome: "paperclip", rotulo: "Anexo", Componente: Paperclip },
      { nome: "archive", rotulo: "Arquivo", Componente: Archive },
      { nome: "scale", rotulo: "Jurídico", Componente: Scale },
      { nome: "stamp", rotulo: "Carimbo", Componente: Stamp },
      { nome: "signature", rotulo: "Assinatura", Componente: Signature },
    ],
  },
  {
    rotulo: "Gerais",
    itens: [
      { nome: "ellipsis", rotulo: "Outros", Componente: Ellipsis },
      { nome: "circle", rotulo: "Círculo", Componente: Circle },
      { nome: "star", rotulo: "Favorito", Componente: Star },
      { nome: "flag", rotulo: "Bandeira", Componente: Flag },
      { nome: "bookmark", rotulo: "Marcador", Componente: Bookmark },
      { nome: "layers", rotulo: "Camadas", Componente: Layers },
      { nome: "box", rotulo: "Caixa", Componente: Box },
      { nome: "puzzle", rotulo: "Peça", Componente: Puzzle },
      { nome: "settings", rotulo: "Ajustes", Componente: Settings },
      { nome: "house", rotulo: "Casa", Componente: House },
      { nome: "coffee", rotulo: "Café", Componente: Coffee },
      { nome: "utensils", rotulo: "Alimentação", Componente: Utensils },
      { nome: "heart", rotulo: "Saúde", Componente: Heart },
      { nome: "pill", rotulo: "Medicamento", Componente: Pill },
      { nome: "dumbbell", rotulo: "Academia", Componente: Dumbbell },
      { nome: "trophy", rotulo: "Prêmio", Componente: Trophy },
      { nome: "leaf", rotulo: "Sustentável", Componente: Leaf },
      { nome: "recycle", rotulo: "Reciclagem", Componente: Recycle },
      { nome: "wind", rotulo: "Vento", Componente: Wind },
      { nome: "droplet", rotulo: "Água", Componente: Droplet },
      { nome: "flame", rotulo: "Fogo", Componente: Flame },
    ],
  },
];

const POR_NOME = new Map<string, IconeDoCatalogo>(
  CATALOGO_ICONES.flatMap((grupo) => grupo.itens).map((item) => [item.nome, item]),
);

/** Total do catálogo — o seletor mostra na dica de busca vazia. */
export const QUANTIDADE_DE_ICONES = POR_NOME.size;

/**
 * Resolve o nome guardado no banco. Nome desconhecido **não quebra a tela**:
 * cai no ícone padrão, porque o banco aceita qualquer texto (a coluna é `text`)
 * e um `undefined` renderizado derrubaria a lista inteira.
 */
export function iconeDoCatalogo(nome: string | null | undefined): IconeDoCatalogo {
  return (nome ? POR_NOME.get(nome) : undefined) ?? POR_NOME.get(ICONE_PADRAO)!;
}

export function rotuloDoIcone(nome: string | null | undefined): string {
  return iconeDoCatalogo(nome).rotulo;
}

/** Busca por rótulo PT-BR **ou** nome Lucide, sem acento e sem caixa. */
export function filtraIcones(termo: string): GrupoDeIcones[] {
  const limpo = semAcento(termo.trim());
  if (!limpo) return CATALOGO_ICONES;
  return CATALOGO_ICONES.map((grupo) => ({
    rotulo: grupo.rotulo,
    itens: grupo.itens.filter(
      (item) => semAcento(item.rotulo).includes(limpo) || item.nome.includes(limpo),
    ),
  })).filter((grupo) => grupo.itens.length > 0);
}

// `NFD` separa "ç" em "c" + cedilha; `\p{Diacritic}` remove o que sobrou. Sem isto,
// procurar "cafe" não acha "Café" e "eletrica" não acha "Elétrica".
const semAcento = (texto: string) =>
  texto
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

/**
 * Desenha o ícone da categoria. `nome` é o que veio da API.
 *
 * `aria-hidden` de propósito: o nome da categoria está do lado em texto, e o
 * ícone repetido em leitor de tela é ruído.
 */
export function IconeDaCategoria({
  nome,
  tamanho = 16,
  className,
}: {
  nome: string | null | undefined;
  tamanho?: number;
  className?: string;
}) {
  const { Componente } = iconeDoCatalogo(nome);
  return <Componente size={tamanho} className={className} aria-hidden strokeWidth={1.9} />;
}
