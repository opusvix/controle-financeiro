import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import { api, type MesAgua } from "../api";
import { reais } from "../formato";
import { coresGrafico, useTema } from "../tema";
import { useDados } from "./useDados";

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const rotulo = (ref: string) => `${MES[Number(ref.slice(5)) - 1]}/${ref.slice(2, 4)}`;
const m3 = (n: number) => `${n.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} m³`;

/**
 * Água da casa (CESAN). A conta tem duas partes, como um contrato com mensalidade + uso:
 * a FIXA (água + esgoto, paga mesmo sem abrir a torneira) e a VARIÁVEL (por m³).
 */
export default function PainelAgua() {
  const { dados, erro } = useDados(() => api.agua(12), []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!dados || !dados.meses.length) return null;
  const { meses, resumo: r } = dados;
  const ultimo = meses[meses.length - 1];
  const pctFixo = r.total_centavos ? Math.round((r.fixo_centavos / r.total_centavos) * 100) : 0;
  const v = r.variacao_consumo_pct;
  const atrasos = meses.filter((m) => m.pago_com_atraso).length;
  return (
    <div className="cartao-painel energia">
      <h3>Água da casa <small>CESAN · últimos {r.meses} meses de consumo</small></h3>
      <div className="energia-kpis">
        <div><span>Preço médio do m³ ({rotulo(ultimo.referencia)})</span>
          <strong>{ultimo.custo_m3 != null ? reais(ultimo.custo_m3) : "—"}</strong>
          <small>média {r.custo_m3 != null ? reais(r.custo_m3) : "—"}</small></div>
        <div><span>Gasto com água</span><strong>{reais(r.total_centavos)}</strong>
          <small>{m3(r.consumo)} · {reais(Math.round(r.total_centavos / r.meses))}/mês</small></div>
        <div><span>Parte fixa da conta</span><strong>{pctFixo}%</strong>
          <small>{reais(Math.round(r.fixo_centavos / r.meses))}/mês mesmo sem consumo</small></div>
        <div><span>Consumo × ano anterior</span>
          <strong className={v == null ? "" : v <= 0 ? "pos" : "neg"}>
            {v == null ? "—" : `${v > 0 ? "+" : ""}${v.toLocaleString("pt-BR")}%`}</strong>
          <small>mesmos {r.meses_comparados} meses</small></div>
      </div>
      <GraficoAgua meses={meses} />
      <ul className="energia-leituras">
        <li><b>Parte fixa:</b> {pctFixo}% do que você pagou não depende do consumo (tarifa mínima de água + esgoto).
          {" "}Economizar água reduz só os outros {100 - pctFixo}%.</li>
        <li><b>Esgoto:</b> a CESAN cobra o esgoto sobre o mesmo volume da água, então cada m³ a menos economiza duas vezes.</li>
        <li><b>Pontualidade:</b> {atrasos === 0 ? "nenhuma conta de água paga com atraso. 👏"
          : `${atrasos} mês(es) pago(s) depois do vencimento (multa de 2% + juros vêm na conta seguinte).`}</li>
      </ul>
    </div>
  );
}

function GraficoAgua({ meses }: { meses: MesAgua[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const tema = useTema();
  useEffect(() => {
    if (!ref.current) return;
    const g = echarts.init(ref.current);
    const c = coresGrafico();
    const eixo = { color: c.suave };
    g.setOption({
      grid: { left: 56, right: 56, top: 36, bottom: 28 },
      legend: { top: 0, textStyle: eixo, itemWidth: 14, itemHeight: 10 },
      tooltip: {
        trigger: "axis",
        formatter: (ps: { dataIndex: number }[]) => {
          const m = meses[ps[0].dataIndex];
          return [`<b>${rotulo(m.referencia)}</b>`,
            `Fixa ${reais(m.fixo_centavos)} · Variável ${reais(m.variavel_centavos)}`,
            `Total ${reais(m.total_centavos)} · ${m3(m.consumo ?? 0)}`,
            m.custo_m3 != null ? `Preço médio ${reais(m.custo_m3)}/m³` : "",
            m.consumo_ano_anterior != null ? `Ano anterior ${m3(m.consumo_ano_anterior)}` : "",
            m.pago_com_atraso ? "Pago depois do vencimento" : ""].filter(Boolean).join("<br/>");
        },
      },
      xAxis: { type: "category", data: meses.map((m) => rotulo(m.referencia)), axisLabel: eixo },
      yAxis: [
        { type: "value", axisLabel: { ...eixo, formatter: (valor: number) => `R$ ${valor / 100}` },
          splitLine: { lineStyle: { color: c.borda } } },
        { type: "value", axisLabel: { ...eixo, formatter: "{value} m³" }, splitLine: { show: false } },
      ],
      series: [
        { name: "Parte fixa", type: "bar", stack: "agua", data: meses.map((m) => m.fixo_centavos),
          itemStyle: { color: "#64748b" }, barMaxWidth: 34 },
        { name: "Parte variável", type: "bar", stack: "agua", data: meses.map((m) => m.variavel_centavos),
          itemStyle: { color: "#22d3ee", borderRadius: [4, 4, 0, 0] } },
        { name: "Consumo", type: "line", yAxisIndex: 1, data: meses.map((m) => m.consumo),
          itemStyle: { color: c.texto }, symbolSize: 6 },
        { name: "Mesmo mês, ano anterior", type: "line", yAxisIndex: 1,
          data: meses.map((m) => m.consumo_ano_anterior),
          itemStyle: { color: "#71717a" }, lineStyle: { type: "dashed" }, symbol: "none" },
      ],
    });
    const redimensionar = () => g.resize();
    window.addEventListener("resize", redimensionar);
    return () => { window.removeEventListener("resize", redimensionar); g.dispose(); };
  }, [meses, tema]);
  return <div ref={ref} className="energia-grafico" />;
}
