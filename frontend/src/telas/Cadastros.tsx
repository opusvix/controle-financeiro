import { useState } from "react";
import { api, type Categoria } from "../api";
import { useDados } from "../componentes/useDados";

export default function Cadastros() {
  const categorias = useDados(api.categorias);
  const tags = useDados(api.tags);
  const [tipo, setTipo] = useState<"despesa" | "receita">("despesa");
  const [novaCat, setNovaCat] = useState({ nome: "", pai_id: "" });
  const [novaTag, setNovaTag] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const daVez = categorias.dados?.filter((c) => c.tipo === tipo) ?? [];
  const maes = daVez.filter((c) => c.pai_id === null);

  async function criarCategoria() {
    if (!novaCat.nome.trim()) return;
    const mae = maes.find((m) => String(m.id) === novaCat.pai_id);
    try {
      await api.criarCategoria({ nome: novaCat.nome.trim(), tipo,
        pai_id: mae ? mae.id : null, cor: mae?.cor ?? "#6b7280" });
      setNovaCat({ nome: "", pai_id: novaCat.pai_id }); setErro(null); categorias.recarregar();
    } catch (e) { setErro((e as Error).message); }
  }

  async function alternarFixa(c: Categoria) {
    try { await api.editarCategoria(c.id, { fixa: !c.fixa }); categorias.recarregar(); }
    catch (e) { setErro((e as Error).message); }
  }
  // Fixa (conta da casa) x variável: a subcategoria herda a marca da categoria-mãe.
  const Marca = ({ c, herdada }: { c: Categoria; herdada?: boolean }) => tipo !== "despesa" ? null : herdada
    ? <span className="marca-fixa sim herdada" title="Herdada da categoria-mãe">fixa</span>
    : <button className={`marca-fixa${c.fixa ? " sim" : ""}`} onClick={() => alternarFixa(c)}
        title="Clique para alternar entre despesa fixa e variável">{c.fixa ? "fixa" : "variável"}</button>;

  async function criarTag() {
    if (!novaTag.trim()) return;
    try { await api.criarTag({ nome: novaTag.trim() }); setNovaTag(""); setErro(null); tags.recarregar(); }
    catch (e) { setErro((e as Error).message); }
  }

  return (
    <>
      <header className="topo"><h1>Cadastros</h1></header>
      {erro && <p className="erro">{erro}</p>}
      <section className="grade-2">
        <div className="cartao-painel">
          <header>
            <h3>Categorias</h3>
            <div className="abas">
              <button className={tipo === "despesa" ? "sel" : ""} onClick={() => setTipo("despesa")}>Despesas</button>
              <button className={tipo === "receita" ? "sel" : ""} onClick={() => setTipo("receita")}>Receitas</button>
            </div>
          </header>
          <p className="dica">Categoria responde <b>o que</b> foi gasto (como uma conta contábil).
            Para <b>qual projeto</b>, use uma tag.
            {tipo === "despesa" && <> A marca <b>fixa</b> separa as contas da casa (luz, água, internet,
              plano de saúde) dos gastos variáveis no Dashboard.</>}</p>
          <ul className="arvore">
            {maes.map((m) => (
              <li key={m.id}><i style={{ background: m.cor }} />{m.nome}<Marca c={m} />
                <ul>{daVez.filter((c) => c.pai_id === m.id).map((c) => (
                  <li key={c.id}>{c.nome}<Marca c={c} herdada={!!m.fixa} /></li>))}</ul>
              </li>
            ))}
          </ul>
          <div className="linha-form">
            <input placeholder="Nova categoria" value={novaCat.nome}
              onChange={(e) => setNovaCat({ ...novaCat, nome: e.target.value })} />
            <select value={novaCat.pai_id} onChange={(e) => setNovaCat({ ...novaCat, pai_id: e.target.value })}>
              <option value="">(categoria principal)</option>
              {maes.map((m) => <option key={m.id} value={m.id}>dentro de {m.nome}</option>)}
            </select>
            <button className="primario" onClick={criarCategoria}>Adicionar</button>
          </div>
        </div>
        <div className="cartao-painel">
          <h3>Tags</h3>
          <p className="dica">Tags funcionam como centros de custo: CERCO FELINO, Empreendimentos, Viagem 2026…</p>
          <ul className="chips">{tags.dados?.map((t) => <li key={t.id}>{t.nome}</li>)}</ul>
          {tags.dados?.length === 0 && <p className="vazio">Nenhuma tag ainda.</p>}
          <div className="linha-form">
            <input placeholder="Nova tag" value={novaTag} onChange={(e) => setNovaTag(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && criarTag()} />
            <button className="primario" onClick={criarTag}>Adicionar</button>
          </div>
          <h3 className="espaco">Importar e exportar</h3>
          <p className="vazio">Importação do Mobills: rode <code>scripts\importar_mobills.bat ARQUIVO.xlsx</code> (simula primeiro e pede confirmação).</p>
        </div>
      </section>
    </>
  );
}
