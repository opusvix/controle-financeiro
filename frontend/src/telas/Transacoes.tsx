import { useState } from "react";
import { api, type Transacao } from "../api";
import EditarTransacao from "../componentes/EditarTransacao";
import SeletorCategoria from "../componentes/SeletorCategoria";
import Kpi from "../componentes/Kpi";
import Modal from "../componentes/Modal";
import SeletorMes from "../componentes/SeletorMes";
import { useDados } from "../componentes/useDados";
import { dataBR, hojeISO, mesAtual, paraCentavos, reais } from "../formato";

type Tipo = "despesa" | "receita" | "despesa_cartao" | "transferencia" | "pagamento_fatura";

const TIPOS: { tipo: Tipo; nome: string; cor: string }[] = [
  { tipo: "despesa", nome: "Despesa", cor: "#ef4444" },
  { tipo: "receita", nome: "Receita", cor: "#22c55e" },
  { tipo: "despesa_cartao", nome: "Despesa no cartão", cor: "#14b8a6" },
  { tipo: "transferencia", nome: "Transferência", cor: "#3b82f6" },
  { tipo: "pagamento_fatura", nome: "Pagamento de fatura", cor: "#8b5cf6" },
];

/** Sinal do valor na lista: o que entra é +, o que sai é −. */
function efeito(t: Transacao) {
  if (t.tipo === "receita" || (t.tipo === "transferencia" && t.entrada)) return 1;
  if (t.tipo === "ajuste") return t.ajuste_negativo ? -1 : 1;
  return -1;
}

