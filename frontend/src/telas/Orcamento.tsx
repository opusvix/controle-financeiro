import { useState } from "react";
import { api, type Categoria, type LinhaOrcamento } from "../api";
import SeletorMes from "../componentes/SeletorMes";
import { useDados } from "../componentes/useDados";
import { mesAtual, paraCentavos, reais } from "../formato";

/**
 * Orçamento × realizado: para cada categoria de despesa, um teto no mês e o quanto já foi
 * gasto (o mesmo "gasto por categoria" do Dashboard). A barra mostra o quanto do teto já foi
 * usado; passar de 100% fica vermelho. Pense num "planejado × realizado" do Power BI.
 */
export default function Orcamento() {
  const [mes, setMes] = useState(mesAtual());
  const { dados, erro, recarregar } = useDados(() => api.orcamento(mes), [mes]);
  const catDados = useDados(() => api.categorias(), []);
  const [extras, setExtras] = useState<LinhaOrcamento[]>([]);   // categorias adicionadas na tela
  const [rascunho, setRascunho] = useState<Record<number, string>>({});   // id -> texto do teto em edição
  const [salvando, setSalvando] = useState<number | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  if (erro) return <p className="erro">{erro}</p>;
  if (!dados) return null;

  // Linhas do servidor + as que o usuário acabou de adicionar (sem teto ainda).
  const mapa = new Map<number, LinhaOrcamento>();
  dados.linhas.forEach((l) => mapa.set(l.categoria_id, l));
  extras.forEach((l) => { if (!mapa.has(l.categoria_id)) mapa.set(l.categoria_id, l); });
  const linhas = [...mapa.values()];

  const maesDespesa = (catDados.dados ?? []).filter((c) => c.tipo === "despesa" && c.pai_id === null);
  const faltantes = maesDespesa.filter((c) => !mapa.has(c.id));

  async function salvarTeto(categoria_id: number) {
    const texto = rascunho[categoria_id];
    if (texto === undefined) return;                       // nada digitado nesta linha
    const centavos = texto.trim() === "" ? 0 : paraCentavos(texto);
    if (centavos === null) { setAviso("Valor do teto inválido. Use algo como 500 ou 1.200,00."); return; }
    setSalvando(categoria_id); setAviso(null);
    try {
      await api.definirOrcamento(categoria_id, mes, centavos);
      setRascunho((r) => { const n = { ...r }; delete n[categoria_id]; return n; });
      setExtras((e) => e.filter((l) => l.categoria_id !== categoria_id));
      await recarregar();
    } catch (e) { setAviso((e as Error).message); }
    finally { setSalvando(null); }
  }

  function adicionar(categoria: Categoria) {
    setExtras((e) => [...e, { categoria_id: categoria.id, categoria: categoria.nome, cor: categoria.cor,
      orcado_centavos: 0, realizado_centavos: 0, saldo_centavos: 0, pct: null }]);
  }

  async function copiarMesAnterior() {
    setAviso(null);
    try {
      const { copiados } = await api.copiarOrcamento(mes);
      setAviso(copiados ? `Copiei ${copiados} teto(s) do mês anterior.` : "Nada novo para copiar do mês anterior.");
      await recarregar();
    } catch (e) { setAviso((e as Error).message); }
  }

  const t = dados.total;

  return (
    <>
      <header className="topo">
        <h1>Orçamento × realizado</h1>
        <SeletorMes mes={mes} aoMudar={(m) => { setMes(m); setExtras([]); setRascunho({}); }} />
      </header>

      <div className="energia-kpis espaco">
        <div><span>Orçado no mês</span><strong>{reais(t.orcado_centavos)}</strong></div>
        <div><span>Realizado (com teto)</span><strong>{reais(t.realizado_centavos)}</strong></div>
        <div><span>Saldo do orçamento</span>
          <strong className={t.saldo_centavos < 0 ? "neg" : "pos"}>{reais(t.saldo_centavos)}</strong>
          <small>{t.pct == null ? "sem teto definido" : `${t.pct}% do planejado`}</small></div>
      </div>

      {aviso && <p className="dica">{aviso}</p>}

      <section className="cartao-painel espaco">
        <div className="orc-acoes">
          <h3>Tetos por categoria <small>· despesa</small></h3>
          <div className="orc-acoes-dir">
            {faltantes.length > 0 && (
              <select value="" onChange={(e) => {
                const c = faltantes.find((x) => x.id === Number(e.target.value));
                if (c) adicionar(c);
              }}>
                <option value="">+ Adicionar categoria…</option>
                {faltantes.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </select>
            )}
            <button className="ver-mais" onClick={copiarMesAnterior}>Copiar do mês anterior</button>
          </div>
        </div>

        {linhas.length === 0 ? (
          <p className="vazio">Nenhum teto neste mês ainda. Use "+ Adicionar categoria…" para definir
            um limite, ou "Copiar do mês anterior".</p>
        ) : (
          <table className="tabela orc-tabela">
            <thead><tr>
              <th>Categoria</th><th>Teto (R$)</th><th className="num">Realizado</th>
              <th className="orc-col-barra">Uso</th><th className="num">Saldo</th>
            </tr></thead>
            <tbody>
              {linhas.map((l) => {
                const emEdicao = rascunho[l.categoria_id] !== undefined;
                const valorInput = emEdicao ? rascunho[l.categoria_id]
                  : l.orcado_centavos ? (l.orcado_centavos / 100).toFixed(2).replace(".", ",") : "";
                const estourou = l.pct != null && l.pct > 100;
                return (
                  <tr key={l.categoria_id}>
                    <td><span className="orc-cat"><i style={{ background: l.cor }} />{l.categoria}</span></td>
                    <td>
                      <input className="orc-input" inputMode="decimal" placeholder="— sem teto —"
                        value={valorInput}
                        onChange={(e) => setRascunho((r) => ({ ...r, [l.categoria_id]: e.target.value }))}
                        onBlur={() => salvarTeto(l.categoria_id)}
                        onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                        disabled={salvando === l.categoria_id} />
                    </td>
                    <td className="num">{reais(l.realizado_centavos)}</td>
                    <td className="orc-col-barra">
                      {l.orcado_centavos ? (
                        <div className="orc-barra" title={`${l.pct}% do teto`}>
                          <i className={estourou ? "estourou" : ""}
                            style={{ width: `${Math.min(100, l.pct ?? 0)}%`, background: estourou ? undefined : l.cor }} />
                          <span>{l.pct}%</span>
                        </div>
                      ) : <span className="dica">—</span>}
                    </td>
                    <td className="num"><span className={l.saldo_centavos < 0 ? "neg" : "pos"}>
                      {l.orcado_centavos ? reais(l.saldo_centavos) : "—"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <p className="dica">Digite o teto e saia do campo (ou tecle Enter) para salvar. Deixe em branco
          para remover o teto. O "realizado" é o mesmo gasto por categoria do Dashboard (itens de cupom
          na categoria de cada item, estornos abatem, lançamentos "ignorar" ficam de fora).</p>
      </section>
    </>
  );
}
