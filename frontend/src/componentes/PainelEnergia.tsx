import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import { api, type MesEnergia } from "../api";
import { reais } from "../formato";
import { useDados } from "./useDados";

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const COR = { escelsa: "#60a5fa", solar: "#fbbf24", consumo: "#ececf1", anterior: "#71717a" };
const MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const rotulo = (ref: string) => `${MES[Number(ref.slice(5)) - 1]}/${ref.slice(2, 4)}`;
const kwh = (n: number) => `${Math.round(n).toLocaleString("pt-BR")} kWh`;

/**
 * Luz da casa: a fatura da EDP Escelsa + a cobrança da EDP Solar de cada mês de consumo.
 * Pense num custo-padrão: o "preço real do kWh" é tudo o que saiu do bolso ÷ o que a casa consumiu.
 */
export default function PainelEnergia() {
  const { dados, erro } = useDados(() => api.energia(12), []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!dados) return null;
  const { meses, resumo: r } = dados;
  if (!meses.length) return (
    <div className="cartao-painel"><h3>Energia da casa</h3>
      <p className="vazio">Sem fichas de luz ainda. Rode scripts\importar_contas.bat para ler os PDFs.</p></div>);

  const ultimo = meses[meses.length - 1];
  const fixoMes = meses.length ? Math.round(r.fixos_centavos / meses.length) : 0;
  const maior = meses.reduce((a, b) => ((b.consumo ?? 0) > (a.consumo ?? 0) ? b : a));
  const menor = meses.reduce((a, b) => ((b.consumo ?? Infinity) < (a.consumo ?? Infinity) ? b : a));
  const v = r.variacao_consumo_pct;

  return (
    <div className="cartao-painel energia">
      <h3>Energia da casa <small>Escelsa + Solar · últimos {r.meses} meses de consumo</small></h3>
      <div className="energia-kpis">
        <div><span>Preço real do kWh ({rotulo(ultimo.referencia)})</span>
          <strong>{ultimo.custo_kwh != null ? reais(ultimo.custo_kwh) : "—"}</strong>
          <small>média {r.custo_kwh != null ? reais(r.custo_kwh) : "—"}</small></div>
        <div><span>Gasto com luz</span><strong>{reais(r.total_centavos)}</strong>
          <small>{kwh(r.consumo)} · {reais(Math.round(r.total_centavos / r.meses))}/mês</small></div>
        <div><span>Economia da Solar</span><strong className="pos">{reais(r.economia_solar_centavos)}</strong>
          <small>desconto de 10% nos créditos</small></div>
        <div><span>Consumo × ano anterior</span>
          <strong className={v == null ? "" : v <= 0 ? "pos" : "neg"}>
            {v == null ? "—" : `${v > 0 ? "+" : ""}${v.toLocaleString("pt-BR")}%`}</strong>
          <small>mesmos {r.meses_comparados} meses</small></div>
      </div>
      <GraficoEnergia meses={meses} />
      <ul className="energia-leituras">
        <li><b>Parte fixa:</b> iluminação pública{r.seguro_centavos ? " e seguro" : ""} somam
          {" "}{reais(fixoMes)}/mês, mesmo sem acender uma lâmpada. Some a isso a taxa mínima de 50 kWh do bifásico.</li>
        {maior.custo_kwh && menor.custo_kwh && maior !== menor && (
          <li><b>Escala:</b> em {rotulo(maior.referencia)} ({kwh(maior.consumo ?? 0)}) o kWh saiu a {reais(maior.custo_kwh)};
            {" "}em {rotulo(menor.referencia)} ({kwh(menor.consumo ?? 0)}), a {reais(menor.custo_kwh)}.
            {" "}Quanto menos se consome, mais pesa a parte fixa no preço de cada kWh.</li>)}
        {r.seguro_centavos > 0 && (
          <li><b>Seguro 0800:</b> {reais(r.seguro_centavos)} no período. Cancelando, essa linha some.</li>)}
        {r.bandeira_centavos > 0 && (
          <li><b>Bandeira tarifária:</b> {reais(r.bandeira_centavos)} a mais no período (amarela/vermelha).</li>)}
        <li><b>Pontualidade:</b> {r.meses_com_atraso === 0 && r.multa_centavos === 0
          ? "nenhuma conta de luz paga com atraso. 👏"
          : `${r.meses_com_atraso} mês(es) com pagamento depois do vencimento${r.multa_centavos ? `, ${reais(r.multa_centavos)} de multa e juros` : ""}.`}</li>
      </ul>
    </div>
  );
}

function GraficoEnergia({ meses }: { meses: MesEnergia[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const g = echarts.init(ref.current);
    const eixoTexto = { color: "#a1a1aa" };
    g.setOption({
      grid: { left: 56, right: 56, top: 36, bottom: 28 },
      legend: { top: 0, textStyle: eixoTexto, itemWidth: 14, itemHeight: 10 },
      tooltip: {
        trigger: "axis",
        formatter: (ps: { dataIndex: number }[]) => {
          const m = meses[ps[0].dataIndex];
          return [`<b>${rotulo(m.referencia)}</b>`,
            `Escelsa ${reais(m.escelsa_centavos)} · Solar ${reais(m.solar_centavos)}`,
            `Total ${reais(m.total_centavos)} · ${kwh(m.consumo ?? 0)}`,
            m.custo_kwh != null ? `Preço real ${reais(m.custo_kwh)}/kWh` : "",
            m.consumo_ano_anterior != null ? `Ano anterior ${kwh(m.consumo_ano_anterior)}` : "",
            m.economia_centavos ? `Economia Solar ${reais(m.economia_centavos)}` : "",
            m.bandeira ? `Bandeira ${m.bandeira}` : "",
            m.dias_atraso ? `Pago ${m.dias_atraso} dia(s) depois do vencimento` : "",
          ].filter(Boolean).join("<br/>");
        },
      },
      xAxis: { type: "category", data: meses.map((m) => rotulo(m.referencia)), axisLabel: eixoTexto },
      yAxis: [
        { type: "value", axisLabel: { ...eixoTexto, formatter: (c: number) => `R$ ${c / 100}` },
          splitLine: { lineStyle: { color: "#3a3a41" } } },
        { type: "value", axisLabel: { ...eixoTexto, formatter: "{value} kWh" }, splitLine: { show: false } },
      ],
      series: [
        { name: "Escelsa", type: "bar", stack: "luz", data: meses.map((m) => m.escelsa_centavos),
          itemStyle: { color: COR.escelsa }, barMaxWidth: 34 },
        { name: "Solar", type: "bar", stack: "luz", data: meses.map((m) => m.solar_centavos),
          itemStyle: { color: COR.solar, borderRadius: [4, 4, 0, 0] } },
        { name: "Consumo", type: "line", yAxisIndex: 1, data: meses.map((m) => m.consumo),
          itemStyle: { color: COR.consumo }, symbolSize: 6 },
        { name: "Mesmo mês, ano anterior", type: "line", yAxisIndex: 1,
          data: meses.map((m) => m.consumo_ano_anterior),
          itemStyle: { color: COR.anterior }, lineStyle: { type: "dashed" }, symbol: "none" },
      ],
    });
    const redimensionar = () => g.resize();
    window.addEventListener("resize", redimensionar);
    return () => { window.removeEventListener("resize", redimensionar); g.dispose(); };
  }, [meses]);
  return <div ref={ref} className="energia-grafico" />;
}
