import { useState } from "react";
import { api } from "../api";
import { nomeMes, paraCentavos, somarMes } from "../formato";
import FichaConta, { gravarFicha, useFicha } from "./FichaConta";
import Modal from "./Modal";
import SeletorCategoria from "./SeletorCategoria";
import { useDados } from "./useDados";

/** O mínimo que a edição precisa saber de um lançamento (vale para a lista e para a fatura). */
export type Editavel = {
  id: number; tipo: string; descricao: string; valor_centavos: number; data: string;
  conta_id: number | null; cartao_id?: number | null; categoria_id: number | null;
  observacao: string | null; itens: number; conferido: number; parcela: number | null;
  total_parcelas?: number | null; recorrencia_id?: string | null; pago?: number;
  vencimento?: string | null;
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
  const trocaCartao = noCartao && !trocaPagamento;           // parcela ou crédito: só entre cartões
  const temProximas = !!t.parcela && !!t.total_parcelas && t.parcela < t.total_parcelas;

  const [f, setF] = useState({
    descricao: t.descricao, valor: (t.valor_centavos / 100).toFixed(2).replace(".", ","), data: t.data,
    pagoCom: noCartao ? `cartao:${t.cartao_id}` : `conta:${t.conta_id}`,
    categoria_id: t.categoria_id ? String(t.categoria_id) : "", observacao: t.observacao ?? "",
    conferido: !!t.conferido, fatura: competenciaFatura ?? "", proximas: true, nasProximas: true,
  });
  const [erro, setErro] = useState<string | null>(null);
  // Conta da casa (despesa à vista paga por conta): ficha com consumo, bandeira e multa.
  const usaFicha = t.tipo === "despesa";
  const ficha = useFicha(t.id);
  const [vencimento, setVencimento] = useState(t.vencimento ?? "");
  const cat = categorias.find((c) => String(c.id) === f.categoria_id);
  const mae = categorias.find((c) => c.id === cat?.pai_id);
  const catFixa = !!(cat?.fixa || mae?.fixa);   // conta da casa: mostra a ficha
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
    else if (trocaCartao && Number(id) !== t.cartao_id) {
      d.cartao_id = Number(id);
      d.parcelas_seguintes = temProximas && f.proximas;
    }
    else if (usaConta) d.conta_id = Number(id);
    if (t.recorrencia_id) d.aplicar_nas_proximas = f.nasProximas;
    if (noCartao) {
      d.conferido = f.conferido;
      if (f.fatura && f.fatura !== competenciaFatura) d.fatura_competencia = f.fatura;
    }
    if (usaFicha && t.pago && vencimento !== (t.vencimento ?? "")) d.vencimento = vencimento || null;
    try {
      await api.editarTransacao(t.id, d);
      if (usaFicha && ficha.form) await gravarFicha(t.id, ficha.form, ficha.gravada);
      aoSalvar();
    }
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
        {trocaCartao && (
          <label>Cartão
            <select value={f.pagoCom} onChange={(e) => muda("pagoCom", e.target.value)}>
              {cartoes.map((c) => <option key={c.id} value={`cartao:${c.id}`}>{c.nome} · final {c.final}</option>)}
            </select></label>
        )}
        {trocaCartao && temProximas && f.pagoCom !== `cartao:${t.cartao_id}` && (
          <label className="chave"><input type="checkbox" checked={f.proximas}
            onChange={(e) => muda("proximas", e.target.checked)} />
            Levar também as próximas parcelas desta compra (até a {t.total_parcelas}ª)</label>
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
        {usaFicha && !!t.pago && (
          <label>Vencimento
            <input type="date" value={vencimento} onChange={(e) => setVencimento(e.target.value)} />
            <small className="dica">Guardado ao dar baixa em “Pagar”. Serve para medir atraso.</small></label>
        )}
        {usaFicha && ficha.form && (ficha.gravada || !!ficha.form.tipo || catFixa) && (
          <FichaConta form={ficha.form} aoMudar={ficha.setForm} valorCentavos={paraCentavos(f.valor)} />
        )}
        <label>Observação<input value={f.observacao} onChange={(e) => muda("observacao", e.target.value)} /></label>
        {t.recorrencia_id && (
          <label className="chave"><input type="checkbox" checked={f.nasProximas}
            onChange={(e) => muda("nasProximas", e.target.checked)} />
            Aplicar também nos próximos meses ainda não pagos (valor, descrição, conta, categoria)</label>
        )}
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
