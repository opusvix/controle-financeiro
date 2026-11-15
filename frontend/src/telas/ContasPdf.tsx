import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type Categoria, type ContaPdfLida, type FaturaPdf } from "../api";
import { useDados } from "../componentes/useDados";
import { dataBR, hojeISO, reais } from "../formato";

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

/** Dados para criar a despesa que falta: conta que pagou (obrigatória), categoria (opcional) e se já está paga. */
type Criar = { conta_id: string; categoria_id: string; pago: boolean };

/** Um item enviado para gravar: anexa a um lançamento existente ou cria a despesa que falta. */
type ItemGravar = { fatura: FaturaPdf; transacao_id?: number;
  criar?: { conta_id: number; categoria_id: number | null; pago: boolean } };

/** Palpite de "já paga": se o vencimento já passou, provavelmente foi paga. */
const pagaPorPadrao = (f: FaturaPdf) => f.vencimento <= hojeISO();

export default function ContasPdf() {
  const contas = useDados(api.contas);
  const categorias = useDados(api.categorias);
  const [senha, setSenha] = useState("");
  const [lidas, setLidas] = useState<ContaPdfLida[] | null>(null);
  const [marcadas, setMarcadas] = useState<Record<number, boolean>>({});
  const [criar, setCriar] = useState<Record<number, Criar>>({});
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const [lendo, setLendo] = useState(false);
  const [gravando, setGravando] = useState(false);

  async function enviar(arquivos: FileList | null) {
    const pdfs = Array.from(arquivos ?? []).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) {
      setMsg({ ok: false, texto: "Não achei nenhum arquivo .pdf no que você escolheu." });
      return;
    }
    setMsg(null); setLidas(null); setCriar({}); setLendo(true);
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

  /** Itens válidos para gravar: os marcados que têm lançamento, ou os sem lançamento com conta escolhida. */
  function montarItens(): ItemGravar[] {
    return (lidas ?? []).flatMap<ItemGravar>((l, i) => {
      if (!marcadas[i] || !l.fatura) return [];
      if (l.lancamento) return [{ fatura: l.fatura, transacao_id: l.lancamento.id }];
      const cr = criar[i];
      if (!cr?.conta_id) return [];
      return [{ fatura: l.fatura, criar: { conta_id: Number(cr.conta_id),
        categoria_id: cr.categoria_id ? Number(cr.categoria_id) : null, pago: cr.pago } }];
    });
  }

  async function gravar() {
    const itens = montarItens();
    if (!itens.length) return setMsg({ ok: false, texto: "Marque ao menos uma fatura (e, se for criar a despesa, escolha a conta)." });
    setGravando(true);
    try {
      const r = await api.gravarContasPdf(itens);
      const extra = r.criadas ? ` (${r.criadas} despesa(s) criada(s))` : "";
      setMsg({ ok: true, texto: `Pronto: ${r.gravadas} ficha(s) gravada(s)${extra}. Veja o consumo nos painéis das Contas.` });
      setLidas(null); setMarcadas({}); setCriar({});
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
    finally { setGravando(false); }
  }

  /** Mexe nos dados de criação de uma linha, preservando o resto. */
  function mudarCriar(i: number, campo: Partial<Criar>, padrao: boolean) {
    const atual = criar[i] ?? { conta_id: "", categoria_id: "", pago: padrao };
    setCriar({ ...criar, [i]: { ...atual, ...campo } });
  }

  /** Escolhe a conta que pagou uma fatura sem lançamento (e já marca a linha para gravar). */
  function escolherConta(i: number, conta_id: string, padrao: boolean) {
    mudarCriar(i, { conta_id }, padrao);
    setMarcadas({ ...marcadas, [i]: !!conta_id });
  }

  const paraGravar = montarItens().length;

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
          O app procura um <strong>lançamento pago de mesmo valor</strong>, perto do vencimento, para
          preencher. Se não achar, você pode <strong>criar a despesa</strong> aqui mesmo (escolhendo a
          conta que pagou) ou lançar antes em <Link to="/transacoes">Transações</Link>.
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
                const semLancamento = l.status === "ok" && !l.lancamento;
                const podeMarcar = l.status === "ok" && (!!l.lancamento || !!criar[i]?.conta_id);
                return (
                  <tr key={`${l.arquivo}-${i}`}>
                    <td><input type="checkbox" disabled={!podeMarcar} checked={!!marcadas[i]}
                      onChange={(e) => setMarcadas({ ...marcadas, [i]: e.target.checked })} /></td>
                    <td>{l.fatura?.emissor ?? l.arquivo}<br /><small className="suave">{l.arquivo}</small></td>
                    <td>{l.fatura?.referencia ?? "—"}</td>
                    <td>{l.fatura ? dataBR(l.fatura.vencimento) : "—"}</td>
                    <td>{l.fatura ? reais(l.fatura.total_centavos) : "—"}</td>
                    <td>{l.fatura ? resumoFatura(l.fatura) : "—"}</td>
                    <td className={s.ok ? "aviso-ok" : "erro"}>
                      {s.texto}
                      {semLancamento && l.fatura && (() => {
                        const padrao = pagaPorPadrao(l.fatura);
                        const pago = criar[i]?.pago ?? padrao;
                        return (
                          <div className="form espaco">
                            <p className="suave">Não achei o pagamento no app. Escolha a conta e eu
                              <strong> crio a despesa</strong> (datada no vencimento) junto com a ficha:</p>
                            <div className="duas">
                              <label>Conta
                                <select value={criar[i]?.conta_id ?? ""} onChange={(e) => escolherConta(i, e.target.value, padrao)}>
                                  <option value="">Escolha a conta…</option>
                                  {contas.dados?.filter((x) => x.ativa).map((x) =>
                                    <option key={x.id} value={x.id}>{x.nome}</option>)}
                                </select></label>
                              <label>Categoria <small>(opcional)</small>
                                <CategoriasDespesa lista={categorias.dados ?? []} valor={criar[i]?.categoria_id ?? ""}
                                  aoMudar={(v) => mudarCriar(i, { categoria_id: v }, padrao)} />
                              </label>
                            </div>
                            <label className="chave"><input type="checkbox" checked={pago}
                              onChange={(e) => mudarCriar(i, { pago: e.target.checked }, padrao)} />
                              <span><strong>Já paga</strong> — {l.fatura.vencimento <= hojeISO()
                                ? "o vencimento já passou, por isso sugeri marcada"
                                : "o vencimento é futuro; deixe desmarcada se ainda vai pagar (fica em “a pagar”)"}</span></label>
                          </div>
                        );
                      })()}
                    </td>
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

/** Seletor de categoria de despesa (mãe + subcategorias), igual ao da tela de Cupons. */
function CategoriasDespesa({ lista, valor, aoMudar }:
    { lista: Categoria[]; valor: string; aoMudar: (v: string) => void }) {
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
