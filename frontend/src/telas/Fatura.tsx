import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type Fatura as TFatura, type LancamentoFatura } from "../api";
import EditarTransacao from "../componentes/EditarTransacao";
import Kpi from "../componentes/Kpi";
import Modal from "../componentes/Modal";
import SeletorCategoria from "../componentes/SeletorCategoria";
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
  const [lancando, setLancando] = useState(false);
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
              valor={f.conferido} cor="#F38433" />
          </section>
          <ConferenciaBanco key={`${f.cartao.id}-${f.competencia}`} fatura={f} aoMudar={fatura.recarregar} />
          <div className="acoes-fatura">
            <button onClick={() => setLancando(true)}>+ Lançar nesta fatura</button>
          </div>
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
                  <td>{t.tipo === "credito_cartao" && <span className="selo-credito">crédito</span>}
                    {t.descricao}{t.observacao && <small className="dica"> · {t.observacao}</small>}</td>
                  <td>{t.categoria ?? (t.itens ? `${t.itens} itens` : "—")}</td>
                  <td className={`num ${t.tipo === "credito_cartao" ? "pos" : ""}`}>
                    {reais(t.tipo === "credito_cartao" ? -t.valor_centavos : t.valor_centavos)}</td>
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
      {lancando && f && <LancarNaFatura fatura={f} aoFechar={() => setLancando(false)}
        aoSalvar={(continuar) => { if (!continuar) setLancando(false); fatura.recarregar(); }} />}
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
            ? "o app tem a mais. Falta lançar um crédito ou estorno, ou algum valor está maior."
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

const MODELOS = [
  { id: "compra", nome: "Compra esquecida", descricao: "", categoria: null },
  { id: "credito", nome: "Crédito / estorno", descricao: "Estorno ", categoria: null },
  { id: "tarifa", nome: "Anuidade / tarifa", descricao: "Anuidade", categoria: "Tarifas bancárias" },
  { id: "juros", nome: "Juros / IOF / multa", descricao: "Juros e IOF", categoria: "Tarifas bancárias" },
] as const;

/**
 * Lança direto nesta fatura o que apareceu no extrato do banco e faltava no app.
 * Já entra como conferido, porque veio do próprio extrato.
 */
function LancarNaFatura({ fatura: f, aoFechar, aoSalvar }: {
  fatura: TFatura; aoFechar: () => void; aoSalvar: (continuar: boolean) => void;
}) {
  const categorias = useDados(api.categorias).dados ?? [];
  const dif = f.diferenca_banco ?? 0;   // > 0: app tem a mais (falta crédito); < 0: falta compra/tarifa
  const vespera = (() => {   // compra precisa cair antes do fechamento
    const d = new Date(f.data_fechamento + "T12:00:00"); d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  })();
  const [modelo, setModelo] = useState<(typeof MODELOS)[number]["id"]>(dif > 0 ? "credito" : "compra");
  const ehCredito = modelo === "credito";
  const [descricao, setDescricao] = useState("");
  const sugestao = (credito: boolean) => {
    const v = credito ? Math.max(dif, 0) : Math.max(-dif, 0);
    return v ? (v / 100).toFixed(2).replace(".", ",") : "";
  };
  const [valor, setValor] = useState(sugestao(dif > 0));
  const [data, setData] = useState(hojeISO() < f.data_fechamento ? hojeISO() : vespera);
  const [categoria, setCategoria] = useState("");
  const [parcelas, setParcelas] = useState("1");
  const [erro, setErro] = useState<string | null>(null);

  function escolher(id: (typeof MODELOS)[number]["id"]) {
    const m = MODELOS.find((x) => x.id === id)!;
    setModelo(id); setDescricao(m.descricao); setValor(sugestao(id === "credito"));
    setParcelas("1");
    const cat = m.categoria && categorias.find((c) => c.nome === m.categoria);
    setCategoria(cat ? String(cat.id) : "");
  }

  async function salvar(continuar: boolean) {
    const v = paraCentavos(valor);
    if (!v) return setErro("Valor inválido.");
    if (!descricao.trim()) return setErro("Informe a descrição.");
    try {
      const [t] = await api.criarTransacao({ tipo: ehCredito ? "credito_cartao" : "despesa_cartao", descricao, valor_centavos: v, data,
        cartao_id: f.cartao.id, fatura_competencia: f.competencia,
        parcelas: ehCredito ? 1 : Number(parcelas) || 1,
        categoria_id: categoria ? Number(categoria) : null });
      await api.editarTransacao(t.id, { conferido: true });
      setErro(null);
      if (continuar) { setDescricao(""); setValor(""); }
      aoSalvar(continuar);
    } catch (e) { setErro((e as Error).message); }
  }

  return (
    <Modal titulo={`Lançar na fatura de ${dataBR(f.data_vencimento).slice(3)}`} aoFechar={aoFechar}>
      <div className="form">
        <div className="abas">{MODELOS.map((m) => (
          <button key={m.id} className={modelo === m.id ? "sel" : ""} onClick={() => escolher(m.id)}>{m.nome}</button>
        ))}</div>
        <label>Descrição<input value={descricao} onChange={(e) => setDescricao(e.target.value)} autoFocus
          placeholder={modelo === "compra" ? "Como aparece no extrato" : ""} /></label>
        <div className="duas">
          <label>Valor (R$)<input value={valor} onChange={(e) => setValor(e.target.value)} inputMode="decimal" /></label>
          <label>Data<input type="date" value={data} onChange={(e) => setData(e.target.value)} /></label>
        </div>
        {!ehCredito && (
          <label>Parcelas<input type="number" min={1} max={72} value={parcelas}
            onChange={(e) => setParcelas(e.target.value)} /></label>
        )}
        {!ehCredito && Number(parcelas) > 1 && <p className="dica">O <b>valor total</b> é dividido em {Number(parcelas)}x.
          A 1ª parcela entra nesta fatura; as demais caem uma por mês nas faturas seguintes.</p>}
        {sugestao(ehCredito) && <p className="dica">O valor já vem com a diferença para o banco. Ajuste se
          for só parte dela.</p>}
        {ehCredito && <p className="dica">Crédito <b>diminui</b> a fatura. Escolha a categoria da compra
          estornada para a despesa dela também diminuir.</p>}
        <SeletorCategoria categorias={categorias.filter((c) => c.tipo === "despesa")} valor={categoria}
          aoMudar={setCategoria} />
        <p className="dica">Entra nesta fatura mesmo que a data seja depois do fechamento, e já fica marcado
          como conferido.</p>
        {erro && <p className="erro">{erro}</p>}
        <footer><button onClick={aoFechar}>Cancelar</button>
          <button onClick={() => salvar(true)}>Salvar e lançar outro</button>
          <button className="primario" onClick={() => salvar(false)}>Salvar</button></footer>
      </div>
    </Modal>
  );
}
