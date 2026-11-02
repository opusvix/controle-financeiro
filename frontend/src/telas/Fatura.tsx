import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type Fatura as TFatura, type LancamentoFatura } from "../api";
import EditarTransacao from "../componentes/EditarTransacao";
import Kpi from "../componentes/Kpi";
import Modal from "../componentes/Modal";
import SeletorMes from "../componentes/SeletorMes";
import { useDados } from "../componentes/useDados";
import { dataBR, hojeISO, mesAtual, paraCentavos, reais } from "../formato";

/** Fatura de um cartão: conferir item a item com o extrato do banco, corrigir e pagar. */
export default function Fatura() {
  const id = Number(useParams().id);
  const [busca, setBusca] = useSearchParams();
  const mes = busca.get("mes") ?? mesAtual();
  const setMes = (m: string) => setBusca({ mes: m });
  const fatura = useDados(() => api.fatura(id, mes), [id, mes]);
  const [editando, setEditando] = useState<LancamentoFatura | null>(null);
  const [pagando, setPagando] = useState(false);
  const f = fatura.dados;

  async function marcar(t: LancamentoFatura) {
    await api.editarTransacao(t.id, { conferido: !t.conferido });
    fatura.recarregar();
  }
  async function apagar(t: LancamentoFatura) {
    if (!confirm(`Apagar "${t.descricao}"?`)) return;
    await api.apagarTransacao(t.id);
    fatura.recarregar();
  }

  return (
    <>
      <header className="topo">
        <h1><Link to="/cartoes" className="voltar">‹ Cartões</Link>
          {f ? ` ${f.cartao.nome} · final ${f.cartao.final}` : " Fatura"}</h1>
        <SeletorMes mes={mes} aoMudar={setMes} />
        <button className="primario" disabled={!f || f.a_pagar === 0} onClick={() => setPagando(true)}>Pagar fatura</button>
      </header>
      {fatura.erro && <p className="erro">{fatura.erro}</p>}
      {f && (
        <>
          <p className="faixa-fatura">
            Fecha em <b>{dataBR(f.data_fechamento)}</b> · vence em <b>{dataBR(f.data_vencimento)}</b> ·
            <span className={`situacao ${f.situacao.replace(" ", "-")}`}> {f.situacao}</span>
          </p>
          <section className="kpis">
            <Kpi titulo="Total da fatura" valor={f.total} cor="#14b8a6" />
            <Kpi titulo="Pago" valor={f.pago} cor="#22c55e" />
            <Kpi titulo="A pagar" valor={f.a_pagar} cor="#ef4444" />
            <Kpi titulo={`Conferido (${f.lancamentos.filter((t) => t.conferido).length} de ${f.lancamentos.length})`}
              valor={f.conferido} cor="#8b5cf6" />
          </section>
          <ConferenciaBanco key={`${f.cartao.id}-${f.competencia}`} fatura={f} aoMudar={fatura.recarregar} />
          <table className="tabela">
            <thead><tr><th title="Conferido com o extrato">✓</th><th>Data</th><th>Descrição</th><th>Categoria</th>
              <th className="num">Valor</th><th /></tr></thead>
            <tbody>
              {f.lancamentos.length === 0 && <tr><td colSpan={6} className="vazio">Nenhuma compra nesta fatura.</td></tr>}
              {f.lancamentos.map((t) => (
                <tr key={t.id} className={t.conferido ? "conferido" : ""}>
                  <td><input type="checkbox" checked={!!t.conferido} onChange={() => marcar(t)}
                    aria-label="Conferido" /></td>
                  <td>{dataBR(t.data)}</td>
                  <td>{t.descricao}{t.observacao && <small className="dica"> · {t.observacao}</small>}</td>
                  <td>{t.categoria ?? (t.itens ? `${t.itens} itens` : "—")}</td>
                  <td className="num">{reais(t.valor_centavos)}</td>
                  <td className="acoes"><button className="link" onClick={() => setEditando(t)}>Editar</button>
                    <button className="link" onClick={() => apagar(t)}>Apagar</button></td>
                </tr>
              ))}
            </tbody>
            {f.lancamentos.length > 0 && (
              <tfoot><tr><td colSpan={4}>Total</td><td className="num"><b>{reais(f.total)}</b></td><td /></tr></tfoot>
            )}
          </table>
          {f.pagamentos.length > 0 && (
            <>
              <h3 className="espaco">Pagamentos</h3>
              <table className="tabela">
                <tbody>{f.pagamentos.map((p) => (
                  <tr key={p.id}><td>{dataBR(p.data)}</td><td>{p.descricao}</td><td>{p.conta}</td>
                    <td className="num pos">{reais(p.valor_centavos)}</td>
                    <td className="acoes"><button className="link" onClick={() => setEditando(p)}>Editar</button>
                      <button className="link" onClick={() => apagar(p)}>Apagar</button></td></tr>
                ))}</tbody>
              </table>
            </>
          )}
        </>
      )}
      {editando && f && (
        <EditarTransacao transacao={{ ...editando, cartao_id: f.cartao.id }} competenciaFatura={f.competencia}
          aoFechar={() => setEditando(null)} aoSalvar={() => { setEditando(null); fatura.recarregar(); }} />
      )}
      {pagando && f && <PagarFatura fatura={f} aoFechar={() => setPagando(false)}
        aoSalvar={() => { setPagando(false); fatura.recarregar(); }} />}
    </>
  );
}

