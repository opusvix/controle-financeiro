import { useState } from "react";
import { api } from "../api";
import { dataBR, hojeISO, paraCentavos } from "../formato";
import Modal from "./Modal";
import { useDados } from "./useDados";

/** O mínimo para dar baixa numa conta a pagar (ou a receber). */
export type Pagavel = {
  id: number; tipo: string; descricao: string; valor_centavos: number; data: string; conta_id: number | null;
};

/**
 * Dá baixa numa conta a pagar: confirma o valor real (a luz nunca vem igual à estimativa),
 * a data do pagamento e a conta de onde o dinheiro saiu.
 */
export default function PagarConta({ transacao: t, aoFechar, aoSalvar }: {
  transacao: Pagavel; aoFechar: () => void; aoSalvar: () => void;
}) {
  const contas = useDados(api.contas).dados?.filter((c) => c.ativa) ?? [];
  const receita = t.tipo === "receita";
  const [f, setF] = useState({
    valor: (t.valor_centavos / 100).toFixed(2).replace(".", ","), data: hojeISO(),
    conta_id: t.conta_id ? String(t.conta_id) : "",
  });
  const [erro, setErro] = useState<string | null>(null);

  async function salvar() {
    const valor = paraCentavos(f.valor);
    if (!valor) return setErro("Valor inválido.");
    if (!f.conta_id) return setErro("Escolha a conta.");
    try {
      await api.editarTransacao(t.id, { pago: true, valor_centavos: valor, data: f.data, conta_id: Number(f.conta_id) });
      aoSalvar();
    } catch (e) { setErro((e as Error).message); }
  }

  return (
    <Modal titulo={receita ? "Confirmar recebimento" : "Pagar conta"} aoFechar={aoFechar}>
      <div className="form">
        <p><strong>{t.descricao}</strong> · previsto para {dataBR(t.data)}</p>
        <div className="duas">
          <label>{receita ? "Valor recebido (R$)" : "Valor pago (R$)"}
            <input value={f.valor} inputMode="decimal" autoFocus onChange={(e) => setF({ ...f, valor: e.target.value })} /></label>
          <label>{receita ? "Recebido em" : "Pago em"}
            <input type="date" value={f.data} onChange={(e) => setF({ ...f, data: e.target.value })} /></label>
        </div>
        <label>{receita ? "Entrou na conta" : "Saiu da conta"}
          <select value={f.conta_id} onChange={(e) => setF({ ...f, conta_id: e.target.value })}>
            <option value="">Escolha…</option>
            {contas.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select></label>
        <p className="dica">Os meses seguintes continuam com o valor previsto.</p>
        {erro && <p className="erro">{erro}</p>}
        <footer><button onClick={aoFechar}>Cancelar</button>
          <button className="primario" onClick={salvar}>{receita ? "Confirmar" : "Pagar"}</button></footer>
      </div>
    </Modal>
  );
}
