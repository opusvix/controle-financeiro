import { useState } from "react";
import { api, type FiltroTransacoes, type FiltroSalvo } from "../api";
import { dataBR } from "../formato";
import Modal from "./Modal";
import { useDados } from "./useDados";

const TIPOS: [string, string][] = [
  ["despesa", "Despesa"], ["receita", "Receita"], ["despesa_cartao", "Despesa no cartão"],
  ["credito_cartao", "Crédito na fatura"], ["transferencia", "Transferência"],
  ["pagamento_fatura", "Pagamento de fatura"], ["ajuste", "Ajuste"],
];
const SITUACOES: [string, string][] = [["pago", "Pagas / recebidas"], ["pendente", "Pendentes"]];

/** Modal de filtro da tela Transações (período, categorias, contas, tags, situações, tipos). */
export default function FiltroTransacoes({ inicial, aoAplicar, aoFechar }: {
  inicial: FiltroTransacoes; aoAplicar: (f: FiltroTransacoes) => void; aoFechar: () => void;
}) {
  const categorias = useDados(() => api.categorias(), []);
  const contas = useDados(() => api.contas(), []);
  const tags = useDados(() => api.tags(), []);
  const salvos = useDados(() => api.filtrosSalvos(), []);
  const [aba, setAba] = useState<"novo" | "salvos">("novo");

  const [ini, setIni] = useState(inicial.ini ?? "");
  const [fim, setFim] = useState(inicial.fim ?? "");
  const [cats, setCats] = useState<number[]>(inicial.categorias ?? []);
  const [cnts, setCnts] = useState<number[]>(inicial.contas ?? []);
  const [tgs, setTgs] = useState<number[]>(inicial.tags ?? []);
  const [sits, setSits] = useState<string[]>(inicial.situacoes ?? []);
  const [tps, setTps] = useState<string[]>(inicial.tipos ?? []);
  const [salvar, setSalvar] = useState(false);
  const [nome, setNome] = useState("");

  const maes = (categorias.dados ?? []).filter((c) => c.pai_id === null);
  const optCategorias: [number, string][] = maes.flatMap((m) => [
    [m.id, m.nome] as [number, string],
    ...(categorias.dados ?? []).filter((c) => c.pai_id === m.id).map((c) => [c.id, `   ${c.nome}`] as [number, string]),
  ]);

  function montar(): FiltroTransacoes {
    return {
      ...(ini && fim ? { ini, fim } : {}),
      categorias: cats, contas: cnts, tags: tgs,
      situacoes: sits as ("pago" | "pendente")[], tipos: tps,
    };
  }

  async function aplicar() {
    const f = montar();
    if (salvar && nome.trim()) await api.salvarFiltro(nome.trim(), f);
    aoAplicar(f);
  }

  async function apagarSalvo(s: FiltroSalvo) {
    await api.apagarFiltro(s.id);
    salvos.recarregar();
  }

  return (
    <Modal titulo="Filtro de transações" aoFechar={aoFechar}>
      <div className="filtro-abas">
        <button className={aba === "novo" ? "ativa" : ""} onClick={() => setAba("novo")}>Novo filtro</button>
        <button className={aba === "salvos" ? "ativa" : ""} onClick={() => setAba("salvos")}>
          Filtros salvos{salvos.dados?.length ? ` (${salvos.dados.length})` : ""}</button>
      </div>

      {aba === "novo" ? (
        <div className="filtro-corpo">
          <div className="duas">
            <label>De<input type="date" value={ini} onChange={(e) => setIni(e.target.value)} /></label>
            <label>Até<input type="date" value={fim} onChange={(e) => setFim(e.target.value)} /></label>
          </div>
          {ini && !fim || !ini && fim ? <p className="dica">Preencha as duas datas, ou deixe as duas em branco (usa o mês atual).</p> : null}

          <Multi titulo="Categorias" vazio="Todas as categorias" opcoes={optCategorias} sel={cats} setSel={setCats} />
          <Multi titulo="Contas" vazio="Todas as contas"
            opcoes={(contas.dados ?? []).filter((c) => c.ativa).map((c) => [c.id, c.nome])} sel={cnts} setSel={setCnts} />
          <Multi titulo="Tags" vazio="Todas as tags"
            opcoes={(tags.dados ?? []).map((t) => [t.id, t.nome])} sel={tgs} setSel={setTgs} />
          <MultiTexto titulo="Situações" vazio="Todas as situações" opcoes={SITUACOES} sel={sits} setSel={setSits} />
          <MultiTexto titulo="Tipos" vazio="Todos os tipos" opcoes={TIPOS} sel={tps} setSel={setTps} />

          <label className="chave filtro-salvar">
            <input type="checkbox" checked={salvar} onChange={(e) => setSalvar(e.target.checked)} />
            Salvar filtro personalizado</label>
          {salvar && <input className="filtro-nome" placeholder="Nome do filtro (ex.: Casa em novembro)"
            value={nome} onChange={(e) => setNome(e.target.value)} />}

          <footer className="filtro-rodape">
            <button onClick={aoFechar}>Cancelar</button>
            <button className="primario" disabled={salvar && !nome.trim()} onClick={aplicar}>Aplicar filtros</button>
          </footer>
        </div>
      ) : (
        <div className="filtro-corpo">
          {!salvos.dados?.length && <p className="vazio">Nenhum filtro salvo ainda.</p>}
          <ul className="filtro-lista">
            {salvos.dados?.map((s) => (
              <li key={s.id}>
                <button className="link" onClick={() => aoAplicar(s.criterios)}>{s.nome}</button>
                <small>{resumo(s.criterios)}</small>
                <button className="link apagar" onClick={() => apagarSalvo(s)} aria-label="Apagar filtro">Apagar</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Modal>
  );
}

function resumo(f: FiltroTransacoes): string {
  const p: string[] = [];
  if (f.ini && f.fim) p.push(`${dataBR(f.ini)}–${dataBR(f.fim)}`);
  if (f.categorias?.length) p.push(`${f.categorias.length} categoria(s)`);
  if (f.contas?.length) p.push(`${f.contas.length} conta(s)`);
  if (f.tags?.length) p.push(`${f.tags.length} tag(s)`);
  if (f.tipos?.length) p.push(`${f.tipos.length} tipo(s)`);
  if (f.situacoes?.length === 1) p.push(f.situacoes[0] === "pago" ? "pagas" : "pendentes");
  return p.join(" · ") || "sem filtros";
}

function Multi({ titulo, vazio, opcoes, sel, setSel }: {
  titulo: string; vazio: string; opcoes: [number, string][]; sel: number[]; setSel: (v: number[]) => void;
}) {
  const alternar = (id: number) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]);
  const rotulo = sel.length === 0 ? vazio : `${sel.length} selecionada(s)`;
  return (
    <details className="filtro-multi">
      <summary><span className="filtro-rotulo">{titulo}</span><span className="chip">{rotulo}</span></summary>
      <div className="filtro-opcoes">
        {opcoes.map(([id, nome]) => (
          <label key={id} className="chave"><input type="checkbox" checked={sel.includes(id)}
            onChange={() => alternar(id)} /><span style={{ whiteSpace: "pre" }}>{nome}</span></label>
        ))}
        {sel.length > 0 && <button className="link" onClick={() => setSel([])}>Limpar</button>}
      </div>
    </details>
  );
}

function MultiTexto({ titulo, vazio, opcoes, sel, setSel }: {
  titulo: string; vazio: string; opcoes: [string, string][]; sel: string[]; setSel: (v: string[]) => void;
}) {
  const alternar = (id: string) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]);
  const rotulo = sel.length === 0 ? vazio : `${sel.length} selecionado(s)`;
  return (
    <details className="filtro-multi">
      <summary><span className="filtro-rotulo">{titulo}</span><span className="chip">{rotulo}</span></summary>
      <div className="filtro-opcoes">
        {opcoes.map(([id, nome]) => (
          <label key={id} className="chave"><input type="checkbox" checked={sel.includes(id)}
            onChange={() => alternar(id)} />{nome}</label>
        ))}
        {sel.length > 0 && <button className="link" onClick={() => setSel([])}>Limpar</button>}
      </div>
    </details>
  );
}