export default function Transacoes() {
  const [mes, setMes] = useState(mesAtual());
  const lista = useDados(() => api.transacoes(mes), [mes]);
  const painel = useDados(() => api.painel(mes), [mes]);
  const [novo, setNovo] = useState<Tipo | null>(null);
  const [escolhendo, setEscolhendo] = useState(false);
  const [editando, setEditando] = useState<Transacao | null>(null);

  async function apagar(t: Transacao) {
    const aviso = t.tipo === "transferencia" ? " As duas pontas da transferência serão apagadas." : "";
    if (!confirm(`Apagar "${t.descricao}"?${aviso}`)) return;
    await api.apagarTransacao(t.id);
    lista.recarregar(); painel.recarregar();
  }

  return (
    <>
      <header className="topo">
        <h1>Transações</h1>
        <SeletorMes mes={mes} aoMudar={setMes} />
        <div className="menu-novo">
          <button className="primario" onClick={() => setEscolhendo(!escolhendo)}>+ Nova</button>
          {escolhendo && (
            <ul>{TIPOS.map((t) => (
              <li key={t.tipo}><button onClick={() => { setNovo(t.tipo); setEscolhendo(false); }}>
                <i style={{ background: t.cor }} />{t.nome}</button></li>
            ))}</ul>
          )}
        </div>
      </header>
      {painel.dados && (
        <section className="kpis">
          <Kpi titulo="Saldo disponível" valor={painel.dados.saldo_disponivel} cor="#3b82f6" />
          <Kpi titulo="Receitas" valor={painel.dados.receitas} cor="#22c55e" />
          <Kpi titulo="Despesas" valor={painel.dados.despesas} cor="#ef4444" />
          <Kpi titulo="Balanço do mês" valor={painel.dados.receitas - painel.dados.despesas} cor="#14b8a6" />
        </section>
      )}
      <table className="tabela">
        <thead><tr><th>Situação</th><th>Data</th><th>Descrição</th><th>Categoria</th><th>Conta / cartão</th>
          <th className="num">Valor</th><th /></tr></thead>
        <tbody>
          {lista.dados?.length === 0 && <tr><td colSpan={7} className="vazio">Nenhuma transação neste mês.</td></tr>}
          {lista.dados?.map((t) => (
            <tr key={t.id}>
              <td>{t.pago ? <span className="ok" title="Paga">✓</span> : <span className="pendente" title="Pendente">!</span>}</td>
              <td>{dataBR(t.data)}</td>
              <td>{t.descricao}{t.tags && <small className="tags"> {t.tags}</small>}</td>
              <td>{t.categoria ?? (t.itens ? `${t.itens} itens` : TIPOS.find((x) => x.tipo === t.tipo)?.nome ?? "—")}</td>
              <td>{t.conta ?? t.cartao}</td>
              <td className={`num ${efeito(t) > 0 ? "pos" : "neg"}`}>{reais(efeito(t) * t.valor_centavos)}</td>
              <td className="acoes"><button className="link" onClick={() => setEditando(t)}>Editar</button>
                <button className="link" onClick={() => apagar(t)} aria-label="Apagar">Apagar</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {editando && <EditarTransacao transacao={editando} aoFechar={() => setEditando(null)}
        aoSalvar={() => { setEditando(null); lista.recarregar(); painel.recarregar(); }} />}
      {novo && <FormTransacao tipo={novo} aoFechar={() => setNovo(null)}
        aoSalvar={(continuar) => { if (!continuar) setNovo(null); lista.recarregar(); painel.recarregar(); }} />}
    </>
  );
}

function FormTransacao({ tipo, aoFechar, aoSalvar }: {
  tipo: Tipo; aoFechar: () => void; aoSalvar: (continuar: boolean) => void;
}) {
  const contas = useDados(api.contas).dados?.filter((c) => c.ativa) ?? [];
  const cartoes = useDados(api.cartoes).dados?.filter((c) => c.ativo) ?? [];
  const categorias = useDados(api.categorias).dados ?? [];
  const tags = useDados(api.tags).dados ?? [];
  const [f, setF] = useState({
    descricao: "", valor: "", data: hojeISO(), pago: true, conta_id: "", conta_destino_id: "",
    cartao_id: "", categoria_id: "", parcelas: "1", observacao: "", tags: [] as number[],
  });
  const [erro, setErro] = useState<string | null>(null);
  const muda = (campo: string, valor: unknown) => setF({ ...f, [campo]: valor });
  const info = TIPOS.find((t) => t.tipo === tipo)!;
  const tipoCategoria = tipo === "receita" ? "receita" : "despesa";
  const usaCategoria = tipo === "despesa" || tipo === "receita" || tipo === "despesa_cartao";
  const usaCartao = tipo === "despesa_cartao" || tipo === "pagamento_fatura";
  const usaConta = tipo !== "despesa_cartao";

  async function salvar(continuar: boolean) {
    const valor = paraCentavos(f.valor);
    if (!valor) return setErro("Informe um valor maior que zero, por exemplo 375,06");
    const num = (s: string) => (s ? Number(s) : null);
    try {
      await api.criarTransacao({
        tipo, descricao: f.descricao || info.nome, valor_centavos: valor, data: f.data,
        pago: tipo === "despesa" || tipo === "receita" ? f.pago : true,
        conta_id: usaConta ? num(f.conta_id) : null,
        conta_destino_id: tipo === "transferencia" ? num(f.conta_destino_id) : null,
        cartao_id: usaCartao ? num(f.cartao_id) : null,
        categoria_id: usaCategoria ? num(f.categoria_id) : null,
        parcelas: tipo === "despesa_cartao" ? Number(f.parcelas) || 1 : 1,
        observacao: f.observacao || null, tags: f.tags,
      });
      if (continuar) setF({ ...f, descricao: "", valor: "", observacao: "" });
      setErro(null);
      aoSalvar(continuar);
    } catch (e) { setErro((e as Error).message); }
  }

  return (
    <Modal titulo={`Nova ${info.nome.toLowerCase()}`} aoFechar={aoFechar}>
      <div className="form">
        <div className="duas">
          <label>Valor (R$)<input value={f.valor} onChange={(e) => muda("valor", e.target.value)}
            inputMode="decimal" placeholder="0,00" autoFocus style={{ color: info.cor }} /></label>
          <label>{tipo === "despesa_cartao" ? "Data da compra" : "Data"}
            <input type="date" value={f.data} onChange={(e) => muda("data", e.target.value)} /></label>
        </div>
        <label>Descrição<input value={f.descricao} onChange={(e) => muda("descricao", e.target.value)}
          placeholder={tipo === "transferencia" ? "Ex.: Aplicação no CDB" : "Ex.: SUPERMERCADO PERIM"} /></label>
        {usaCategoria && <SeletorCategoria categorias={categorias.filter((c) => c.tipo === tipoCategoria)}
          valor={f.categoria_id} aoMudar={(v) => muda("categoria_id", v)} />}
        {usaConta && (
          <label>{tipo === "transferencia" ? "Sai da conta" : tipo === "receita" ? "Entra na conta" : "Conta"}
            <select value={f.conta_id} onChange={(e) => muda("conta_id", e.target.value)}>
              <option value="">Escolha…</option>
              {contas.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select></label>
        )}
        {tipo === "transferencia" && (
          <label>Entra na conta<select value={f.conta_destino_id} onChange={(e) => muda("conta_destino_id", e.target.value)}>
            <option value="">Escolha…</option>
            {contas.filter((c) => String(c.id) !== f.conta_id).map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select></label>
        )}
        {usaCartao && (
          <div className={tipo === "despesa_cartao" ? "duas" : ""}>
            <label>Cartão<select value={f.cartao_id} onChange={(e) => muda("cartao_id", e.target.value)}>
              <option value="">Escolha…</option>
              {cartoes.map((c) => <option key={c.id} value={c.id}>{c.nome} · final {c.final}</option>)}</select></label>
            {tipo === "despesa_cartao" && (
              <label>Parcelas<input type="number" min={1} max={72} value={f.parcelas}
                onChange={(e) => muda("parcelas", e.target.value)} /></label>
            )}
          </div>
        )}
        {tipo === "pagamento_fatura" && (
          <p className="dica">Pagar a fatura não é uma despesa nova: a despesa já foi lançada em cada compra.
            Aqui só sai o dinheiro da conta.</p>
        )}
        {(tipo === "despesa" || tipo === "receita") && (
          <label className="chave"><input type="checkbox" checked={f.pago} onChange={(e) => muda("pago", e.target.checked)} />
            {tipo === "despesa" ? "Já foi paga" : "Já foi recebida"}</label>
        )}
        {tags.length > 0 && (
          <fieldset className="tags-sel"><legend>Tags</legend>
            {tags.map((t) => (
              <label key={t.id} className="chave"><input type="checkbox" checked={f.tags.includes(t.id)}
                onChange={(e) => muda("tags", e.target.checked ? [...f.tags, t.id] : f.tags.filter((x) => x !== t.id))} />
                {t.nome}</label>
            ))}</fieldset>
        )}
        <label>Observação<input value={f.observacao} onChange={(e) => muda("observacao", e.target.value)} /></label>
        {erro && <p className="erro">{erro}</p>}
        <footer>
          <button onClick={() => salvar(true)}>Salvar e criar nova</button>
          <button className="primario" onClick={() => salvar(false)}>Salvar</button>
        </footer>
      </div>
    </Modal>
  );
}
