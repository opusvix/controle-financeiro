import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type Cartao } from "../api";
import Modal from "../componentes/Modal";
import SeletorMes from "../componentes/SeletorMes";
import { useDados } from "../componentes/useDados";
import { dataBR, mesAtual, paraCentavos, reais } from "../formato";

const BANDEIRAS = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard", "Outra"];

export default function Cartoes() {
  const [mes, setMes] = useState(mesAtual());
  const painel = useDados(() => api.painel(mes), [mes]);
  const cartoes = useDados(api.cartoes);
  const contas = useDados(api.contas);
  const inst = useDados(api.instituicoes);
  const [editando, setEditando] = useState<Partial<Cartao> | null>(null);
  const cadastro = (id: number) => cartoes.dados?.find((c) => c.id === id);

  return (
    <>
      <header className="topo">
        <h1>Cartões de crédito</h1>
        <SeletorMes mes={mes} aoMudar={setMes} />
        <button className="primario" onClick={() => setEditando({ bandeira: "Visa", dia_fechamento: 3,
          dia_vencimento: 10, limite_centavos: 0 })}>+ Novo cartão</button>
      </header>
      {painel.dados?.cartoes.length === 0 && (
        <p className="dica">Nenhum cartão cadastrado. Clique em <b>+ Novo cartão</b> para começar.</p>)}
      <section className="grade-cartoes">
        {painel.dados?.cartoes.map((c) => {
          const usado = c.limite_centavos ? 1 - c.limite_disponivel / c.limite_centavos : 0;
          return (
            <div key={c.id} className="cartao-painel">
              <header><strong>{c.nome}</strong><small>{c.bandeira} · final {c.final}</small>
                <button className="link" onClick={() => setEditando(cadastro(c.id) ?? null)}>Editar</button></header>
              <dl>
                <dt>Fatura de {mes.split("-").reverse().join("/")}</dt><dd className="neg">{reais(c.fatura_total)}</dd>
                <dt>Situação</dt><dd>{c.fatura_situacao}</dd>
                {c.data_vencimento && <><dt>Vencimento</dt><dd>{dataBR(c.data_vencimento)}</dd></>}
              </dl>
              <div className="barra"><b style={{ width: `${Math.min(100, usado * 100)}%` }} /></div>
              <small>{reais(c.limite_centavos - c.limite_disponivel)} de {reais(c.limite_centavos)} ·
                disponível {reais(c.limite_disponivel)}</small>
              <Link className="botao bloco" to={`/cartoes/${c.id}?mes=${mes}`}>Ver fatura e conferir</Link>
            </div>
          );
        })}
      </section>
      {editando && (
        <FormCartao cartao={editando} contas={contas.dados ?? []} instituicoes={inst.dados ?? []}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => { setEditando(null); cartoes.recarregar(); painel.recarregar(); }} />
      )}
    </>
  );
}

function FormCartao({ cartao, contas, instituicoes, aoFechar, aoSalvar }: {
  cartao: Partial<Cartao>; contas: { id: number; nome: string }[];
  instituicoes: { id: number; nome: string }[]; aoFechar: () => void; aoSalvar: () => void;
}) {
  const [c, setC] = useState(cartao);
  const [limiteTxt, setLimiteTxt] = useState(((cartao.limite_centavos ?? 0) / 100).toFixed(2).replace(".", ","));
  const [erro, setErro] = useState<string | null>(null);
  const muda = (campo: keyof Cartao, valor: unknown) => setC({ ...c, [campo]: valor });

  async function salvar() {
    const limite = paraCentavos(limiteTxt);
    if (limite === null) return setErro("Limite inválido.");
    if (!/^\d{4}$/.test(c.final ?? "")) return setErro("Informe os 4 últimos dígitos do cartão.");
    try { await api.salvarCartao({ ...c, limite_centavos: limite, ativo: c.ativo ?? 1 }, c.id); aoSalvar(); }
    catch (e) { setErro((e as Error).message); }
  }

  return (
    <Modal titulo={c.id ? "Editar cartão" : "Novo cartão"} aoFechar={aoFechar}>
      <div className="form">
        <label>Nome<input value={c.nome ?? ""} onChange={(e) => muda("nome", e.target.value)} placeholder="Ex.: BB JU" autoFocus /></label>
        <div className="duas">
          <label>Bandeira<select value={c.bandeira} onChange={(e) => muda("bandeira", e.target.value)}>
            {BANDEIRAS.map((b) => <option key={b}>{b}</option>)}</select></label>
          <label>4 últimos dígitos<input value={c.final ?? ""} maxLength={4} inputMode="numeric"
            onChange={(e) => muda("final", e.target.value.replace(/\D/g, ""))} placeholder="3756" /></label>
        </div>
        <label>Instituição financeira
          <select value={c.instituicao_id ?? ""} onChange={(e) => muda("instituicao_id", e.target.value ? Number(e.target.value) : null)}>
            <option value="">(nenhuma)</option>
            {instituicoes.map((i) => <option key={i.id} value={i.id}>{i.nome}</option>)}</select></label>
        <div className="tres">
          <label>Limite (R$)<input value={limiteTxt} onChange={(e) => setLimiteTxt(e.target.value)} inputMode="decimal" /></label>
          <label>Dia do fechamento<input type="number" min={1} max={31} value={c.dia_fechamento ?? ""}
            onChange={(e) => muda("dia_fechamento", Number(e.target.value))} /></label>
          <label>Dia do vencimento<input type="number" min={1} max={31} value={c.dia_vencimento ?? ""}
            onChange={(e) => muda("dia_vencimento", Number(e.target.value))} /></label>
        </div>
        <label>Conta que paga a fatura
          <select value={c.conta_pagamento_id ?? ""} onChange={(e) => muda("conta_pagamento_id", e.target.value ? Number(e.target.value) : null)}>
            <option value="">(escolher ao pagar)</option>
            {contas.map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}</select></label>
        <p className="dica">Compras feitas no dia do fechamento ou depois entram na fatura seguinte.</p>
        {erro && <p className="erro">{erro}</p>}
        <footer><button onClick={aoFechar}>Cancelar</button><button className="primario" onClick={salvar}>Salvar</button></footer>
      </div>
    </Modal>
  );
}
