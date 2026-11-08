import { useState } from "react";
import { api, type Categoria, type ConciliacaoFatura as Resultado } from "../api";
import SeletorCategoria from "../componentes/SeletorCategoria";
import SeletorMes from "../componentes/SeletorMes";
import { useDados } from "../componentes/useDados";
import { dataBR, mesAtual, paraCentavos, reais } from "../formato";

/**
 * Conciliação da FATURA do cartão: sobe o arquivo da fatura (CSV do C6, por ora) e
 * cruza com os lançamentos daquela competência. O par é por VALOR (a data da compra
 * na fatura não bate com a competência no app, por causa das parcelas).
 */
export default function ConciliacaoFatura({ categorias, aoCriarCategoria }: {
  categorias: Categoria[]; aoCriarCategoria: (c: Categoria) => void;
}) {
  const cartoes = (useDados(() => api.cartoes(), []).dados ?? []).filter((c) => c.ativo);
  const [cartaoId, setCartaoId] = useState("");
  const [competencia, setCompetencia] = useState(mesAtual());
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [res, setRes] = useState<Resultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const [conferir, setConferir] = useState<Set<number>>(new Set());
  const [lancar, setLancar] = useState<Set<string>>(new Set());
  const [cat, setCat] = useState<Record<string, number | "">>({});
  const [ajuste, setAjuste] = useState<Record<number, string>>({});   // id do app -> valor editado
  const [aplicando, setAplicando] = useState(false);
  const [feito, setFeito] = useState<string | null>(null);

  async function analisar(file = arquivo, cartao = cartaoId, comp = competencia) {
    if (!cartao || !comp || !file) return;
    setCarregando(true); setErro(null); setFeito(null);
    try {
      const r = await api.analisarConciliacaoFatura(file, Number(cartao), comp);
      setRes(r);
      setConferir(new Set(r.casados.map((c) => c.app.id)));
      setLancar(new Set(r.so_fatura.map((l) => l.chave)));   // por padrão, lança o que falta
      setCat({}); setAjuste({});
    } catch (e) { setErro((e as Error).message); setRes(null); }
    finally { setCarregando(false); }
  }

  function escolherArquivo(f: File | null) {
    setArquivo(f); setRes(null); setFeito(null);
    if (f && cartaoId && competencia) analisar(f);
  }

  async function aplicar() {
    if (!res) return;
    setAplicando(true); setErro(null);
    try {
      const criar = res.so_fatura.filter((l) => lancar.has(l.chave)).map((l) => ({
        data: l.data, valor_centavos: l.valor_centavos, descricao: l.descricao,
        categoria_id: cat[l.chave] ? Number(cat[l.chave]) : null,
      }));
      // Divergências em que o usuário acertou o valor: manda o novo valor (com o sinal
      // do lançamento) só quando mudou de verdade e é um número válido.
      const ajustar = res.divergencias.flatMap((x) => {
        const txt = ajuste[x.app.id];
        if (txt === undefined || txt.trim() === "") return [];
        const mag = paraCentavos(txt);
        if (mag === null || mag <= 0 || mag === Math.abs(x.app.valor_centavos)) return [];
        const sinal = x.app.valor_centavos < 0 ? -1 : 1;
        return [{ id: x.app.id, valor_centavos: sinal * mag }];
      });
      const saida = await api.aplicarConciliacaoFatura({
        cartao_id: Number(cartaoId), competencia, conferir_ids: [...conferir],
        criar, ajustar, valor_banco: res.totais.extrato });
      setFeito(`Pronto: ${saida.conferidos} conferido(s)`
        + (saida.ajustados ? `, ${saida.ajustados} valor(es) acertado(s)` : "")
        + `, ${saida.criados} lançado(s)`
        + (saida.valor_banco_gravado ? " e total da fatura gravado." : "."));
      await analisar();
    } catch (e) { setErro((e as Error).message); }
    finally { setAplicando(false); }
  }

  const d = res?.totais.diferenca ?? 0;

  return (
    <>
      <div className="cartao-painel espaco conc-topo">
        <label>Cartão
          <select value={cartaoId} onChange={(e) => { setCartaoId(e.target.value); setRes(null); }}>
            <option value="">Escolha…</option>
            {cartoes.map((c) => <option key={c.id} value={c.id}>{c.nome} · final {c.final}</option>)}
          </select>
        </label>
        <label>Competência (mês de vencimento)
          <SeletorMes mes={competencia} aoMudar={(m) => { setCompetencia(m); setRes(null); }} />
        </label>
        <label>Arquivo da fatura (CSV do C6 ou PDF do BB / Mercado Pago)
          <input type="file" accept=".csv,text/csv,.pdf,application/pdf" disabled={!cartaoId}
            onChange={(e) => escolherArquivo(e.target.files?.[0] ?? null)} />
        </label>
        {carregando && <span className="dica">Lendo a fatura…</span>}
      </div>

      <p className="dica">
        Suba a fatura: <b>CSV</b> do C6 (Faturas → Exportar) ou <b>PDF</b> do Banco do Brasil ou do
        Mercado Pago (como você baixa do app/internet banking). O app casa cada linha
        pelo <b>valor</b> dentro da competência escolhida — a data da compra e a parcela servem só de
        desempate. A linha de pagamento da fatura fica de fora (ela é o "Pagamento de fatura" na conta).
        Nada é gravado até você clicar em "Aplicar".
      </p>

      {erro && <p className="erro">{erro}</p>}
      {feito && <p className="conc-ok">{feito}</p>}

      {res && (
        <>
          <div className={`destaque conferencia espaco ${d === 0 ? "" : ""}`}>
            <span>Total no app: <b>{reais(res.totais.app)}</b></span>
            <span> · Total na fatura: <b>{reais(res.totais.extrato)}</b></span>
            {d === 0
              ? <span className="aviso-ok"> · ✓ Bate com a fatura</span>
              : <span className="erro"> · Diferença de {reais(Math.abs(d))}: {d > 0
                  ? "o app tem a mais (falta um crédito/estorno ou algum valor está maior)."
                  : "falta lançar algo (ou algum valor está menor)."}</span>}
          </div>

          <div className="energia-kpis espaco">
            <Kpi titulo="Linhas na fatura" n={res.resumo.linhas_fatura} />
            <Kpi titulo="Casados" n={res.resumo.casados} cor="#4ade80" />
            <Kpi titulo="Divergências" n={res.resumo.divergencias} cor="#fbbf24" />
            <Kpi titulo="Só na fatura" n={res.resumo.so_fatura} cor="#60a5fa" />
            <Kpi titulo="Só no app" n={res.resumo.so_app} cor="#a1a1aa" />
          </div>

          <SecaoDivergencias res={res} conferir={conferir} setConferir={setConferir}
            ajuste={ajuste} setAjuste={setAjuste} />
          <SecaoSoFatura res={res} categorias={categorias} lancar={lancar} setLancar={setLancar}
            cat={cat} setCat={setCat} aoCriarCategoria={aoCriarCategoria} />
          <SecaoSoApp res={res} />
          <SecaoCasados res={res} conferir={conferir} setConferir={setConferir} />
          <Pagamentos res={res} />

          <div className="conc-aplicar">
            <span className="dica">Vai conferir <b>{conferir.size}</b> e lançar <b>{lancar.size}</b> na fatura.</span>
            <button className="primario" disabled={aplicando} onClick={aplicar}>
              {aplicando ? "Aplicando…" : "Aplicar conciliação"}</button>
          </div>
        </>
      )}
    </>
  );
}

