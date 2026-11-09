import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type Categoria, type CupomLido } from "../api";
import { useDados } from "../componentes/useDados";
import { dataBR, paraCentavos, reais } from "../formato";

/** Centavos -> "4,99" (sem o R$), para editar dentro da tabela. */
const valorEdit = (centavos: number) => (centavos / 100).toFixed(2).replace(".", ",");

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
  const [soPrecos, setSoPrecos] = useState(false);
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
      setSoPrecos(!!r.despesa_parecida);   // a despesa já está no app: só os preços
      const p = r.pagamento_sugerido;
      setPagoCom(p?.cartao_id ? `cartao:${p.cartao_id}` : p?.conta_id ? `conta:${p.conta_id}` : "");
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
  }

  async function lancar() {
    if (!lido) return;
    if (!soPrecos && !pagoCom) return setMsg({ ok: false, texto: "Escolha a conta ou o cartão usado no pagamento." });
    const [tipo, id] = pagoCom.split(":");
    setOcupado(true);
    try {
      const r = await api.lancarCupom({
        cupom: lido.cupom, arquivo: lido.arquivo, data: data || null, descricao,
        conta_id: tipo === "conta" ? Number(id) : null, cartao_id: tipo === "cartao" ? Number(id) : null,
        categorias: Object.fromEntries(Object.entries(cats).filter(([, v]) => v).map(([k, v]) => [k, Number(v)])),
        so_precos: soPrecos,
      });
      setMsg({ ok: true, texto: r.so_precos
        ? `Preços registrados: ${r.itens} itens (${reais(r.valor_centavos)}). Nenhuma despesa foi criada.`
        : `Lançado: ${reais(r.valor_centavos)} em ${r.itens} itens. Veja em Transações.` });
      setLido(null); setQr(null);
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
    finally { setOcupado(false); }
  }

  /** Corrige um item na tela antes de salvar (OCR pode errar nome, quantidade ou valor). */
  function editarItem(seq: number, campo: Partial<CupomLido["cupom"]["itens"][number]>) {
    setLido((l) => l && { ...l, cupom: { ...l.cupom, itens: l.cupom.itens.map((i) => (i.seq === seq ? { ...i, ...campo } : i)) } });
  }

  const c = lido?.cupom;
  // Conferência AO VIVO: recalcula enquanto o João corrige os itens.
  const somaItens = c ? c.itens.reduce((s, i) => s + i.valor_total_centavos - i.desconto_centavos, 0) : 0;
  const confere = c ? somaItens === c.valor_pagar_centavos : false;
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
        <div className="cartao-painel">
          <h3>📷 Cupom sem QR (foto ou PDF)</h3>
          <p className="suave">Pedido impresso sem QR (ex.: Frescor): mande a foto (.jpg/.png) ou o PDF. O app lê os
            itens sozinho e você confere/corrige antes de salvar.</p>
          <input type="file" accept="image/*,.pdf" onChange={(e) => enviarPagina(e.target.files?.[0])} />
          <p className="suave"><small>Primeira vez? Rode uma vez <code>scripts\ler_cupom_por_foto.bat</code> para ligar a
            leitura por foto (grátis e offline).</small></p>
        </div>
      </section>

      {msg && <p className={msg.ok ? "aviso-ok" : "erro"}>{msg.texto}</p>}

      {c && lido && (
        <section className="cartao-painel espaco">
          <h3>{c.emitente.nome || "Estabelecimento"}</h3>
          <small>{c.emitente.cnpj && `CNPJ ${c.emitente.cnpj} · `}{c.numero && `Nota ${c.numero} · `}
            {c.emissao && dataBR(c.emissao.slice(0, 10))}</small>
          {lido.ja_lancado && <p className="erro">Este cupom já foi {lido.ja_lancado.so_precos ? "registrado (só preços)" : "lançado"}
            {lido.ja_lancado.data ? ` em ${dataBR(lido.ja_lancado.data)}` : ""}.</p>}
          <p className={confere ? "aviso-ok" : "erro"}>
            {confere
              ? `✓ Itens conferem com o total: ${reais(c.valor_pagar_centavos)}`
              : `Atenção: itens somam ${reais(somaItens)}, mas o cupom diz ${reais(c.valor_pagar_centavos)} (diferença de ${reais(Math.abs(somaItens - c.valor_pagar_centavos))}).`}
          </p>
          {c.origem === "foto" && <p className="dica">Li o cupom por foto. Confira os itens abaixo e
            <b> corrija o que o leitor errou</b> (nome, quantidade ou valor) antes de salvar.</p>}
          <fieldset className="modo-cupom">
            <label className="chave"><input type="radio" checked={!soPrecos} onChange={() => setSoPrecos(false)} />
              <span><b>Lançar como despesa</b> · compra nova, ainda não está no app</span></label>
            <label className="chave"><input type="radio" checked={soPrecos} onChange={() => setSoPrecos(true)} />
              <span><b>Só registrar os preços</b> · a despesa já está no app (ex.: veio do Mobills)</span></label>
            {lido.despesa_parecida && (
              <p className="dica">Achei no app <b>{lido.despesa_parecida.descricao}</b> de {reais(lido.despesa_parecida.valor_centavos)} em{" "}
                {dataBR(lido.despesa_parecida.data)}{lido.despesa_parecida.onde ? ` (${lido.despesa_parecida.onde})` : ""}.
                Por isso sugeri só registrar os preços, para não contar a compra duas vezes.</p>
            )}
          </fieldset>
          {!soPrecos && <div className="form destaque">
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
          </div>}
          <table className="tabela cupom-itens">
            <thead><tr><th>Item</th><th>Qtde.</th><th>Un.</th><th>Unit.</th><th>Total</th><th>Categoria</th></tr></thead>
            <tbody>
              {c.itens.map((i) => (
                <tr key={`${lido.arquivo}-${i.seq}`}>
                  <td><input className="cel-nome" defaultValue={i.descricao}
                    onChange={(e) => editarItem(i.seq, { descricao: e.target.value })} />
                    {i.codigo && <small> cód. {i.codigo}</small>}</td>
                  <td><input className="cel-num" type="number" step="0.001" min="0"
                    defaultValue={i.quantidade_milesimos / 1000}
                    onChange={(e) => editarItem(i.seq, { quantidade_milesimos: Math.round(Number(e.target.value) * 1000) })} /></td>
                  <td><select value={i.unidade} onChange={(e) => editarItem(i.seq, { unidade: e.target.value })}>
                    <option>UN</option><option>KG</option></select></td>
                  <td><input className="cel-num" defaultValue={valorEdit(i.preco_unitario_centavos)}
                    onChange={(e) => { const v = paraCentavos(e.target.value); if (v !== null) editarItem(i.seq, { preco_unitario_centavos: v }); }} /></td>
                  <td><input className="cel-num" defaultValue={valorEdit(i.valor_total_centavos)}
                    onChange={(e) => { const v = paraCentavos(e.target.value); if (v !== null) editarItem(i.seq, { valor_total_centavos: v }); }} />
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
              <button className="primario" disabled={ocupado || !!lido.ja_lancado} onClick={lancar}>{soPrecos ? "Registrar preços" : "Lançar cupom"}</button></footer>
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
