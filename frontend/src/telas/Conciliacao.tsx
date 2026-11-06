import { useRef, useState } from "react";
import { api, type Categoria, type Conciliacao as Resultado } from "../api";
import { useDados } from "../componentes/useDados";
import { dataBR, reais } from "../formato";

/**
 * Conciliação bancária: sobe um extrato OFX de uma conta e cruza com os lançamentos
 * já cadastrados. Mostra quatro baldes — casado, divergência, só no banco, só no app —
 * e deixa marcar os casados como conferidos e lançar o que faltou.
 */
export default function Conciliacao() {
  const contas = useDados(() => api.contas(), []).dados ?? [];
  const categorias = useDados(() => api.categorias(), []).dados ?? [];
  const ativas = contas.filter((c) => c.ativa);

  const [contaId, setContaId] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [res, setRes] = useState<Resultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const inputArquivo = useRef<HTMLInputElement>(null);

  // Seleções do usuário sobre o resultado.
  const [conferir, setConferir] = useState<Set<number>>(new Set());          // ids de lançamentos a marcar conferido
  const [lancar, setLancar] = useState<Record<string, number | "">>({});      // fitid -> categoria escolhida (lançar)
  const [aplicando, setAplicando] = useState(false);
  const [feito, setFeito] = useState<string | null>(null);

  async function analisar(file = arquivo) {
    if (!contaId || !file) return;
    setCarregando(true); setErro(null); setFeito(null);
    try {
      const r = await api.analisarConciliacao(file, Number(contaId));
      setRes(r);
      setConferir(new Set(r.casados.map((c) => c.app.id)));   // casados vêm pré-marcados
      setLancar({});
    } catch (e) { setErro((e as Error).message); setRes(null); }
    finally { setCarregando(false); }
  }

  function escolherArquivo(f: File | null) {
    setArquivo(f); setRes(null); setFeito(null);
    if (f && contaId) analisar(f);
  }

  const totalLancar = Object.values(lancar).filter((v) => v !== "").length;

  async function aplicar() {
    if (!res) return;
    setAplicando(true); setErro(null);
    try {
      const criar = (res.so_banco)
        .filter((b) => lancar[b.fitid] !== undefined && lancar[b.fitid] !== "")
        .map((b) => ({ data: b.data, valor_centavos: b.valor_centavos,
                       descricao: b.descricao, categoria_id: Number(lancar[b.fitid]) }));
      const saida = await api.aplicarConciliacao({
        conta_id: Number(contaId), conferir_ids: [...conferir], criar });
      setFeito(`Pronto: ${saida.conferidos} conferido(s) e ${saida.criados} lançado(s).`);
      await analisar();   // recarrega para mostrar o estado novo
    } catch (e) { setErro((e as Error).message); }
    finally { setAplicando(false); }
  }

  return (
    <>
      <header className="topo"><h1>Conciliação bancária</h1></header>

      <div className="cartao-painel espaco conc-topo">
        <label>Conta
          <select value={contaId} onChange={(e) => { setContaId(e.target.value); setRes(null); }}>
            <option value="">Escolha…</option>
            {ativas.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select>
        </label>
        <label>Extrato (.ofx)
          <input ref={inputArquivo} type="file" accept=".ofx,.OFX,text/*,application/x-ofx"
            disabled={!contaId}
            onChange={(e) => escolherArquivo(e.target.files?.[0] ?? null)} />
        </label>
        {carregando && <span className="dica">Lendo o extrato…</span>}
      </div>

      <p className="dica">
        Exporte o extrato da conta em <b>OFX</b> pelo app/internet banking. O app casa cada linha
        por <b>data (± {res?.tolerancia_dias ?? 3} dias)</b> e <b>valor</b>. Nada é gravado até você clicar em
        "Aplicar".
      </p>

      {erro && <p className="erro">{erro}</p>}
      {feito && <p className="conc-ok">{feito}</p>}

      {res && (
        <>
          <div className="energia-kpis espaco">
            <Kpi titulo="Linhas no extrato" n={res.resumo.linhas_extrato} />
            <Kpi titulo="Casados" n={res.resumo.casados} cor="#4ade80" />
            <Kpi titulo="Divergências" n={res.resumo.divergencias} cor="#fbbf24" />
            <Kpi titulo="Só no banco" n={res.resumo.so_banco} cor="#60a5fa" />
            <Kpi titulo="Só no app" n={res.resumo.so_app} cor="#a1a1aa" />
          </div>

          <SecaoCasados res={res} conferir={conferir} setConferir={setConferir} />
          <SecaoDivergencias res={res} conferir={conferir} setConferir={setConferir} />
          <SecaoSoBanco res={res} categorias={categorias} lancar={lancar} setLancar={setLancar} />
          <SecaoSoApp res={res} />

          <div className="conc-aplicar">
            <span className="dica">Vai marcar <b>{conferir.size}</b> como conferido(s) e lançar <b>{totalLancar}</b>.</span>
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
  return <span className={centavos < 0 ? "neg" : "pos"}>{reais(centavos)}</span>;
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
      <h3>✅ Casados <small>· batem data e valor</small></h3>
      <table className="tabela">
        <thead><tr>
          <th><input type="checkbox" checked={todos} onChange={marcarTodos} /></th>
          <th>Data</th><th>Extrato</th><th className="num">Valor</th><th>Lançamento no app</th>
        </tr></thead>
        <tbody>
          {res.casados.map((c) => (
            <tr key={c.banco.fitid}>
              <td><input type="checkbox" checked={conferir.has(c.app.id)}
                onChange={() => alternar(c.app.id)} /></td>
              <td>{dataBR(c.banco.data)}</td>
              <td>{c.banco.descricao}</td>
              <td className="num"><Valor centavos={c.banco.valor_centavos} /></td>
              <td>{c.app.descricao}{c.app.conferido ? " ✓" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function SecaoDivergencias({ res, conferir, setConferir }: {
  res: Resultado; conferir: Set<number>; setConferir: (s: Set<number>) => void;
}) {
  if (!res.divergencias.length) return null;
  const alternar = (id: number) => {
    const s = new Set(conferir); s.has(id) ? s.delete(id) : s.add(id); setConferir(s);
  };
  return (
    <section className="cartao-painel espaco">
      <h3>⚠️ Divergências <small>· valor parecido, confira se é o mesmo lançamento</small></h3>
      <table className="tabela">
        <thead><tr>
          <th>Data</th><th>Extrato</th><th className="num">Banco</th>
          <th>No app</th><th className="num">App</th><th className="num">Diferença</th>
          <th>É o mesmo?</th>
        </tr></thead>
        <tbody>
          {res.divergencias.map((d) => (
            <tr key={d.banco.fitid}>
              <td>{dataBR(d.banco.data)}</td>
              <td>{d.banco.descricao}</td>
              <td className="num"><Valor centavos={d.banco.valor_centavos} /></td>
              <td>{d.app.descricao}</td>
              <td className="num"><Valor centavos={d.app.valor_centavos} /></td>
              <td className="num">{reais(d.diferenca_centavos)}</td>
              <td><input type="checkbox" checked={conferir.has(d.app.id)}
                onChange={() => alternar(d.app.id)} /> conferir</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function SecaoSoBanco({ res, categorias, lancar, setLancar }: {
  res: Resultado; categorias: Categoria[];
  lancar: Record<string, number | "">; setLancar: (m: Record<string, number | "">) => void;
}) {
  if (!res.so_banco.length) return null;
  const mudar = (fitid: string, v: string) => setLancar({ ...lancar, [fitid]: v === "" ? "" : Number(v) });
  return (
    <section className="cartao-painel espaco">
      <h3>🟡 Só no banco <small>· veio no extrato, falta lançar</small></h3>
      <table className="tabela">
        <thead><tr>
          <th>Data</th><th>Extrato</th><th className="num">Valor</th><th>Tipo</th><th>Categoria (para lançar)</th>
        </tr></thead>
        <tbody>
          {res.so_banco.map((b) => {
            const receita = b.valor_centavos > 0;
            const opcoes = categorias.filter((c) => c.tipo === (receita ? "receita" : "despesa"));
            return (
              <tr key={b.fitid}>
                <td>{dataBR(b.data)}</td>
                <td>{b.descricao}</td>
                <td className="num"><Valor centavos={b.valor_centavos} /></td>
                <td>{receita ? "Receita" : "Despesa"}</td>
                <td>
                  <SelecCategoria opcoes={opcoes} valor={lancar[b.fitid] ?? ""}
                    aoMudar={(v) => mudar(b.fitid, v)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="dica">Escolha uma categoria para a linha ser lançada ao aplicar. Deixe em branco para pular por enquanto.</p>
    </section>
  );
}

function SelecCategoria({ opcoes, valor, aoMudar }: {
  opcoes: Categoria[]; valor: number | ""; aoMudar: (v: string) => void;
}) {
  const maes = opcoes.filter((c) => c.pai_id === null);
  return (
    <select value={valor} onChange={(e) => aoMudar(e.target.value)}>
      <option value="">— não lançar —</option>
      {maes.map((m) => {
        const filhas = opcoes.filter((c) => c.pai_id === m.id);
        return filhas.length ? (
          <optgroup key={m.id} label={m.nome}>
            <option value={m.id}>{m.nome} (geral)</option>
            {filhas.map((f) => <option key={f.id} value={f.id}>{f.nome}</option>)}
          </optgroup>
        ) : <option key={m.id} value={m.id}>{m.nome}</option>;
      })}
    </select>
  );
}

function SecaoSoApp({ res }: { res: Resultado }) {
  if (!res.so_app.length) return null;
  return (
    <section className="cartao-painel espaco">
      <h3>🔵 Só no app <small>· lançado, mas não apareceu no extrato</small></h3>
      <table className="tabela">
        <thead><tr><th>Data</th><th>Descrição</th><th className="num">Valor</th><th>Situação</th></tr></thead>
        <tbody>
          {res.so_app.map((a) => (
            <tr key={a.id}>
              <td>{dataBR(a.data)}</td>
              <td>{a.descricao}</td>
              <td className="num"><Valor centavos={a.valor_centavos} /></td>
              <td>{a.conferido ? "conferido" : "a conferir"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="dica">Pode ser lançamento com data diferente, ainda não compensado, ou que não deveria estar aqui. Revise na tela Transações.</p>
    </section>
  );
}
