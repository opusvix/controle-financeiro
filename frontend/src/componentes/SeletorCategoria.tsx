import type { Categoria } from "../api";

export default function SeletorCategoria({ categorias, valor, aoMudar }: {
  categorias: Categoria[]; valor: string; aoMudar: (v: string) => void;
}) {
  const maes = categorias.filter((c) => c.pai_id === null);
  return (
    <label>Categoria
      <select value={valor} onChange={(e) => aoMudar(e.target.value)}>
        <option value="">Escolha…</option>
        {maes.map((m) => (
          <optgroup key={m.id} label={m.nome}>
            <option value={m.id}>{m.nome} (geral)</option>
            {categorias.filter((c) => c.pai_id === m.id).map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
