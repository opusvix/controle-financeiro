import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type ContaPdfLida, type FaturaPdf } from "../api";
import { dataBR, reais } from "../formato";

/** Um número da ficha, ou null se não veio. */
const num = (fc: FaturaPdf["ficha"], k: string) => (typeof fc[k] === "number" ? (fc[k] as number) : null);

/** Resumo do que o leitor achou na fatura, por tipo de conta. */
function resumoFatura(f: FaturaPdf): string {
  const fc = f.ficha;
  if (f.tipo === "energia") {
    const partes = [`${num(fc, "consumo") ?? 0} kWh`];
    if (num(fc, "kwh_compensado")) partes.push(`créditos Solar ${num(fc, "kwh_compensado")} kWh`);
    if (fc["bandeira"] && fc["bandeira"] !== "verde") partes.push(`bandeira ${fc["bandeira"]}`);
    return partes.join(" · ");
  }
  if (f.tipo === "energia_solar")
    return num(fc, "desconto_centavos") ? `economia ${reais(num(fc, "desconto_centavos")!)}` : "crédito solar";
  if (f.tipo === "agua")
    return `${num(fc, "consumo") ?? 0} m³` + (num(fc, "fixo_centavos") ? ` · parte fixa ${reais(num(fc, "fixo_centavos")!)}` : "");
  if (f.tipo === "saude") return `${num(fc, "vidas") ?? 0} vidas · ${f.itens.length} itens`;
  return "";
}

/** Texto da situação de cada arquivo lido (achou lançamento, sem lançamento, senha, erro…). */
function situacao(l: ContaPdfLida): { texto: string; ok: boolean } {
  if (l.status === "senha") return { texto: "🔒 protegido por senha — preencha a senha acima", ok: false };
  if (l.status === "erro") return { texto: `⚠ não consegui ler (${l.mensagem})`, ok: false };
  if (l.status === "sem_leitor") return { texto: "sem leitor para esta conta ainda", ok: false };
  if (!l.lancamento) return { texto: "✗ sem lançamento de mesmo valor no app", ok: false };
  if (l.lancamento.ja_tem_ficha)
    return { texto: `já tem ficha (lançamento de ${dataBR(l.lancamento.data)}) — marque para regravar`, ok: true };
  return { texto: `✓ lançamento de ${dataBR(l.lancamento.data)}`, ok: true };
}

