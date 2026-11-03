// Acesso ao servidor local. Dinheiro sempre em centavos (inteiros).

export type Conta = {
  id: number; nome: string; instituicao_id: number | null; tipo: string;
  saldo_inicial_centavos: number; data_saldo_inicial: string; cor: string;
  compoe_saldo_disponivel: number; ativa: number;
};
export type Cartao = {
  id: number; nome: string; instituicao_id: number | null; bandeira: string; final: string;
  limite_centavos: number; dia_fechamento: number; dia_vencimento: number;
  conta_pagamento_id: number | null; cor: string; ativo: number;
};
export type Categoria = {
  id: number; nome: string; tipo: "receita" | "despesa"; pai_id: number | null; cor: string;
  fixa: number;
};
export type Tag = { id: number; nome: string; cor: string };
export type Instituicao = { id: number; nome: string; codigo: string | null };
export type Transacao = {
  id: number; tipo: string; descricao: string; valor_centavos: number; data: string; pago: number;
  conta_id: number | null; cartao_id: number | null; categoria: string | null; conta: string | null;
  cartao: string | null; tags: string | null; itens: number; entrada: number;
  ajuste_negativo: number; parcela: number | null; total_parcelas: number | null;
  categoria_id: number | null; observacao: string | null; conferido: number;
  recorrencia_id: string | null; vencimento: string | null; fixa: number; tem_ficha: number;
};
export type TipoFicha = "energia" | "energia_solar" | "agua" | "internet" | "telefone" | "saude" | "outra";
export type Ficha = {
  transacao_id: number; gravada: boolean; tipo: TipoFicha | null; referencia: string | null;
  consumo: number | null; kwh_compensado: number | null; bandeira: string | null;
  bandeira_centavos: number | null; multa_juros_centavos: number | null; vidas: number | null;
  observacao: string | null; cip_centavos: number | null; terceiros_centavos: number | null;
  arquivo: string | null; desconto_centavos: number | null;
};
export type APagar = {
  id: number; tipo: "receita" | "despesa"; descricao: string; valor_centavos: number; data: string;
  conta_id: number | null; conta: string | null; categoria: string | null; recorrencia_id: string | null;
};
export type LancamentoFatura = {
  id: number; tipo: string; descricao: string; valor_centavos: number; data: string;
  categoria_id: number | null; categoria: string | null; parcela: number | null;
  total_parcelas: number | null; conferido: number; observacao: string | null;
  conta_id: number | null; conta: string | null; itens: number;
};
export type Fatura = {
  cartao: { id: number; nome: string; final: string; bandeira: string; conta_pagamento_id: number | null };
  competencia: string; fatura_id: number | null; data_fechamento: string; data_vencimento: string;
  total: number; pago: number; a_pagar: number; conferido: number;
  situacao: "sem lançamentos" | "aberta" | "fechada" | "paga";
  valor_banco: number | null; diferenca_banco: number | null;
  lancamentos: LancamentoFatura[]; pagamentos: LancamentoFatura[];
};
export type Fatia = { categoria_id: number; categoria: string; cor: string; total: number };
export type SaldoConta = {
  id: number; nome: string; tipo: string; cor: string; compoe_saldo_disponivel: number;
  saldo_atual: number; saldo_previsto: number;
};
export type CartaoPainel = {
  id: number; nome: string; bandeira: string; final: string; cor: string; limite_centavos: number;
  data_vencimento: string | null; fatura_total: number; fatura_paga: number; em_aberto: number;
  limite_disponivel: number; fatura_situacao: "sem fatura" | "paga" | "aberta";
};
export type Painel = {
  competencia: string; saldo_disponivel: number; patrimonio: number; receitas: number;
  despesas: number; cartoes_fatura_mes: number;
  pendencias: { despesas: number; receitas: number };
  contas: SaldoConta[]; cartoes: CartaoPainel[];
  receitas_por_categoria: Fatia[]; despesas_por_categoria: Fatia[];
  fixas_variaveis: { fixas: number; variaveis: number };
};
export type MesEnergia = {
  referencia: string; consumo: number | null; kwh_compensado: number | null;
  escelsa_centavos: number; solar_centavos: number; total_centavos: number;
  fixos_centavos: number; seguro_centavos: number; bandeira: string | null; bandeira_centavos: number;
  multa_centavos: number; economia_centavos: number; dias_atraso: number;
  custo_kwh: number | null; custo_kwh_energia: number | null; consumo_ano_anterior: number | null;
  completo: boolean;
};
export type PainelEnergia = {
  meses: MesEnergia[];
  historico: { referencia: string; consumo: number }[];
  resumo: {
    meses: number; total_centavos: number; consumo: number; custo_kwh: number | null;
    custo_kwh_energia: number | null; economia_solar_centavos: number; fixos_centavos: number;
    seguro_centavos: number; bandeira_centavos: number; multa_centavos: number;
    meses_com_atraso: number; variacao_consumo_pct: number | null; meses_comparados: number;
  };
};
export type MesAgua = {
  referencia: string; consumo: number | null; total_centavos: number; fixo_centavos: number;
  variavel_centavos: number; multa_centavos: number; custo_m3: number | null; variavel_m3: number | null;
  consumo_ano_anterior: number | null; pago_com_atraso: boolean;
};
export type PainelAgua = {
  meses: MesAgua[];
  resumo: { meses: number; total_centavos: number; consumo: number; custo_m3: number | null;
    fixo_centavos: number; multa_centavos: number; variacao_consumo_pct: number | null; meses_comparados: number };
};
export type EventoPlano = {
  referencia: string; antes_centavos: number; depois_centavos: number; percentual: number;
  diferenca_mes_centavos: number; tipo: "anual" | "faixa_etaria" | "desconhecido"; quem: string[];
  detalhe: { beneficiario: string; item: string; antes_centavos: number; depois_centavos: number; percentual: number }[];
  teto_ans?: { ciclo_inicio: string; percentual: number; fonte: string | null } | null;
  comparacao?: { indice: string; percentual: number | null; periodo: string }[];
  acima_do_teto?: boolean;
};
export type PainelPlano = {
  meses: { referencia: string; total_centavos: number; vidas: number | null;
    itens: { beneficiario: string; item: string; valor_centavos: number }[] }[];
  eventos: EventoPlano[];
  indices_ate: Record<string, string | null>;
};
export type CompraPreco = { data: string; loja: string; preco_centavos: number; qtd_milesimos: number };
export type ProdutoPreco = {
  nome: string; unidade: string; compras: number; lojas: number;
  categoria: string | null; categoria_mae: string | null;
  preco_atual_centavos: number; data_atual: string; loja_atual: string;
  preco_anterior_centavos: number | null; data_anterior: string | null; variacao_pct: number | null;
  menor_centavos: number; menor_loja: string; menor_data: string; maior_centavos: number;
  media_centavos: number; melhor_loja: string | null;
  por_loja: { loja: string; preco_centavos: number; data: string }[];
  serie: CompraPreco[];
};
export type GrupoPreco = { categoria: string; categoria_mae: string | null; produtos: ProdutoPreco[] };
export type PainelPrecos = {
  grupos: GrupoPreco[];
  resumo: { produtos: number; compras: number; lojas: number; com_historico: number;
    subindo: number; caindo: number };
};
export type Saude = {
  ok: boolean; banco: string; leitura_ia_configurada: boolean;
  ultimo_backup: { arquivo: string; criado_em: string; copiado_drive: number } | null;
};