/** Total que o banco cobrou x total lançado no app: a diferença aponta o que falta conferir. */
function ConferenciaBanco({ fatura: f, aoMudar }: { fatura: TFatura; aoMudar: () => void }) {
  const [txt, setTxt] = useState(f.valor_banco != null ? (f.valor_banco / 100).toFixed(2).replace(".", ",") : "");
  const [erro, setErro] = useState<string | null>(null);
  if (!f.fatura_id) return null;

  async function salvar() {
    const valor = txt.trim() ? paraCentavos(txt) : null;
    if (txt.trim() && valor === null) return setErro("Valor inválido.");
    try { await api.valorBanco(f.cartao.id, f.competencia, valor); setErro(null); aoMudar(); }
    catch (e) { setErro((e as Error).message); }
  }

  const d = f.diferenca_banco;
  return (
    <div className="destaque conferencia">
      <label>Total da fatura no app do banco (R$)
        <span className="linha"><input value={txt} onChange={(e) => setTxt(e.target.value)} inputMode="decimal"
          placeholder="ex.: 1.234,56" onKeyDown={(e) => e.key === "Enter" && salvar()} />
          <button onClick={salvar}>Comparar</button></span></label>
      {d === null ? <span className="dica">Digite o total do banco para comparar com o app.</span>
        : d === 0 ? <span className="aviso-ok">✓ Bate com o banco</span>
        : <span className="erro">Diferença de {reais(Math.abs(d))}: {d > 0
            ? "o app tem lançamentos a mais (ou valores maiores)."
            : "falta lançar algo no app (ou algum valor está menor)."}</span>}
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}

function PagarFatura({ fatura: f, aoFechar, aoSalvar }: { fatura: TFatura; aoFechar: () => void; aoSalvar: () => void }) {
  const contas = useDados(api.contas).dados?.filter((c) => c.ativa) ?? [];
  const [conta, setConta] = useState(f.cartao.conta_pagamento_id ? String(f.cartao.conta_pagamento_id) : "");
  const [valor, setValor] = useState((f.a_pagar / 100).toFixed(2).replace(".", ","));
  const [data, setData] = useState(hojeISO() < f.data_vencimento ? hojeISO() : f.data_vencimento);
  const [erro, setErro] = useState<string | null>(null);

  async function salvar() {
    const v = paraCentavos(valor);
    if (!v) return setErro("Valor inválido.");
    if (!conta) return setErro("Escolha a conta que pagou.");
    try {
      await api.criarTransacao({ tipo: "pagamento_fatura", descricao: `Fatura ${f.cartao.nome}`,
        valor_centavos: v, data, conta_id: Number(conta), cartao_id: f.cartao.id,
        fatura_competencia: f.competencia });
      aoSalvar();
    } catch (e) { setErro((e as Error).message); }
  }

  return (
    <Modal titulo={`Pagar fatura ${f.cartao.nome}`} aoFechar={aoFechar}>
      <div className="form">
        <label>Conta que pagou<select value={conta} onChange={(e) => setConta(e.target.value)}>
          <option value="">Escolha…</option>
          {contas.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select></label>
        <div className="duas">
          <label>Valor (R$)<input value={valor} onChange={(e) => setValor(e.target.value)} inputMode="decimal" /></label>
          <label>Data<input type="date" value={data} onChange={(e) => setData(e.target.value)} /></label>
        </div>
        <p className="dica">O pagamento só tira o dinheiro da conta. As compras já foram contadas como despesa
          no dia em que foram feitas, por isso ele não entra como despesa de novo.</p>
        {erro && <p className="erro">{erro}</p>}
        <footer><button onClick={aoFechar}>Cancelar</button><button className="primario" onClick={salvar}>Registrar pagamento</button></footer>
      </div>
    </Modal>
  );
}
