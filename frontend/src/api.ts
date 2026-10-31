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
};
export type Tag = { id: number; nome: string; cor: string };
export type Instituicao = { id: number; nome: string; codigo: string | null };
export type Transacao = {
  id: number; tipo: string; descricao: string; valor_centavos: number; data: string; pago: number;
  conta_id: number | null; cartao_id: number | null; categoria: string | null; conta: string | null;
  cartao: string | null; tags: string | null; itens: number; entrada: number;
  ajuste_negativo: number; parcela: number | null; total_parcelas: number | null;
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
};
export type Saude = {
  ok: boolean; banco: string; leitura_ia_configurada: boolean;
  ultimo_backup: { arquivo: string; criado_em: string; copiado_drive: number } | null;
};

async function chamar<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  const r = await fetch(caminho, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
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

export const api = {
  saude: () => chamar<Saude>("/api/saude"),
  painel: (comp: string) => chamar<Painel>(`/api/dashboard?competencia=${comp}`),
  instituicoes: () => chamar<Instituicao[]>("/api/instituicoes"),
  contas: () => chamar<Conta[]>("/api/contas"),
  salvarConta: (d: Partial<Conta>, id?: number) =>
    chamar<Conta>(id ? `/api/contas/${id}` : "/api/contas", enviar(id ? "PUT" : "POST", d)),
  cartoes: () => chamar<Cartao[]>("/api/cartoes"),
  salvarCartao: (d: Partial<Cartao>, id?: number) =>
    chamar<Cartao>(id ? `/api/cartoes/${id}` : "/api/cartoes", enviar(id ? "PUT" : "POST", d)),
  categorias: () => chamar<Categoria[]>("/api/categorias"),
  criarCategoria: (d: Partial<Categoria>) => chamar<Categoria>("/api/categorias", enviar("POST", d)),
  tags: () => chamar<Tag[]>("/api/tags"),
  criarTag: (d: Partial<Tag>) => chamar<Tag>("/api/tags", enviar("POST", d)),
  transacoes: (comp: string) => chamar<Transacao[]>(`/api/transacoes?competencia=${comp}`),
  criarTransacao: (d: Record<string, unknown>) =>
    chamar<Transacao[]>("/api/transacoes", enviar("POST", d)),
  apagarTransacao: (id: number) => chamar<void>(`/api/transacoes/${id}`, { method: "DELETE" }),
  backup: () => chamar<{ arquivo: string; copiado_drive: boolean }>("/api/backup", { method: "POST" }),
};
