import { useState } from "react";
import { api, type EventoPlano } from "../api";
import { reais } from "../formato";
import { useDados } from "./useDados";

const MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const rotulo = (ref: string) => `${MES[Number(ref.slice(5)) - 1]}/${ref.slice(2, 4)}`;
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
const periodo = (p: string) => p.split(" a ").map(rotulo).join(" a ");

/**
 * Plano de saúde: cada aumento é classificado e medido contra a régua certa.
 * - Reajuste ANUAL (todos sobem o mesmo %): comparado com o teto da ANS e com a inflação.
 * - FAIXA ETÁRIA (só uma pessoa sobe): regra de idade do contrato, não é inflação.
 */
export default function PainelPlano() {
  const { dados, erro, recarregar } = useDados(() => api.plano(), []);
  const [baixando, setBaixando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  if (erro) return <p className="erro">{erro}</p>;
  if (!dados || !dados.meses.length) return null;

  const atual = dados.meses[dados.meses.length - 1];
  const vidas = atual.vidas || new Set(atual.itens.map((i) => i.beneficiario)).size || null;
  const anual = [...dados.eventos].reverse().find((e) => e.tipo === "anual");
  const semIndices = Object.values(dados.indices_ate).every((m) => !m);

  async function baixar() {
    setBaixando(true); setAviso(null);
    try {
      const r = await api.atualizarIndices();
      const erros = Object.entries(r).filter(([, v]) => v.erro).map(([k]) => k);
      setAviso(erros.length ? `Não consegui baixar: ${erros.join(", ")} (sem internet?).` : "Índices atualizados.");
      recarregar();
    } catch (e) { setAviso((e as Error).message); } finally { setBaixando(false); }
  }

  return (
    <div className="cartao-painel energia">
      <h3>Plano de saúde <small>Unimed · {vidas ?? "?"} vidas · individual (teto da ANS vale)</small></h3>
      <div className="energia-kpis">
        <div><span>Mensalidade ({rotulo(atual.referencia)})</span><strong>{reais(atual.total_centavos)}</strong>
          <small>{reais(atual.total_centavos * 12)} por ano</small></div>
        <div><span>Custo por vida</span><strong>{vidas ? reais(Math.round(atual.total_centavos / vidas)) : "—"}</strong>
          <small>sem coparticipação</small></div>
        <div><span>Último reajuste anual</span>
          <strong className={anual?.acima_do_teto ? "neg" : ""}>{anual ? pct(anual.percentual) : "—"}</strong>
          <small>{anual ? `${rotulo(anual.referencia)} · teto ANS ${anual.teto_ans ? pct(anual.teto_ans.percentual) : "?"}` : "nenhum no período"}</small></div>
        <div><span>Aumentos no período</span><strong>{dados.eventos.length}</strong>
          <small>{dados.eventos.filter((e) => e.tipo === "faixa_etaria").length} por faixa etária</small></div>
      </div>
      {dados.eventos.map((e) => <Evento key={e.referencia} e={e} />)}
      <div className="plano-rodape">
        <button onClick={baixar} disabled={baixando}>{baixando ? "Baixando…" : "Atualizar índices (Banco Central)"}</button>
        <small>{semIndices ? "Índices ainda não baixados: clique para comparar com IPCA, INPC, IGP-M, IGP-DI e IPC-Fipe."
          : `Índices até ${Object.entries(dados.indices_ate).filter(([, m]) => m).map(([k, m]) => `${k} ${rotulo(m!)}`).join(" · ")}`}</small>
        {aviso && <small className="aviso">{aviso}</small>}
      </div>
    </div>
  );
}

function Evento({ e }: { e: EventoPlano }) {
  const cabecalho = (
    <header>
      <strong>{rotulo(e.referencia)} · {e.tipo === "anual" ? "Reajuste anual" : e.tipo === "faixa_etaria" ? "Mudança de faixa etária" : "Aumento"}</strong>
      <span>{reais(e.antes_centavos)} → {reais(e.depois_centavos)} ({pct(e.percentual)})</span>
      <small>+{reais(e.diferenca_mes_centavos)}/mês · +{reais(e.diferenca_mes_centavos * 12)}/ano</small>
    </header>);
  if (e.tipo === "faixa_etaria") return (
    <div className="plano-evento">
      {cabecalho}
      <p className="dica">{e.detalhe.map((d) => `${d.beneficiario}: ${d.item.toLowerCase()} ${reais(d.antes_centavos)} → ${reais(d.depois_centavos)} (${pct(d.percentual)})`).join(" · ")}.
        {" "}Só {e.quem.join(", ")} subiu: é a tabela de idade do contrato, não o reajuste anual. Vale conferir se o % bate com a tabela de faixas do contrato.</p>
    </div>);
  const barras = [
    { nome: "Unimed", v: e.percentual, cor: "#f87171" },
    ...(e.teto_ans ? [{ nome: "Teto ANS", v: e.teto_ans.percentual, cor: "#F38433" }] : []),
    ...(e.comparacao ?? []).filter((c) => c.percentual != null).map((c) => ({ nome: c.indice, v: c.percentual!, cor: "#60a5fa" })),
  ];
  const max = Math.max(...barras.map((b) => Math.abs(b.v)), 1);
  const ipca = e.comparacao?.find((c) => c.indice === "IPCA")?.percentual;
  return (
    <div className="plano-evento">
      {cabecalho}
      <div className="barras-indices">
        {barras.map((b) => (
          <div key={b.nome} className="barra-indice">
            <span>{b.nome}</span>
            <div><b style={{ width: `${(Math.abs(b.v) / max) * 100}%`, background: b.cor }} /></div>
            <em className={b.v < 0 ? "pos" : ""}>{pct(b.v)}</em>
          </div>))}
      </div>
      <p className="dica">
        {e.teto_ans && (e.acima_do_teto
          ? <>⚠️ <b>Acima do teto da ANS</b> ({pct(e.teto_ans.percentual)}). Em plano individual isso não pode: vale reclamar na ANS (0800 701 9656).</>
          : <>Dentro do teto da ANS ({pct(e.teto_ans.percentual)}, {e.teto_ans.fonte}).</>)}
        {ipca != null && <> Inflação (IPCA) em {periodo(e.comparacao!.find((c) => c.indice === "IPCA")!.periodo)}: {pct(ipca)}, então o plano subiu
          {" "}{(e.percentual - ipca).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ponto(s) {e.percentual >= ipca ? "acima" : "abaixo"} da inflação.</>}
      </p>
    </div>);
}