async function chamar<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  const ehArquivo = opcoes?.body instanceof FormData;   // upload: o navegador define o cabeçalho
  const r = await fetch(caminho, {
    headers: ehArquivo ? undefined : { "Content-Type": "application/json" },
    ...opcoes,
  });
  // Página HTML no lugar de dados: é o servidor antigo, ligado antes da atualização.
  if (caminho.startsWith("/api/") && (r.headers.get("content-type") ?? "").includes("text/html"))
    throw new Error("O servidor que está ligado é de uma versão anterior. "
      + "Rode scripts\\parar.bat e abra o app de novo pelo atalho.");
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}));
    const detalhe = corpo.detail;
    throw new Error(
      typeof detalhe === "string" ? detalhe
        : Array.isArray(detalhe) ? detalhe.map((d: { msg: string }) => d.msg).join("; ")
        : `Erro ${r.status}`,
    );
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

const enviar = (metodo: string, dados: unknown): RequestInit =>
  ({ method: metodo, body: JSON.stringify(dados) });

export type ItemCupom = {
  seq: number; descricao: string; codigo: string | null; quantidade_milesimos: number;
  unidade: string; preco_unitario_centavos: number; valor_total_centavos: number;
  desconto_centavos: number; categoria_sugerida?: number | null;
};
export type Cupom = {
  origem: string; tipo_documento: string; chave: string | null;
  emitente: { nome: string; cnpj: string | null; cidade: string | null; uf: string | null };
  numero: string | null; serie: string | null; emissao: string | null; itens: ItemCupom[];
  valor_total_centavos: number; desconto_centavos: number; valor_pagar_centavos: number;
};
export type CupomLido = {
  arquivo: string; cupom: Cupom;
  conferencia: { liquido_itens: number; valor_pagar: number; diferenca: number; confere: boolean };
  ja_lancado: { id: number; transacao_id: number | null; data: string | null; so_precos?: number } | null;
  despesa_parecida: { id: number; descricao: string; data: string; valor_centavos: number; onde: string | null } | null;
  pagamento_sugerido: { conta_id: number | null; cartao_id: number | null } | null;
};
export type NotaQR = { chave: string; numero: number; cnpj: string; valida: boolean; url_consulta: string | null };

