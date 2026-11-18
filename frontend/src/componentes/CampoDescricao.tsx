import { useEffect, useRef, useState } from "react";
import { api } from "../api";

type Sugestao = { descricao: string; categoria_id: number | null };

/**
 * Campo "Descrição" com autocompletar (estilo Mobills): conforme a pessoa digita,
 * mostra descrições já usadas antes (as mais frequentes/recentes primeiro). Ao escolher
 * uma, preenche a descrição e — se o campo de categoria ainda estiver vazio — já sugere
 * a categoria que costuma ir com aquela descrição. É só conveniência: nada é gravado.
 */
export default function CampoDescricao({ tipo, valor, aoMudar, aoEscolherCategoria, placeholder }: {
  tipo: string; valor: string; aoMudar: (v: string) => void;
  aoEscolherCategoria?: (id: number) => void; placeholder?: string;
}) {
  const [sugestoes, setSugestoes] = useState<Sugestao[]>([]);
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const pularBusca = useRef(false);   // não reabrir a lista logo após escolher um item
  const caixa = useRef<HTMLLabelElement>(null);

  useEffect(() => {
    if (pularBusca.current) { pularBusca.current = false; return; }
    const termo = valor.trim();
    if (termo.length < 2) { setSugestoes([]); setAberto(false); return; }
    let cancelado = false;
    const t = setTimeout(async () => {
      try {
        const r = await api.sugestoesDescricao(termo, tipo);
        if (cancelado) return;
        setSugestoes(r); setAtivo(-1); setAberto(r.length > 0);
      } catch { /* silencioso: autocompletar é só ajuda */ }
    }, 180);
    return () => { cancelado = true; clearTimeout(t); };
  }, [valor, tipo]);

  // Fecha ao clicar fora.
  useEffect(() => {
    function fora(e: MouseEvent) {
      if (caixa.current && !caixa.current.contains(e.target as Node)) setAberto(false);
    }
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, []);

  function escolher(s: Sugestao) {
    pularBusca.current = true;
    aoMudar(s.descricao);
    if (s.categoria_id && aoEscolherCategoria) aoEscolherCategoria(s.categoria_id);
    setAberto(false); setAtivo(-1);
  }

  function tecla(e: React.KeyboardEvent) {
    if (!aberto || !sugestoes.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setAtivo((i) => (i + 1) % sugestoes.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setAtivo((i) => (i - 1 + sugestoes.length) % sugestoes.length); }
    else if (e.key === "Enter" && ativo >= 0) { e.preventDefault(); escolher(sugestoes[ativo]); }
    else if (e.key === "Escape") { setAberto(false); }
  }

  return (
    <label className="autocompletar" ref={caixa}>Descrição
      <input value={valor} placeholder={placeholder} autoComplete="off"
        onChange={(e) => aoMudar(e.target.value)}
        onFocus={() => { if (sugestoes.length) setAberto(true); }}
        onKeyDown={tecla} />
      {aberto && sugestoes.length > 0 && (
        <ul className="autocompletar-lista">
          {sugestoes.map((s, i) => (
            <li key={s.descricao}>
              <button type="button" className={"autocompletar-item" + (i === ativo ? " ativo" : "")}
                onMouseEnter={() => setAtivo(i)} onClick={() => escolher(s)}>{s.descricao}</button>
            </li>
          ))}
        </ul>
      )}
    </label>
  );
}
