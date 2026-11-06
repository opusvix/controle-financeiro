import { useState } from "react";
import { api, type Categoria } from "../api";

/**
 * Seletor de categoria (mãe → subcategoria). Passando `tipo`, ganha a opção
 * "+ Nova categoria…", que cria a categoria na hora (sem sair da tela) e já a
 * seleciona. As categorias criadas aqui entram na lista desta instância; use
 * `aoCriar` para o pai também aproveitá-la em outros seletores.
 */
export default function SeletorCategoria({
  categorias, valor, aoMudar, tipo, semRotulo, vazio = "Escolha…", aoCriar,
}: {
  categorias: Categoria[]; valor: string; aoMudar: (v: string) => void;
  tipo?: "receita" | "despesa"; semRotulo?: boolean; vazio?: string;
  aoCriar?: (c: Categoria) => void;
}) {
  const [extra, setExtra] = useState<Categoria[]>([]);
  const [criando, setCriando] = useState(false);
  const [nome, setNome] = useState("");
  const [maeId, setMaeId] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const vistos = new Set<number>();
  const todas = [...categorias, ...extra].filter((c) => !vistos.has(c.id) && vistos.add(c.id));
  const maes = todas.filter((c) => c.pai_id === null);

  async function criar() {
    if (!nome.trim() || !tipo) return;
    try {
      const nova = await api.criarCategoria({
        nome: nome.trim(), tipo, pai_id: maeId ? Number(maeId) : null });
      setExtra((e) => [...e, nova]);
      aoCriar?.(nova);
      aoMudar(String(nova.id));
      setCriando(false); setNome(""); setMaeId(""); setErro(null);
    } catch (e) { setErro((e as Error).message); }
  }

  const select = (
    <select value={valor}
      onChange={(e) => e.target.value === "__nova__" ? setCriando(true) : aoMudar(e.target.value)}>
      <option value="">{vazio}</option>
      {maes.map((m) => (
        <optgroup key={m.id} label={m.nome}>
          <option value={m.id}>{m.nome} (geral)</option>
          {todas.filter((c) => c.pai_id === m.id).map((c) => (
            <option key={c.id} value={c.id}>{c.nome}</option>))}
        </optgroup>
      ))}
      {tipo && <option value="__nova__">+ Nova categoria…</option>}
    </select>
  );

  const criador = criando && (
    <div className="nova-categoria">
      <input placeholder="Nome da nova categoria" value={nome} autoFocus
        onChange={(e) => setNome(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); criar(); } }} />
      <select value={maeId} onChange={(e) => setMaeId(e.target.value)}>
        <option value="">Como categoria principal</option>
        {maes.map((m) => <option key={m.id} value={m.id}>dentro de {m.nome}</option>)}
      </select>
      <button type="button" className="primario" disabled={!nome.trim()} onClick={criar}>Criar</button>
      <button type="button" onClick={() => { setCriando(false); setErro(null); }}>Cancelar</button>
      {erro && <span className="erro">{erro}</span>}
    </div>
  );

  return (
    <>
      {semRotulo ? select : <label>Categoria{select}</label>}
      {criador}
    </>
  );
}