function Kpi({ titulo, n, cor = "#6b7280" }: { titulo: string; n: number; cor?: string }) {
  return <div><span>{titulo}</span><strong style={{ color: cor }}>{n}</strong></div>;
}

function Valor({ centavos }: { centavos: number }) {
  return <span className={centavos < 0 ? "pos" : ""}>{reais(centavos)}</span>;
}

function Parcela({ p, t }: { p: number | null; t: number | null }) {
  return p && t ? <small className="dica"> · {p}/{t}</small> : null;
}

function SecaoCasados({ res, conferir, setConferir }: {
  res: Resultado; conferir: Set<number>; setConferir: (s: Set<number>) => void;
}) {
  if (!res.casados.length) return null;
  const alternar = (id: number) => {
    const s = new Set(conferir); s.has(id) ? s.delete(id) : s.add(id); setConferir(s);
  };
  const todos = res.casados.every((c) => conferir.has(c.app.id));
  const marcarTodos = () => {
    const s = new Set(conferir);
    res.casados.forEach((c) => todos ? s.delete(c.app.id) : s.add(c.app.id));
    setConferir(s);
  };
  return (
    <section className="cartao-painel espaco">
      <h3>✅ Casados <small>· mesmo valor na fatura e no app</small></h3>
      <table className="tabela">
        <thead><tr>
          <th><input type="checkbox" checked={todos} onChange={marcarTodos} /></th>
          <th>Compra</th><th>Fatura</th><th>No app</th><th className="num">Valor</th>
        </tr></thead>
        <tbody>
          {res.casados.map((c) => (
            <tr key={c.fatura.chave}>
              <td><input type="checkbox" checked={conferir.has(c.app.id)}
                onChange={() => alternar(c.app.id)} /></td>
              <td>{dataBR(c.fatura.data)}</td>
              <td>{c.fatura.descricao}<Parcela p={c.fatura.parcela} t={c.fatura.total_parcelas} /></td>
              <td>{c.app.descricao}{c.app.conferido ? " ✓" : ""}</td>
              <td className="num"><Valor centavos={c.fatura.valor_centavos} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="dica">Marque o que confere — fica salvo como conferido ao aplicar.</p>
    </section>
  );
}

const _mag = (centavos: number) => (Math.abs(centavos) / 100).toFixed(2).replace(".", ",");

function SecaoDivergencias({ res, conferir, setConferir, ajuste, setAjuste }: {
  res: Resultado; conferir: Set<number>; setConferir: (s: Set<number>) => void;
  ajuste: Record<number, string>; setAjuste: (m: Record<number, string>) => void;
}) {
  if (!res.divergencias.length) return null;
  const alternar = (id: number) => {
    const s = new Set(conferir); s.has(id) ? s.delete(id) : s.add(id); setConferir(s);
  };
  // Editar o valor acerta o lançamento e já o dá por conferido ao aplicar.
  const editar = (id: number, texto: string) => {
    setAjuste({ ...ajuste, [id]: texto });
    if (!conferir.has(id)) { const s = new Set(conferir); s.add(id); setConferir(s); }
  };
  return (
    <section className="cartao-painel espaco">
      <h3>⚠️ Divergências <small>· valor parecido, confira se é a mesma compra</small></h3>
      <table className="tabela">
        <thead><tr>
          <th>Compra</th><th>Fatura</th><th className="num">Fatura</th>
          <th>No app</th><th className="num">Valor no app (edite p/ acertar)</th>
          <th className="num">Diferença</th><th>É a mesma?</th>
        </tr></thead>
        <tbody>
          {res.divergencias.map((x) => {
            const txt = ajuste[x.app.id] ?? _mag(x.app.valor_centavos);
            const mudou = (paraCentavos(txt) ?? -1) !== Math.abs(x.app.valor_centavos);
            return (
              <tr key={x.fatura.chave}>
                <td>{dataBR(x.fatura.data)}</td>
                <td>{x.fatura.descricao}<Parcela p={x.fatura.parcela} t={x.fatura.total_parcelas} /></td>
                <td className="num"><Valor centavos={x.fatura.valor_centavos} /></td>
                <td>{x.app.descricao}</td>
                <td className="num">
                  <input className="conc-valor" inputMode="decimal" value={txt}
                    onChange={(e) => editar(x.app.id, e.target.value)} />
                  <button type="button" className="conc-igualar"
                    title="Usar o valor da fatura"
                    onClick={() => editar(x.app.id, _mag(x.fatura.valor_centavos))}>= fatura</button>
                </td>
                <td className="num">{mudou ? "—" : reais(x.diferenca_centavos)}</td>
                <td><input type="checkbox" checked={conferir.has(x.app.id)}
                  onChange={() => alternar(x.app.id)} /> conferir</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="dica">Se a diferença é só um arredondamento (ex.: R$ 0,01), edite o valor no app —
        ou clique em <b>= fatura</b> — e marque <b>conferir</b>. Ao aplicar, o valor é acertado.</p>
    </section>
  );
}

function SecaoSoFatura({ res, categorias, lancar, setLancar, cat, setCat, aoCriarCategoria }: {
  res: Resultado; categorias: Categoria[];
  lancar: Set<string>; setLancar: (s: Set<string>) => void;
  cat: Record<string, number | "">; setCat: (m: Record<string, number | "">) => void;
  aoCriarCategoria: (c: Categoria) => void;
}) {
  if (!res.so_fatura.length) return null;
  const alternar = (chave: string) => {
    const s = new Set(lancar); s.has(chave) ? s.delete(chave) : s.add(chave); setLancar(s);
  };
  return (
    <section className="cartao-painel espaco">
      <h3>🟡 Só na fatura <small>· veio na fatura, falta lançar no cartão</small></h3>
      <table className="tabela">
        <thead><tr>
          <th>Lançar?</th><th>Compra</th><th>Descrição</th><th className="num">Valor</th><th>Categoria</th>
        </tr></thead>
        <tbody>
          {res.so_fatura.map((l) => (
            <tr key={l.chave}>
              <td><input type="checkbox" checked={lancar.has(l.chave)} onChange={() => alternar(l.chave)} /></td>
              <td>{dataBR(l.data)}</td>
              <td>{l.descricao}<Parcela p={l.parcela} t={l.total_parcelas} /></td>
              <td className="num"><Valor centavos={l.valor_centavos} /></td>
              <td>
                <SeletorCategoria semRotulo vazio="— sem categoria —" tipo="despesa"
                  categorias={categorias.filter((c) => c.tipo === "despesa")}
                  valor={cat[l.chave] ? String(cat[l.chave]) : ""}
                  aoMudar={(v) => setCat({ ...cat, [l.chave]: v === "" ? "" : Number(v) })}
                  aoCriar={aoCriarCategoria} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="dica">Marcadas, entram na fatura como compra do cartão (valor negativo vira crédito/estorno),
        já conferidas. A categoria é opcional. Desmarque o que não quer lançar agora.</p>
    </section>
  );
}

function SecaoSoApp({ res }: { res: Resultado }) {
  if (!res.so_app.length) return null;
  return (
    <section className="cartao-painel espaco">
      <h3>🔵 Só no app <small>· lançado, mas não veio nesta fatura</small></h3>
      <table className="tabela">
        <thead><tr><th>Descrição</th><th className="num">Valor</th><th>Situação</th></tr></thead>
        <tbody>
          {res.so_app.map((a) => (
            <tr key={a.id}>
              <td>{a.descricao}<Parcela p={a.parcela} t={a.total_parcelas} /></td>
              <td className="num"><Valor centavos={a.valor_centavos} /></td>
              <td>{a.conferido ? "conferido" : "a conferir"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="dica">Pode estar em outra competência, ou não deveria estar aqui. Revise na fatura/Transações.</p>
    </section>
  );
}

function Pagamentos({ res }: { res: Resultado }) {
  if (!res.pagamentos.length) return null;
  return (
    <section className="cartao-painel espaco">
      <h3>💸 Pagamentos na fatura <small>· fora dos itens (viram "Pagamento de fatura" na conta)</small></h3>
      <table className="tabela">
        <tbody>
          {res.pagamentos.map((p, i) => (
            <tr key={i}><td>{dataBR(p.data)}</td><td>{p.descricao}</td>
              <td className="num pos">{reais(p.valor_centavos)}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
