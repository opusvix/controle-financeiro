import * as echarts from "echarts/core";
import { PieChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import type { Fatia } from "../api";
import { reais } from "../formato";
import { coresGrafico, useTema } from "../tema";

echarts.use([PieChart, TooltipComponent, CanvasRenderer]);

/** Gráfico de rosca com o total no centro. O total é a soma das fatias. */
export default function Rosca({ fatias }: { fatias: Fatia[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const tema = useTema();
  const total = fatias.reduce((s, f) => s + f.total, 0);

  useEffect(() => {
    if (!ref.current) return;
    const grafico = echarts.init(ref.current);
    const c = coresGrafico();
    grafico.setOption({
      tooltip: {
        trigger: "item",
        formatter: (p: { name: string; value: number; percent: number }) =>
          `${p.name}<br/>${reais(p.value)} (${p.percent.toLocaleString("pt-BR")}%)`,
      },
      series: [{
        type: "pie", radius: ["58%", "80%"], label: { show: false },
        itemStyle: { borderColor: c.painel, borderWidth: 2 },
        data: fatias.map((f) => ({ name: f.categoria, value: f.total, itemStyle: { color: f.cor } })),
      }],
    });
    const redimensionar = () => grafico.resize();
    window.addEventListener("resize", redimensionar);
    return () => { window.removeEventListener("resize", redimensionar); grafico.dispose(); };
  }, [fatias, tema]);

  if (!fatias.length) return <p className="vazio">Sem lançamentos neste mês.</p>;
  return (
    <div className="rosca">
      <div ref={ref} className="rosca-grafico" />
      <div className="rosca-centro"><strong>{reais(total)}</strong><span>Total</span></div>
      <ul className="legenda">
        {fatias.map((f) => (
          <li key={f.categoria_id}>
            <i style={{ background: f.cor }} />{f.categoria}
            <span>{reais(f.total)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
