import { useState } from "react";
import { api } from "../api";
import { nomeMes, paraCentavos, somarMes } from "../formato";
import Modal from "./Modal";
import SeletorCategoria from "./SeletorCategoria";
import { useDados } from "./useDados";

/** O mínimo que a edição precisa saber de um lançamento (vale para a lista e para a fatura). */
export type Editavel = {
  id: number; tipo: string; descricao: string; valor_centavos: number; data: string;
  conta_id: number | null; cartao_id?: number | null; categoria_id: number | null;
  observacao: string | null; itens: number; conferido: number; parcela: number | null;
};

/**
 * Corrige um lançamento já feito. Numa despesa à vista dá para trocar a forma de
 * pagamento (conta <-> cartão); numa compra no cartão, mover para outra fatura.
 */
export default function EditarTransacao({ transacao: t, competenciaFatura, aoFechar, aoSalvar }: {
  transacao: Editavel; competenciaFatura?: string; aoFechar: () => void; aoSalvar: () => void;
}) {
  const contas = useDados(api.contas).dados?.filter((c) => c.ativa) ?? [];
  const cartoes = useDados(api.cartoes).dados?.filter((c) => c.ativo) ?? [];
  const categorias = useDados(api.categorias).dados ?? [];
  const ehCompra = t.tipo === "despesa" || t.tipo === "despesa_cartao";
  const trocaPagamento = ehCompra && t.parcela === null;     // parcelada fica presa ao cartão
  const noCartao = t.tipo === "despesa_cartao" || t.tipo === "credito_cartao";
  const usaCategoria = (ehCompra || t.tipo === "receita" || t.tipo === "credito_cartao") && !t.itens;
  const usaConta = !noCartao && t.tipo !== "transferencia";

  const [f, setF] = useState({
    descricao: t.descricao, valor: (t.valor_centavos / 100).toFixed(2).replace(".", ","), data: t.data,
    pagoCom: noCartao ? `cartao:${t.cartao_id}` : `conta:${t.conta_id}`,
    categoria_id: t.categoria_id ? String(t.categoria_id) : "", observacao: t.observacao ?? "",
    conferido: !!t.conferido, fatura: competenciaFatura ?? "",
  });
  const [erro, setErro] = useState<string | null>(null);
  const muda = (campo: keyof typeof f, valor: unknown) => setF({ ...f, [campo]: valor });
  const viraCartao = f.pagoCom.startsWith("cartao:");

  async function salvar() {
    const valor = paraCentavos(f.valor);
    if (!valor) return setErro("Valor inválido.");
    const d: Record<string, unknown> = { descricao: f.descricao, data: f.data, observacao: f.observacao || null };
    if (!t.itens) d.valor_centavos = valor;
    if (usaCategoria && f.categoria_id) d.categoria_id = Number(f.categoria_id);
    const [qual, id] = f.pagoCom.split(":");
    if (trocaPagamento) d[qual === "cartao" ? "cartao_id" : "conta_id"] = Number(id);
    else if (usaConta) d.conta_id = Number(id);
    if (noCartao) {
      d.conferido = f.conferido;
      if (f.fatura && f.fatura !== competenciaFatura) d.fatura_competencia = f.fatura;
    }
    try { await api.editarTransacao(t.id, d); aoSalvar(); }
    catch (e) { setErro((e as Error).message); }
  }

  return (
    <Modal titulo={t.tipo === "credito_cartao" ? "Editar crédito na fatura" : "Editar lançamento"} aoFechar={aoFechar}>
      <div className="form">
        <label>Descrição<input value={f.descricao} onChange={(e) => muda("descricao", e.target.value)} autoFocus /></label>
        <div className="duas">
          <label>Valor (R$)<input value={f.valor} inputMode="decimal" disabled={!!t.itens}
            onChange={(e) => muda("valor", e.target.value)} /></label>
          <label>{t.tipo === "despesa_cartao" ? "Data da compra" : "Data"}
            <input type="date" value={f.data} onChange={(e) => muda("data", e.target.value)} /></label>
        </div>
        {t.itens > 0 && <p className="dica">O valor e as categorias vêm dos {t.itens} itens do cupom.</p>}
        {(trocaPagamento || usaConta) && (
          <label>{trocaPagamento ? "Pago com" : "Conta"}
            <select value={f.pagoCom} onChange={(e) => muda("pagoCom", e.target.value)}>
              <optgroup label="Contas">{contas.map((c) => <option key={c.id} value={`conta:${c.id}`}>{c.nome}</option>)}</optgroup>
              {trocaPagamento && cartoes.length > 0 && (
                <optgroup label="Cartões de crédito">{cartoes.map((c) => (
                  <option key={c.id} value={`cartao:${c.id}`}>{c.nome} · final {c.final}</option>))}</optgroup>
              )}
            </select></label>
        )}
        {usaCategoria && <SeletorCategoria valor={f.categoria_id} aoMudar={(v) => muda("categoria_id", v)}
          categorias={categorias.filter((c) => c.tipo === (t.tipo === "receita" ? "receita" : "despesa"))} />}
        {noCartao && viraCartao && competenciaFatura && (
          <label>Fatura
            <select value={f.fatura} onChange={(e) => muda("fatura", e.target.value)}>
              {[-1, 0, 1].map((n) => somarMes(competenciaFatura, n)).map((m) => (
                <option key={m} value={m}>Vencimento em {nomeMes(m)}</option>))}
            </select>
            <small className="dica">Use quando o banco lançou a compra numa fatura diferente.</small></label>
        )}
        <label>Observação<input value={f.observacao} onChange={(e) => muda("observacao", e.target.value)} /></label>
        {noCartao && (
          <label className="chave"><input type="checkbox" checked={f.conferido}
            onChange={(e) => muda("conferido", e.target.checked)} />Conferido com o extrato do banco</label>
        )}
        {erro && <p className="erro">{erro}</p>}
        <footer><button onClick={aoFechar}>Cancelar</button><button className="primario" onClick={salvar}>Salvar</button></footer>
      </div>
    </Modal>
  );
}
