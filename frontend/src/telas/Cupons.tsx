import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type Categoria, type CupomLido } from "../api";
import { useDados } from "../componentes/useDados";
import { dataBR, reais } from "../formato";

/** Quantidade em milésimos -> "0,172 KG" ou "2 UN". */
const qtd = (mil: number, un: string) =>
  `${(mil / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 3 })} ${un}`;

export default function Cupons() {
  const categorias = useDados(api.categorias);
  const contas = useDados(api.contas);
  const cartoes = useDados(api.cartoes);
  const [qr, setQr] = useState<Awaited<ReturnType<typeof api.lerQR>> | null>(null);
  const [lido, setLido] = useState<CupomLido | null>(null);
  const [cats, setCats] = useState<Record<number, string>>({});
  const [pagoCom, setPagoCom] = useState("");
  const [data, setData] = useState("");
  const [descricao, setDescricao] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function enviarFoto(f: File | undefined) {
    if (!f) return;
    setMsg(null); setQr(null);
    try {
      const r = await api.lerQR(f);
      setQr(r);
      if (!r.notas.length) setMsg({ ok: false, texto: "Não achei QR de nota nesta imagem. Se for um pedido sem QR, me peça para ler a foto." });
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
  }

  async function enviarPagina(f: File | undefined) {
    if (!f) return;
    setMsg(null); setLido(null);
    try {
      const r = await api.lerCupom(f);
      setLido(r);
      setCats(Object.fromEntries(r.cupom.itens.map((i) => [i.seq, i.categoria_sugerida ? String(i.categoria_sugerida) : ""])));
      setData(r.cupom.emissao ? r.cupom.emissao.slice(0, 10) : "");
      setDescricao(r.cupom.emitente.nome);
      const p = r.pagamento_sugerido;
      setPagoCom(p?.cartao_id ? `cartao:${p.cartao_id}` : p?.conta_id ? `conta:${p.conta_id}` : "");
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
  }

  async function lancar() {
    if (!lido) return;
    if (!pagoCom) return setMsg({ ok: false, texto: "Escolha a conta ou o cartão usado no pagamento." });
    const [tipo, id] = pagoCom.split(":");
    setOcupado(true);
    try {
      const r = await api.lancarCupom({
        cupom: lido.cupom, arquivo: lido.arquivo, data: data || null, descricao,
        conta_id: tipo === "conta" ? Number(id) : null, cartao_id: tipo === "cartao" ? Number(id) : null,
        categorias: Object.fromEntries(Object.entries(cats).filter(([, v]) => v).map(([k, v]) => [k, Number(v)])),
      });
      setMsg({ ok: true, texto: `Lançado: ${reais(r.valor_centavos)} em ${r.itens} itens. Veja em Transações.` });
      setLido(null); setQr(null);
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
    finally { setOcupado(false); }
  }

  const c = lido?.cupom;
  return (
    <>
      <header className="topo"><h1>Cupons</h1></header>

      <section className="passos">
        <div className="cartao-painel">
          <h3>1. Foto do cupom com QR</h3>
          <p className="suave">O app lê o QR e mostra o link da SEFAZ. Abra, resolva o captcha e,
            com os itens na tela, aperte <b>Ctrl+S</b>.</p>
          <input type="file" accept="image/*" onChange={(e) => enviarFoto(e.target.files?.[0])} />
          {qr?.notas.map((n) => (
            <p key={n.chave}>Nota nº {n.numero} · {n.valida ? "chave válida" : "chave com erro"}{" "}
              {n.url_consulta && <a href={n.url_consulta} target="_blank" rel="noreferrer">Abrir na SEFAZ ↗</a>}</p>
          ))}
        </div>
        <div className="cartao-painel">
          <h3>2. Página salva (.html) ou pedido lido (.json)</h3>
          <p className="suave">Escolha o arquivo salvo no passo 1, ou o .json que o Claude gerou de um pedido sem QR.</p>
          <input type="file" accept=".html,.htm,.json" onChange={(e) => enviarPagina(e.target.files?.[0])} />
        </div>
      </section>

      {msg && <p className={msg.ok ? "aviso-ok" : "erro"}>{msg.texto}</p>}

      {c && lido && (
        <section className="cartao-painel espaco">
          <h3>{c.emitente.nome || "Estabelecimento"}</h3>
          <small>{c.emitente.cnpj && `CNPJ ${c.emitente.cnpj} · `}{c.numero && `Nota ${c.numero} · `}
            {c.emissao && dataBR(c.emissao.slice(0, 10))}</small>
          {lido.ja_lancado && <p className="erro">Este cupom já foi lançado{lido.ja_lancado.data ? ` em ${dataBR(lido.ja_lancado.data)}` : ""}.</p>}
          <p className={lido.conferencia.confere ? "aviso-ok" : "erro"}>
            {lido.conferencia.confere
              ? `✓ Itens conferem com o total: ${reais(lido.conferencia.valor_pagar)}`
              : `Atenção: itens somam ${reais(lido.conferencia.liquido_itens)}, mas o cupom diz ${reais(lido.conferencia.valor_pagar)}.`}
          </p>
          <div className="form destaque">
            <label>💳 Pago com <small>(a página da SEFAZ não informa a forma de pagamento)</small>
              <select value={pagoCom} onChange={(e) => setPagoCom(e.target.value)}>
                <option value="">Escolha a conta ou o cartão…</option>
                <optgroup label="Contas (débito, Pix, dinheiro)">
                  {contas.dados?.filter((x) => x.ativa).map((x) => <option key={x.id} value={`conta:${x.id}`}>{x.nome}</option>)}
                </optgroup>
                <optgroup label="Cartões de crédito">
                  {cartoes.dados?.filter((x) => x.ativo).map((x) => <option key={x.id} value={`cartao:${x.id}`}>{x.nome} · final {x.final}</option>)}
                </optgroup>
              </select></label>
            {cartoes.dados?.length === 0 && <p className="suave">Nenhum cartão cadastrado ainda. <Link to="/cartoes">Cadastrar cartão de crédito</Link></p>}
          </div>
          <table className="tabela">
            <thead><tr><th>Item</th><th>Qtde.</th><th>Unit.</th><th>Total</th><th>Categoria</th></tr></thead>
            <tbody>
              {c.itens.map((i) => (
                <tr key={i.seq}>
                  <td>{i.descricao}{i.codigo && <small> · cód. {i.codigo}</small>}</td>
                  <td>{qtd(i.quantidade_milesimos, i.unidade)}</td>
                  <td>{reais(i.preco_unitario_centavos)}</td>
                  <td>{reais(i.valor_total_centavos - i.desconto_centavos)}
                    {i.desconto_centavos > 0 && <small> (−{reais(i.desconto_centavos)})</small>}</td>
                  <td><Categorias lista={categorias.dados ?? []} valor={cats[i.seq] ?? ""}
                    aoMudar={(v) => setCats({ ...cats, [i.seq]: v })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="form espaco">
            <div className="duas">
              <label>Data<input type="date" value={data} onChange={(e) => setData(e.target.value)} /></label>
              <label>Descrição<input value={descricao} onChange={(e) => setDescricao(e.target.value)} /></label>
            </div>
            <p className="suave">Item sem categoria recebe a categoria mais usada neste cupom.</p>
            <footer><button onClick={() => setLido(null)}>Descartar</button>
              <button className="primario" disabled={ocupado || !!lido.ja_lancado} onClick={lancar}>Lançar cupom</button></footer>
          </div>
        </section>
      )}
    </>
  );
}

function Categorias({ lista, valor, aoMudar }: { lista: Categoria[]; valor: string; aoMudar: (v: string) => void }) {
  const maes = lista.filter((c) => c.pai_id === null && c.tipo === "despesa");
  return (
    <select value={valor} onChange={(e) => aoMudar(e.target.value)}>
      <option value="">—</option>
      {maes.map((m) => (
        <optgroup key={m.id} label={m.nome}>
          <option value={m.id}>{m.nome} (geral)</option>
          {lista.filter((c) => c.pai_id === m.id).map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
        </optgroup>
      ))}
    </select>
  );
}