const comArquivo = (arquivo: File): RequestInit => {
  const f = new FormData();
  f.append("arquivo", arquivo);
  return { method: "POST", body: f };
};

export const api = {
  lerQR: (arquivo: File) => chamar<{ notas: NotaQR[] }>("/api/nfce/qr", comArquivo(arquivo)),
  lerCupom: (arquivo: File) => chamar<CupomLido>("/api/cupons/ler", comArquivo(arquivo)),
  lancarCupom: (d: Record<string, unknown>) =>
    chamar<{ transacao_id: number | null; valor_centavos: number; itens: number; so_precos: boolean }>(
      "/api/cupons/lancar", enviar("POST", d)),
  saude: () => chamar<Saude>("/api/saude"),
  painel: (comp: string) => chamar<Painel>(`/api/dashboard?competencia=${comp}`),
  energia: (meses = 12) => chamar<PainelEnergia>(`/api/painel/energia?meses=${meses}`),
  agua: (meses = 12) => chamar<PainelAgua>(`/api/painel/agua?meses=${meses}`),
  plano: () => chamar<PainelPlano>("/api/painel/plano"),
  precos: (meses = 24) => chamar<PainelPrecos>(`/api/painel/precos?meses=${meses}`),
  atualizarIndices: () =>
    chamar<Record<string, { meses?: number; ultimo?: string | null; erro?: string }>>("/api/indices/atualizar", { method: "POST" }),
  instituicoes: () => chamar<Instituicao[]>("/api/instituicoes"),
  contas: () => chamar<Conta[]>("/api/contas"),
  salvarConta: (d: Partial<Conta>, id?: number) =>
    chamar<Conta>(id ? `/api/contas/${id}` : "/api/contas", enviar(id ? "PUT" : "POST", d)),
  reajustarSaldo: (id: number, saldo_centavos: number, data: string, no_saldo_inicial: boolean) =>
    chamar<{ diferenca: number }>(`/api/contas/${id}/reajuste`,
      enviar("POST", { saldo_centavos, data, no_saldo_inicial })),
  cartoes: () => chamar<Cartao[]>("/api/cartoes"),
  salvarCartao: (d: Partial<Cartao>, id?: number) =>
    chamar<Cartao>(id ? `/api/cartoes/${id}` : "/api/cartoes", enviar(id ? "PUT" : "POST", d)),
  categorias: () => chamar<Categoria[]>("/api/categorias"),
  criarCategoria: (d: Partial<Categoria>) => chamar<Categoria>("/api/categorias", enviar("POST", d)),
  editarCategoria: (id: number, d: { fixa: boolean }) =>
    chamar<Categoria>(`/api/categorias/${id}`, enviar("PATCH", d)),
  tags: () => chamar<Tag[]>("/api/tags"),
  criarTag: (d: Partial<Tag>) => chamar<Tag>("/api/tags", enviar("POST", d)),
  transacoes: (comp: string) => chamar<Transacao[]>(`/api/transacoes?competencia=${comp}`),
  criarTransacao: (d: Record<string, unknown>) =>
    chamar<Transacao[]>("/api/transacoes", enviar("POST", d)),
  editarTransacao: (id: number, d: Record<string, unknown>) =>
    chamar<Transacao>(`/api/transacoes/${id}`, enviar("PATCH", d)),
  fatura: (cartao: number, comp: string) =>
    chamar<Fatura>(`/api/cartoes/${cartao}/fatura?competencia=${comp}`),
  valorBanco: (cartao: number, comp: string, valor_centavos: number | null) =>
    chamar<Fatura>(`/api/cartoes/${cartao}/fatura/${comp}/valor-banco`, enviar("PUT", { valor_centavos })),
  apagarTransacao: (id: number, proximas = false) =>
    chamar<void>(`/api/transacoes/${id}${proximas ? "?proximas=true" : ""}`, { method: "DELETE" }),
  ficha: (id: number) => chamar<Ficha>(`/api/transacoes/${id}/ficha`),
  gravarFicha: (id: number, d: Record<string, unknown>) =>
    chamar<Ficha>(`/api/transacoes/${id}/ficha`, enviar("PUT", d)),
  apagarFicha: (id: number) => chamar<void>(`/api/transacoes/${id}/ficha`, { method: "DELETE" }),
  aPagar: (dias = 30) => chamar<APagar[]>(`/api/a-pagar?dias=${dias}`),
  backup: () => chamar<{ arquivo: string; copiado_drive: boolean }>("/api/backup", { method: "POST" }),
};
