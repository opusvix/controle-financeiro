import { useState } from "react";
import { api, type Conta } from "../api";
import Modal from "../componentes/Modal";
import { useDados } from "../componentes/useDados";
import { hojeISO, paraCentavos, reais } from "../formato";

const TIPOS: Record<string, string> = {
  corrente: "Conta corrente", poupanca: "Poupança", investimento: "Investimento",
  carteira: "Carteira (dinheiro)", outro: "Outro",
};
const CORES = ["#111827", "#0ea5e9", "#a855f7", "#65a30d", "#f59e0b", "#ef4444", "#14b8a6", "#ec4899"];

export default function Contas() {
  const contas = useDados(api.contas);
  const painel = useDados(() => api.painel(hojeISO().slice(0, 7)));
  const inst = useDados(api.instituicoes);
  const [editando, setEditando] = useState<Partial<Conta> | null>(null);
  const saldo = (id: number) => painel.dados?.contas.find((c) => c.id === id);

  return (
    <>
      <header className="topo">
        <h1>Contas</h1>
        <button className="primario" onClick={() => setEditando({ tipo: "corrente", cor: CORES[1],
          compoe_saldo_disponivel: 1, saldo_inicial_centavos: 0, data_saldo_inicial: hojeISO() })}>
          + Nova conta</button>
      </header>
      {painel.dados && (
        <section className="kpis">
          <div className="kpi"><i style={{ background: "#3b82f6" }} />
            <div><span>Saldo disponível</span><strong>{reais(painel.dados.saldo_disponivel)}</strong></div></div>
          <div className="kpi"><i style={{ background: "#8b5cf6" }} />
            <div><span>Patrimônio</span><strong>{reais(painel.dados.patrimonio)}</strong></div></div>
        </section>
      )}
      <section className="grade-cartoes">
        {contas.dados?.map((c) => (
          <div key={c.id} className={`cartao-painel ${c.ativa ? "" : "inativa"}`}>
            <header><i style={{ background: c.cor }} /><strong>{c.nome}</strong>
              <button className="link" onClick={() => setEditando(c)}>Editar</button></header>
            <small>{TIPOS[c.tipo]}{c.compoe_saldo_disponivel ? "" : " · fora do saldo disponível"}</small>
            <dl>
              <dt>Saldo atual</dt><dd>{reais(saldo(c.id)?.saldo_atual ?? 0)}</dd>
              <dt>Saldo previsto</dt><dd>{reais(saldo(c.id)?.saldo_previsto ?? 0)}</dd>
            </dl>
          </div>
        ))}
      </section>
      {editando && (
        <FormConta conta={editando} instituicoes={inst.dados ?? []}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => { setEditando(null); contas.recarregar(); painel.recarregar(); }} />
      )}
    </>
  );
}

function FormConta({ conta, instituicoes, aoFechar, aoSalvar }: {
  conta: Partial<Conta>; instituicoes: { id: number; nome: string }[];
  aoFechar: () => void; aoSalvar: () => void;
}) {
  const [c, setC] = useState(conta);
  const [saldoTxt, setSaldoTxt] = useState(((conta.saldo_inicial_centavos ?? 0) / 100).toFixed(2).replace(".", ","));
  const [erro, setErro] = useState<string | null>(null);
  const muda = (campo: keyof Conta, valor: unknown) => setC({ ...c, [campo]: valor });

  async function salvar() {
    const negativo = saldoTxt.trim().startsWith("-");
    const cent = paraCentavos(saldoTxt.replace("-", ""));
    if (cent === null) return setErro("Saldo inicial inválido. Use, por exemplo, 1.234,56");
    try {
      await api.salvarConta({ ...c, saldo_inicial_centavos: negativo ? -cent : cent,
        compoe_saldo_disponivel: c.compoe_saldo_disponivel, ativa: c.ativa ?? 1 }, c.id);
      aoSalvar();
    } catch (e) { setErro((e as Error).message); }
  }

  return (
    <Modal titulo={c.id ? "Editar conta" : "Nova conta"} aoFechar={aoFechar}>
      <div className="form">
        <label>Nome<input value={c.nome ?? ""} onChange={(e) => muda("nome", e.target.value)}
          placeholder="Ex.: C6 Bank 1118" autoFocus /></label>
        <label>Instituição financeira
          <select value={c.instituicao_id ?? ""} onChange={(e) => muda("instituicao_id", e.target.value ? Number(e.target.value) : null)}>
            <option value="">(nenhuma)</option>
            {instituicoes.map((i) => <option key={i.id} value={i.id}>{i.nome}</option>)}
          </select></label>
        <label>Tipo
          <select value={c.tipo} onChange={(e) => muda("tipo", e.target.value)}>
            {Object.entries(TIPOS).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select></label>
        <div className="duas">
          <label>Saldo inicial (R$)<input value={saldoTxt} onChange={(e) => setSaldoTxt(e.target.value)} inputMode="decimal" /></label>
          <label>Na data<input type="date" value={c.data_saldo_inicial ?? ""} onChange={(e) => muda("data_saldo_inicial", e.target.value)} /></label>
        </div>
        <fieldset className="cores"><legend>Cor da conta</legend>
          {CORES.map((cor) => (
            <button key={cor} type="button" className={c.cor === cor ? "sel" : ""} style={{ background: cor }}
              onClick={() => muda("cor", cor)} aria-label={`Cor ${cor}`} />
          ))}</fieldset>
        <label className="chave"><input type="checkbox" checked={!!c.compoe_saldo_disponivel}
          onChange={(e) => muda("compoe_saldo_disponivel", e.target.checked ? 1 : 0)} />
          Compõe o saldo disponível (desmarque para investimentos)</label>
        {c.id && <label className="chave"><input type="checkbox" checked={!!c.ativa}
          onChange={(e) => muda("ativa", e.target.checked ? 1 : 0)} />Conta ativa</label>}
        {erro && <p className="erro">{erro}</p>}
        <footer><button onClick={aoFechar}>Cancelar</button><button className="primario" onClick={salvar}>Salvar</button></footer>
      </div>
    </Modal>
  );
}