export default function ContasPdf() {
  const [senha, setSenha] = useState("");
  const [lidas, setLidas] = useState<ContaPdfLida[] | null>(null);
  const [marcadas, setMarcadas] = useState<Record<number, boolean>>({});
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const [lendo, setLendo] = useState(false);
  const [gravando, setGravando] = useState(false);

  async function enviar(arquivos: FileList | null) {
    const pdfs = Array.from(arquivos ?? []).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) {
      setMsg({ ok: false, texto: "Não achei nenhum arquivo .pdf no que você escolheu." });
      return;
    }
    setMsg(null); setLidas(null); setLendo(true);
    try {
      const r = await api.analisarContasPdf(pdfs, senha);
      setLidas(r.contas);
      // Já deixo marcado o que achou lançamento e ainda não tem ficha.
      setMarcadas(Object.fromEntries(r.contas.map((l, i) =>
        [i, l.status === "ok" && !!l.lancamento && !l.lancamento.ja_tem_ficha])));
      if (!r.contas.length) setMsg({ ok: false, texto: "Nenhum PDF reconhecido." });
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
    finally { setLendo(false); }
  }

  async function gravar() {
    if (!lidas) return;
    const itens = lidas
      .map((l, i) => ({ l, i }))
      .filter(({ l, i }) => marcadas[i] && l.fatura && l.lancamento)
      .map(({ l }) => ({ fatura: l.fatura!, transacao_id: l.lancamento!.id }));
    if (!itens.length) return setMsg({ ok: false, texto: "Marque ao menos uma fatura para gravar." });
    setGravando(true);
    try {
      const r = await api.gravarContasPdf(itens);
      setMsg({ ok: true, texto: `Pronto: ${r.gravadas} ficha(s) gravada(s). Veja o consumo nos painéis das Contas.` });
      setLidas(null); setMarcadas({});
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
    finally { setGravando(false); }
  }

  const paraGravar = lidas?.filter((_, i) => marcadas[i]).length ?? 0;

  return (
    <>
      <header className="topo"><h1>Contas da casa (PDF)</h1></header>

      <section className="cartao-painel">
        <p>
          Suba os PDFs das contas da casa — <strong>luz (EDP Escelsa e Solar), água (CESAN) e plano
          (Unimed)</strong>. O app lê cada fatura, acha o pagamento que já está lançado e preenche a{" "}
          <strong>ficha</strong> dele (consumo, bandeira, multa, m³, vidas). É isso que alimenta os
          painéis de energia, água e plano. Nada é gravado até você conferir e clicar em{" "}
          <strong>Gravar fichas</strong>.
        </p>
        <p className="dica">
          Uma fatura só é preenchida se já existe no app um <strong>lançamento pago de mesmo valor</strong>,
          perto do vencimento. Se faltar, lance a despesa primeiro em <Link to="/transacoes">Transações</Link>.
        </p>
      </section>

      <section className="passos">
        <div className="cartao-painel">
          <h3>📁 Escolher pasta</h3>
          <p className="suave">Aponte a pasta das contas (ex.: <code>Contas\2026</code>). O app lê todos
            os <code>.pdf</code> de dentro de uma vez.</p>
          {/* webkitdirectory não é tipado no React; ligo pelo ref para o seletor virar "escolher pasta". */}
          <input type="file" ref={(el) => el && el.setAttribute("webkitdirectory", "")}
            onChange={(e) => { enviar(e.target.files); e.target.value = ""; }} />
        </div>
        <div className="cartao-painel">
          <h3>📄 Escolher arquivos</h3>
          <p className="suave">Ou mande um ou poucos PDFs avulsos.</p>
          <input type="file" accept=".pdf" multiple
            onChange={(e) => { enviar(e.target.files); e.target.value = ""; }} />
        </div>
        <div className="cartao-painel">
          <h3>🔒 Senha (se precisar)</h3>
          <p className="suave">Alguns PDFs são protegidos (EDP Solar, Claro). Informe a senha; se forem
            várias, separe por <code>;</code>.</p>
          <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)}
            placeholder="senha do PDF (opcional)" autoComplete="off" />
        </div>
      </section>

      {lendo && <p className="dica">Lendo os PDFs…</p>}
      {msg && <p className={msg.ok ? "aviso-ok" : "erro"}>{msg.texto}</p>}

      {lidas && lidas.length > 0 && (
        <section className="cartao-painel espaco">
          <h3>Confira antes de gravar</h3>
          <p className="suave">Marque as faturas que quer gravar. Por padrão já deixo marcadas as que
            acharam o lançamento e ainda não têm ficha.</p>
          <table className="tabela">
            <thead><tr>
              <th>Gravar</th><th>Conta</th><th>Ref.</th><th>Vence</th><th>Total</th>
              <th>Leitura</th><th>Situação</th>
            </tr></thead>
            <tbody>
              {lidas.map((l, i) => {
                const s = situacao(l);
                const podeMarcar = l.status === "ok" && !!l.lancamento;
                return (
                  <tr key={`${l.arquivo}-${i}`}>
                    <td><input type="checkbox" disabled={!podeMarcar} checked={!!marcadas[i]}
                      onChange={(e) => setMarcadas({ ...marcadas, [i]: e.target.checked })} /></td>
                    <td>{l.fatura?.emissor ?? l.arquivo}<br /><small className="suave">{l.arquivo}</small></td>
                    <td>{l.fatura?.referencia ?? "—"}</td>
                    <td>{l.fatura ? dataBR(l.fatura.vencimento) : "—"}</td>
                    <td>{l.fatura ? reais(l.fatura.total_centavos) : "—"}</td>
                    <td>{l.fatura ? resumoFatura(l.fatura) : "—"}</td>
                    <td className={s.ok ? "aviso-ok" : "erro"}>{s.texto}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <footer className="espaco">
            <button onClick={() => { setLidas(null); setMarcadas({}); }}>Descartar</button>
            <button className="primario" disabled={gravando || paraGravar === 0} onClick={gravar}>
              {gravando ? "Gravando…" : `Gravar fichas (${paraGravar})`}
            </button>
          </footer>
        </section>
      )}
    </>
  );
}
