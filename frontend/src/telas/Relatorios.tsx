import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Relatorio, type RelatorioCategoria, type RelatorioMes } from "../api";
import { useDados } from "../componentes/useDados";
import { reais } from "../formato";

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const rotulo = (comp: string) => `${MES[Number(comp.slice(5)) - 1]}/${comp.slice(2, 4)}`;
const pct = (n: number) => `${n.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

type Filtro = { meses: number } | { ini: string; fim: string };

/**
 * Relatórios (Fase 4): a visão ao longo do tempo. O Dashboard mostra o mês; aqui
 * vemos a evolução de receitas × despesas, para onde o dinheiro foi por categoria
 * e quanto cada projeto (tag) custou no período escolhido.
 */
export default function Relatorios() {
  const [filtro, setFiltro] = useState<Filtro>({ meses: 12 });
  const { dados, erro } = useDados(() => api.relatorio(filtro), [JSON.stringify(filtro)]);

  return (
    <>
      <header className="topo"><h1>Relatórios</h1></header>
      <SeletorPeriodo filtro={filtro} aoMudar={setFiltro} />
      {erro && <p className="erro">{erro}</p>}
      {dados && (dados.resumo.receitas === 0 && dados.resumo.despesas === 0
        ? <div className="cartao-painel espaco"><p className="vazio">Sem lançamentos nesse período.</p></div>
        : <Conteudo dados={dados} />)}
    </>
  );
}

function SeletorPeriodo({ filtro, aoMudar }: { filtro: Filtro; aoMudar: (f: Filtro) => void }) {
  const atalhos: [string, number][] = [["3 meses", 3], ["6 meses", 6], ["12 meses", 12], ["24 meses", 24]];
  const mesesAtual = "meses" in filtro ? filtro.meses : null;
  const [ini, setIni] = useState("");
  const [fim, setFim] = useState("");
  return (
    <div className="rel-periodo">
      {atalhos.map(([nome, m]) => (
        <button key={m} className={mesesAtual === m ? "primario" : ""} onClick={() => aoMudar({ meses: m })}>{nome}</button>
      ))}
      <span className="rel-custom">
        <label>De <input type="date" value={ini} onChange={(e) => setIni(e.target.value)} /></label>
        <label>até <input type="date" value={fim} onChange={(e) => setFim(e.target.value)} /></label>
        <button disabled={!ini || !fim || fim < ini} onClick={() => aoMudar({ ini, fim })}>Aplicar</button>
      </span>
    </div>
  );
}

function Conteudo({ dados }: { dados: Relatorio }) {
  const r = dados.resumo;
  const poupanca = r.taxa_poupanca_pct;
  return (
    <>
      <div className="energia-kpis espaco">
        <div><span>Receitas</span><strong className="pos">{reais(r.receitas)}</strong>
          <small>{reais(r.media_receitas_mes)}/mês</small></div>
        <div><span>Despesas</span><strong className="neg">{reais(r.despesas)}</strong>
          <small>{reais(r.media_despesas_mes)}/mês</small></div>
        <div><span>Resultado ({r.meses} {r.meses === 1 ? "mês" : "meses"})</span>
          <strong className={r.resultado >= 0 ? "pos" : "neg"}>{reais(r.resultado)}</strong>
          <small>receitas − despesas</small></div>
        <div><span>Taxa de poupança</span>
          <strong className={poupanca == null ? "" : poupanca >= 0 ? "pos" : "neg"}>
            {poupanca == null ? "—" : pct(poupanca)}</strong>
          <small>do que entrou, quanto sobrou</small></div>
      </div>

      <section className="cartao-painel espaco">
        <h3>Receitas × despesas por mês</h3>
        <GraficoFluxo meses={dados.meses} />
      </section>

      <section className="cartao-painel espaco">
        <h3>Para onde foi o dinheiro <small>· despesas por categoria no período</small></h3>
        <GraficoCategorias meses={dados.meses} categorias={dados.por_categoria} />
        <table className="tabela espaco">
          <thead><tr><th>Categoria</th><th className="num">Total</th><th className="num">% das despesas</th>
            <th className="num">Média/mês</th></tr></thead>
          <tbody>
            {dados.por_categoria.map((c) => (
              <tr key={c.categoria_id}>
                <td><i className="ponto" style={{ background: c.cor }} /> {c.categoria}</td>
                <td className="num">{reais(c.total)}</td>
                <td className="num">{pct(c.pct)}</td>
                <td className="num">{reais(Math.round(c.total / r.meses))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {dados.por_tag.length > 0 && (
        <section className="cartao-painel espaco">
          <h3>Por projeto <small>· etiquetas (centro de custo), ex.: CERCO FELINO</small></h3>
          <ul className="chips">
            {dados.por_tag.map((t) => (
              <li key={t.tag}><i className="ponto" style={{ background: t.cor }} /> {t.tag}{" "}
                <b>{reais(t.total)}</b> <small>· {t.lancamentos} lanç.</small></li>
            ))}
          </ul>
        </section>
      )}

      <p className="dica">
        <b>Taxa de poupança</b> é quanto das receitas sobrou depois das despesas (regime de competência,
        pela data da compra). As despesas seguem a mesma conta do Dashboard: compras de cartão entram pela
        data da compra e estornos abatem a categoria.
      </p>
    </>
  );
}

function GraficoFluxo({ meses }: { meses: RelatorioMes[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const g = echarts.init(ref.current);
    const eixo = { color: "#a1a1aa" };
    g.setOption({
      grid: { left: 60, right: 20, top: 36, bottom: 28 },
      legend: { top: 0, textStyle: eixo, itemWidth: 14, itemHeight: 10 },
      tooltip: {
        trigger: "axis",
        formatter: (ps: { dataIndex: number }[]) => {
          const m = meses[ps[0].dataIndex];
          return [`<b>${rotulo(m.competencia)}</b>`, `Receitas ${reais(m.receitas)}`,
            `Despesas ${reais(m.despesas)}`, `Resultado ${reais(m.resultado)}`].join("<br/>");
        },
      },
      xAxis: { type: "category", data: meses.map((m) => rotulo(m.competencia)), axisLabel: eixo },
      yAxis: { type: "value", axisLabel: { ...eixo, formatter: (c: number) => `R$ ${c / 100}` },
        splitLine: { lineStyle: { color: "#3a3a41" } } },
      series: [
        { name: "Receitas", type: "bar", data: meses.map((m) => m.receitas),
          itemStyle: { color: "#4ade80", borderRadius: [4, 4, 0, 0] }, barMaxWidth: 22 },
        { name: "Despesas", type: "bar", data: meses.map((m) => m.despesas),
          itemStyle: { color: "#f87171", borderRadius: [4, 4, 0, 0] }, barMaxWidth: 22 },
        { name: "Resultado", type: "line", data: meses.map((m) => m.resultado),
          itemStyle: { color: "#ececf1" }, symbolSize: 6, z: 3 },
      ],
    });
    const red = () => g.resize();
    window.addEventListener("resize", red);
    return () => { window.removeEventListener("resize", red); g.dispose(); };
  }, [meses]);
  return <div ref={ref} className="energia-grafico" />;
}

function GraficoCategorias({ meses, categorias }: { meses: RelatorioMes[]; categorias: RelatorioCategoria[] }) {
  const ref = useRef<HTMLDivElement>(null);
  // Mostra as maiores; agrupa o resto em "Outras" para o gráfico não virar um arco-íris.
  const { series, legenda } = useMemo(() => {
    const top = categorias.slice(0, 8);
    const resto = categorias.slice(8);
    const s = top.map((c) => ({ nome: c.categoria, cor: c.cor, dados: c.serie }));
    if (resto.length) {
      const soma = meses.map((_, i) => resto.reduce((a, c) => a + (c.serie[i] || 0), 0));
      s.push({ nome: "Outras", cor: "#9ca3af", dados: soma });
    }
    return { series: s, legenda: s.map((x) => x.nome) };
  }, [categorias, meses]);
  useEffect(() => {
    if (!ref.current) return;
    const g = echarts.init(ref.current);
    const eixo = { color: "#a1a1aa" };
    g.setOption({
      grid: { left: 60, right: 20, top: 48, bottom: 28 },
      legend: { top: 0, textStyle: eixo, itemWidth: 12, itemHeight: 8, type: "scroll" },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" },
        valueFormatter: (v: number) => reais(v) },
      xAxis: { type: "category", data: meses.map((m) => rotulo(m.competencia)), axisLabel: eixo },
      yAxis: { type: "value", axisLabel: { ...eixo, formatter: (c: number) => `R$ ${c / 100}` },
        splitLine: { lineStyle: { color: "#3a3a41" } } },
      series: series.map((s) => ({
        name: s.nome, type: "bar", stack: "cat", data: s.dados,
        itemStyle: { color: s.cor }, barMaxWidth: 34,
      })),
    });
    const red = () => g.resize();
    window.addEventListener("resize", red);
    return () => { window.removeEventListener("resize", red); g.dispose(); };
  }, [series, legenda, meses]);
  return <div ref={ref} className="energia-grafico" />;
}
