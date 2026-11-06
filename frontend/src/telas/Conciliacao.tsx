import { useRef, useState } from "react";
import { api, type Categoria, type Conciliacao as Resultado } from "../api";
import SeletorCategoria from "../componentes/SeletorCategoria";
import { useDados } from "../componentes/useDados";
import { dataBR, reais } from "../formato";

/**
 * Conciliação bancária: sobe um extrato OFX de uma conta e cruza com os lançamentos
 * já cadastrados. Mostra quatro baldes — casado, divergência, só no banco, só no app —
 * e deixa marcar os casados como conferidos e lançar o que faltou.
 */
export default function Conciliacao() {
  const contas = useDados(() => api.contas(), []).dados ?? [];
  const catDados = useDados(() => api.categorias(), []);
  const [extraCats, setExtraCats] = useState<Categoria[]>([]);
  const categorias = [...(catDados.dados ?? []), ...extraCats];
  const ativas = contas.filter((c) => c.ativa);

  const [contaId, setContaId] = useState("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [res, setRes] = useState<Resultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const inputArquivo = useRef<HTMLInputElement>(null);

  // Seleções do usuário sobre o resultado.
  const [conferir, setConferir] = useState<Set<number>>(new Set());          // ids de lançamentos a marcar conferido
  const [lancar, setLancar] = useState<Record<string, number | "">>({});      // fitid -> categoria escolhida (lançar)
  const [descr, setDescr] = useState<Record<string, string>>({});             // fitid -> descrição ajustada (só no banco)
  const [descrApp, setDescrApp] = useState<Record<number, string>>({});       // id do lançamento -> descrição ajustada (casado/divergência)
  const [aplicando, setAplicando] = useState(false);
  const [feito, setFeito] = useState<string | null>(null);

  async function analisar(files = arquivos) {
    if (!contaId || !files.length) return;
    setCarregando(true); setErro(null); setFeito(null);
    try {
      const r = await api.analisarConciliacao(files, Number(contaId));
      setRes(r);
      setConferir(new Set(r.casados.map((c) => c.app.id)));   // casados vêm pré-marcados
      setLancar({}); setDescr({}); setDescrApp({});
    } catch (e) { setErro((e as Error).message); setRes(null); }
    finally { setCarregando(false); }
  }

  function escolherArquivos(fs: File[]) {
    setArquivos(fs); setRes(null); setFeito(null);
    if (fs.length && contaId) analisar(fs);
  }

  const totalLancar = Object.values(lancar).filter((v) => v !== "").length;

  async function aplicar() {
    if (!res) return;
    setAplicando(true); setErro(null);
    try {
      const criar = (res.so_banco)
        .filter((b) => lancar[b.fitid] !== undefined && lancar[b.fitid] !== "")
        .map((b) => ({ data: b.data, valor_centavos: b.valor_centavos,
                       descricao: (descr[b.fitid] ?? b.descricao).trim() || b.descricao,
                       categoria_id: Number(lancar[b.fitid]) }));
      // Renomeia os lançamentos que vou conferir e cuja descrição foi ajustada na tela.
      const renomear = [...res.casados, ...res.divergencias]
        .filter((m) => conferir.has(m.app.id))
        .map((m) => ({ id: m.app.id, orig: m.app.descricao, novo: (descrApp[m.app.id] ?? m.app.descricao).trim() }))
        .filter((m) => m.novo && m.novo !== m.orig)
        .map((m) => ({ id: m.id, descricao: m.novo }));
      const saida = await api.aplicarConciliacao({
        conta_id: Number(contaId), conferir_ids: [...conferir], criar, renomear });
      setFeito(`Pronto: ${saida.conferidos} conferido(s), ${saida.renomeados} renomeado(s) e ${saida.criados} lançado(s).`);
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
        <label>Extrato (.ofx) — pode escolher vários meses
          <input ref={inputArquivo} type="file" multiple accept=".ofx,.OFX,text/*,application/x-ofx"
            disabled={!contaId}
            onChange={(e) => escolherArquivos(Array.from(e.target.files ?? []))} />
        </label>
        {arquivos.length > 1 && <span className="dica">{arquivos.length} arquivos selecionados.</span>}
        {carregando && <span className="dica">Lendo o extrato…</span>}
      </div>

      <p className="dica">
        Exporte o extrato da conta em <b>OFX</b> pelo app/internet banking. Se o banco só deixa baixar
        um mês por vez, selecione <b>vários arquivos de uma vez</b> aqui. O app casa cada linha
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

          <SecaoCasados res={res} conferir={conferir} setConferir={setConferir}
            descrApp={descrApp} setDescrApp={setDescrApp} />
          <SecaoDivergencias res={res} conferir={conferir} setConferir={setConferir}
            descrApp={descrApp} setDescrApp={setDescrApp} />
          <SecaoSoBanco res={res} categorias={categorias} lancar={lancar} setLancar={setLancar}
            descr={descr} setDescr={setDescr} aoCriarCategoria={(c) => setExtraCats((e) => [...e, c])} />
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

function SecaoCasados({ res, conferir, setConferir, descrApp, setDescrApp }: {
  res: Resultado; conferir: Set<number>; setConferir: (s: Set<number>) => void;
  descrApp: Record<number, string>; setDescrApp: (m: Record<number, string>) => void;
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
          <th>Data</th><th>Extrato</th><th className="num">Valor</th><th>Lançamento no app (edite se quiser)</th>
        </tr></thead>
        <tbody>
          {res.casados.map((c) => (
            <tr key={c.banco.fitid}>
              <td><input type="checkbox" checked={conferir.has(c.app.id)}
                onChange={() => alternar(c.app.id)} /></td>
              <td>{dataBR(c.banco.data)}</td>
              <td>{c.banco.descricao}</td>
              <td className="num"><Valor centavos={c.banco.valor_centavos} /></td>
              <td><input className="conc-descr" value={descrApp[c.app.id] ?? c.app.descricao}
                onChange={(e) => setDescrApp({ ...descrApp, [c.app.id]: e.target.value })} />
                {c.app.conferido ? " ✓" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="dica">Marque o que confere. Pode ajustar a descrição do lançamento do app — o texto editado é salvo só nos que você conferir.</p>
    </section>
  );
}

function SecaoDivergencias({ res, conferir, setConferir, descrApp, setDescrApp }: {
  res: Resultado; conferir: Set<number>; setConferir: (s: Set<number>) => void;
  descrApp: Record<number, string>; setDescrApp: (m: Record<number, string>) => void;
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
          <th>No app (edite se quiser)</th><th className="num">App</th><th className="num">Diferença</th>
          <th>É o mesmo?</th>
        </tr></thead>
        <tbody>
          {res.divergencias.map((d) => (
            <tr key={d.banco.fitid}>
              <td>{dataBR(d.banco.data)}</td>
              <td>{d.banco.descricao}</td>
              <td className="num"><Valor centavos={d.banco.valor_centavos} /></td>
              <td><input className="conc-descr" value={descrApp[d.app.id] ?? d.app.descricao}
                onChange={(e) => setDescrApp({ ...descrApp, [d.app.id]: e.target.value })} /></td>
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

function SecaoSoBanco({ res, categorias, lancar, setLancar, descr, setDescr, aoCriarCategoria }: {
  res: Resultado; categorias: Categoria[];
  lancar: Record<string, number | "">; setLancar: (m: Record<string, number | "">) => void;
  descr: Record<string, string>; setDescr: (m: Record<string, string>) => void;
  aoCriarCategoria: (c: Categoria) => void;
}) {
  if (!res.so_banco.length) return null;
  const mudarCat = (fitid: string, v: string) => setLancar({ ...lancar, [fitid]: v === "" ? "" : Number(v) });
  return (
    <section className="cartao-painel espaco">
      <h3>🟡 Só no banco <small>· veio no extrato, falta lançar</small></h3>
      <table className="tabela">
        <thead><tr>
          <th>Data</th><th className="num">Valor</th><th>Tipo</th>
          <th>Descrição (edite antes de lançar)</th><th>Categoria (para lançar)</th>
        </tr></thead>
        <tbody>
          {res.so_banco.map((b) => {
            const receita = b.valor_centavos > 0;
            const tipo = receita ? "receita" : "despesa";
            return (
              <tr key={b.fitid}>
                <td>{dataBR(b.data)}</td>
                <td className="num"><Valor centavos={b.valor_centavos} /></td>
                <td>{receita ? "Receita" : "Despesa"}</td>
                <td><input className="conc-descr" value={descr[b.fitid] ?? b.descricao}
                  onChange={(e) => setDescr({ ...descr, [b.fitid]: e.target.value })} /></td>
                <td>
                  <SeletorCategoria semRotulo vazio="— não lançar —" tipo={tipo}
                    categorias={categorias.filter((c) => c.tipo === tipo)}
                    valor={lancar[b.fitid] ? String(lancar[b.fitid]) : ""}
                    aoMudar={(v) => mudarCat(b.fitid, v)} aoCriar={aoCriarCategoria} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="dica">Edite a descrição se quiser, escolha uma categoria e a linha é lançada ao aplicar.
        Deixe a categoria em branco para pular por enquanto. Use "+ Nova categoria…" para criar uma na hora.</p>
    </section>
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
