import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Transacao } from "../api";
import EditarTransacao from "../componentes/EditarTransacao";
import SeletorCategoria from "../componentes/SeletorCategoria";
import Kpi from "../componentes/Kpi";
import Modal from "../componentes/Modal";
import PagarConta from "../componentes/PagarConta";
import SeletorMes from "../componentes/SeletorMes";
import { useDados } from "../componentes/useDados";
import { dataBR, hojeISO, mesAtual, paraCentavos, reais } from "../formato";

type Tipo = "despesa" | "receita" | "despesa_cartao" | "credito_cartao" | "transferencia" | "pagamento_fatura";

const TIPOS: { tipo: Tipo; nome: string; cor: string }[] = [
  { tipo: "despesa", nome: "Despesa", cor: "#ef4444" },
  { tipo: "receita", nome: "Receita", cor: "#22c55e" },
  { tipo: "despesa_cartao", nome: "Despesa no cartão", cor: "#14b8a6" },
  { tipo: "credito_cartao", nome: "Crédito na fatura (estorno)", cor: "#84cc16" },
  { tipo: "transferencia", nome: "Transferência", cor: "#3b82f6" },
  { tipo: "pagamento_fatura", nome: "Pagamento de fatura", cor: "#8b5cf6" },
];

/** Sinal do valor na lista: o que entra é +, o que sai é −. */
function efeito(t: Transacao) {
  if (t.tipo === "receita" || t.tipo === "credito_cartao" || (t.tipo === "transferencia" && t.entrada)) return 1;
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
  const [pagando, setPagando] = useState<Transacao | null>(null);
  const [agrupar, setAgrupar] = useState(true);
  const [abertos, setAbertos] = useState<number[]>([]);
  const alternar = (id: number) => setAbertos(abertos.includes(id) ? abertos.filter((x) => x !== id) : [...abertos, id]);

  // Compras e créditos de cartão viram uma linha por cartão (total do mês), que abre com os itens.
  const noCartao = (t: Transacao) => t.tipo === "despesa_cartao" || t.tipo === "credito_cartao";
  const grupos = new Map<number, Transacao[]>();
  for (const t of lista.dados ?? []) if (agrupar && noCartao(t) && t.cartao_id)
    grupos.set(t.cartao_id, [...(grupos.get(t.cartao_id) ?? []), t]);

  // Ordenação por coluna (clique no título; de novo inverte). Um grupo de cartão se ordena como
  // uma linha só: pela data mais recente, pelo total, pelo nome do cartão.
  type Coluna = "situacao" | "data" | "descricao" | "categoria" | "conta" | "valor";
  // A última ordenação escolhida fica guardada neste navegador e volta ao reabrir a tela.
  const [ordem, setOrdemEstado] = useState<{ col: Coluna; asc: boolean }>(() => {
    try { return JSON.parse(localStorage.getItem("transacoes.ordem") ?? "") ?? { col: "data", asc: false }; }
    catch { return { col: "data", asc: false }; }
  });
  const setOrdem = (o: { col: Coluna; asc: boolean }) => {
    setOrdemEstado(o);
    try { localStorage.setItem("transacoes.ordem", JSON.stringify(o)); } catch { /* sem armazenamento: só não lembra */ }
  };
  const ordenarPor = (col: Coluna) =>
    setOrdem(ordem.col === col ? { col, asc: !ordem.asc } : { col, asc: col !== "data" });
  type Item = { t: Transacao; grupo?: Transacao[] };
  const itens: Item[] = [];
  const vistos = new Set<number>();
  for (const t of lista.dados ?? []) {
    const grupo = agrupar && noCartao(t) && t.cartao_id ? grupos.get(t.cartao_id) : undefined;
    if (grupo && vistos.has(t.cartao_id!)) continue;
    if (grupo) vistos.add(t.cartao_id!);
    itens.push({ t, grupo });
  }
  const chave = ({ t, grupo }: Item): string | number => {
    const g = grupo ?? [t];
    switch (ordem.col) {
      case "situacao": return g.every((x) => x.pago) ? 1 : 0;
      case "data": return g.reduce((m, x) => (x.data > m ? x.data : m), "");
      case "descricao": return (grupo ? t.cartao ?? "" : t.descricao).toLowerCase();
      case "categoria": return (grupo ? "Compras do mês" : t.categoria ?? "").toLowerCase();
      case "conta": return (t.conta ?? t.cartao ?? "").toLowerCase();
      case "valor": return g.reduce((s, x) => s + efeito(x) * x.valor_centavos, 0);
    }
  };
  itens.sort((a, b) => {
    const ka = chave(a), kb = chave(b);
    const c = ka < kb ? -1 : ka > kb ? 1 : b.t.id - a.t.id;
    return ordem.asc ? c : -c;
  });
  const ordenar = (g: Transacao[]) => [...g].sort((a, b) => {
    const c = ordem.col === "valor" ? efeito(a) * a.valor_centavos - efeito(b) * b.valor_centavos
      : ordem.col === "descricao" ? a.descricao.localeCompare(b.descricao) : a.data.localeCompare(b.data);
    return ordem.asc ? c : -c;
  });
  const Th = ({ col, children, num }: { col: Coluna; children: string; num?: boolean }) => (
    <th className={`ordenavel${num ? " num" : ""}`} onClick={() => ordenarPor(col)}
      aria-sort={ordem.col === col ? (ordem.asc ? "ascending" : "descending") : "none"}>
      {children}{ordem.col === col ? (ordem.asc ? " ▲" : " ▼") : ""}</th>
  );
  // A fatura que vence no mês pode ter compras do mês anterior (feitas antes do fechamento).
  const fatura = (id: number) => painel.dados?.cartoes.find((c) => c.id === id)?.fatura_total;
  const recarregar = () => { lista.recarregar(); painel.recarregar(); };

  async function apagar(t: Transacao) {
    const aviso = t.tipo === "transferencia" ? " As duas pontas da transferência serão apagadas." : "";
    if (!confirm(`Apagar "${t.descricao}"?${aviso}`)) return;
    // Conta que se repete (ex.: cancelou a internet): oferece apagar os meses seguintes ainda não pagos.
    const proximas = !!t.recorrencia_id &&
      confirm("Esta conta se repete todo mês. Apagar também os próximos meses ainda não pagos?\n\nOK = apaga este e os próximos · Cancelar = só este");
    await api.apagarTransacao(t.id, proximas);
    recarregar();
  }

  const linha = (t: Transacao, filho = false) => (
    <tr key={t.id} className={filho ? "filho" : undefined}>
              <td>{t.pago ? <span className="ok" title="Paga">✓</span>
                : (t.tipo === "despesa" || t.tipo === "receita")
                  ? <button className="pagar" onClick={() => setPagando(t)}>{t.tipo === "receita" ? "Receber" : "Pagar"}</button>
                  : <span className="pendente" title="Pendente">!</span>}</td>
              <td>{dataBR(t.data)}</td>
              <td>{t.descricao}{t.recorrencia_id && <span className="repete" title="Repete todo mês"> ↻</span>}
                {t.tags && <small className="tags"> {t.tags}</small>}</td>
              <td>{t.categoria ?? (t.itens ? `${t.itens} itens` : TIPOS.find((x) => x.tipo === t.tipo)?.nome ?? "—")}</td>
              <td>{t.conta ?? t.cartao}</td>
              <td className={`num ${efeito(t) > 0 ? "pos" : "neg"}`}>{reais(efeito(t) * t.valor_centavos)}</td>
              <td className="acoes"><button className="link" onClick={() => setEditando(t)}>Editar</button>
                <button className="link" onClick={() => apagar(t)} aria-label="Apagar">Apagar</button></td>
    </tr>
  );

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
      <label className="chave agrupar"><input type="checkbox" checked={agrupar} onChange={(e) => setAgrupar(e.target.checked)} />
        Agrupar compras de cartão por cartão</label>
      <table className="tabela">
        <thead><tr><Th col="situacao">Situação</Th><Th col="data">Data</Th><Th col="descricao">Descrição</Th>
          <Th col="categoria">Categoria</Th><Th col="conta">Conta / cartão</Th>
          <Th col="valor" num>Valor</Th><th /></tr></thead>
        <tbody>
          {lista.dados?.length === 0 && <tr><td colSpan={7} className="vazio">Nenhuma transação neste mês.</td></tr>}
          {itens.map(({ t, grupo }) => {
            if (!grupo) return linha(t);
            const total = grupo.reduce((s, x) => s + efeito(x) * x.valor_centavos, 0);
            const aberto = abertos.includes(t.cartao_id!);
            return (
              <Fragment key={`cartao-${t.cartao_id}`}>
                <tr className="grupo-cartao" onClick={() => alternar(t.cartao_id!)}>
                  <td><span className="seta">{aberto ? "▾" : "▸"}</span></td>
                  <td>{dataBR(grupo[grupo.length - 1].data)} a {dataBR(grupo[0].data)}</td>
                  <td><strong>💳 {t.cartao}</strong> <small>· {grupo.length} lançamento{grupo.length > 1 ? "s" : ""}</small></td>
                  <td>Compras do mês<small className="dica-linha">pela data da compra</small></td>
                  <td><Link to={`/cartoes/${t.cartao_id}?mes=${mes}`} onClick={(e) => e.stopPropagation()}>
                    Fatura do mês{fatura(t.cartao_id!) !== undefined && `: ${reais(fatura(t.cartao_id!)!)}`}</Link>
                    <small className="dica-linha">vence no mês; pode ter compras do mês anterior</small></td>
                  <td className={`num ${total > 0 ? "pos" : "neg"}`}><strong>{reais(total)}</strong></td>
                  <td />
                </tr>
                {aberto && ordenar(grupo).map((x) => linha(x, true))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      {editando && <EditarTransacao transacao={editando} aoFechar={() => setEditando(null)}
        aoSalvar={() => { setEditando(null); recarregar(); }} />}
      {pagando && <PagarConta transacao={pagando} aoFechar={() => setPagando(null)}
        aoSalvar={() => { setPagando(null); recarregar(); }} />}
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
    repete: false, meses: "12",
  });
  const [erro, setErro] = useState<string | null>(null);
  const muda = (campo: string, valor: unknown) => setF({ ...f, [campo]: valor });
  const info = TIPOS.find((t) => t.tipo === tipo)!;
  const tipoCategoria = tipo === "receita" ? "receita" : "despesa";
  const noCartao = tipo === "despesa_cartao" || tipo === "credito_cartao";
  const usaCategoria = tipo === "despesa" || tipo === "receita" || noCartao;
  const usaCartao = noCartao || tipo === "pagamento_fatura";
  const usaConta = !noCartao;

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
        repetir_meses: (tipo === "despesa" || tipo === "receita") && f.repete ? Number(f.meses) || 1 : 1,
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
        {(tipo === "despesa" || tipo === "receita") && (
          <div className="repetir">
            <label className="chave"><input type="checkbox" checked={f.repete} onChange={(e) => muda("repete", e.target.checked)} />
              Repete todo mês (luz, água, internet, plano de saúde…)</label>
            {f.repete && (<>
              <label className="meses">por <input type="number" min={2} max={60} value={f.meses}
                onChange={(e) => muda("meses", e.target.value)} /> meses</label>
              <p className="dica">Cria um lançamento por mês, a partir da data acima.
                {f.pago && " Só o primeiro fica como pago;"} os seguintes ficam "a pagar". Para contas que variam,
                lance um valor estimado e informe o real na hora de pagar.</p>
            </>)}
          </div>
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
