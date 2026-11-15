import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import type { Fatia } from "../api";
import { reais } from "../formato";
import { coresGrafico, useTema } from "../tema";

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

// Paleta de reserva (cores bem distintas) para separar categorias de cor parecida.
const PALETA = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#a855f7", "#ec4899", "#14b8a6",
  "#eab308", "#6366f1", "#f97316", "#22c55e", "#06b6d4", "#d946ef", "#84cc16"];

const rgb = (h: string): [number, number, number] =>
  [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
const distancia = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

/** Mantém a cor própria de cada categoria, mas troca as que ficam parecidas demais
 *  (ex.: Aposentadoria × Outras receitas, ambas cinza) por uma cor distinta da paleta. */
function coresDistintas(cores: string[]): string[] {
  const usadas: number[][] = [];
  const hex = /^#[0-9a-fA-F]{6}$/;
  const perto = (c: string) => hex.test(c) && usadas.some((u) => distancia(u, rgb(c)) < 70);
  return cores.map((c0) => {
    let cor = hex.test(c0) ? c0 : PALETA[0];
    if (perto(cor)) cor = PALETA.find((p) => !perto(p)) ?? cor;
    if (hex.test(cor)) usadas.push(rgb(cor));
    return cor;
  });
}

/** Gráfico de COLUNAS por categoria (substitui a rosca, que embolava com muitas categorias). */
export default function BarrasCategoria({ fatias }: { fatias: Fatia[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const tema = useTema();
  const ordenadas = [...fatias].sort((a, b) => b.total - a.total);
  const cores = coresDistintas(ordenadas.map((f) => f.cor));
  const total = ordenadas.reduce((s, f) => s + f.total, 0);

  useEffect(() => {
    if (!ref.current || !ordenadas.length) return;
    const grafico = echarts.init(ref.current);
    const c = coresGrafico();
    const poucos = ordenadas.length <= 7;
    // Em reais; valores grandes viram "R$ 1,2 mil" para o eixo não ficar gigante.
    const curto = (v: number) => v >= 100000
      ? `R$ ${(v / 100000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil` : reais(v);
    grafico.setOption({
      grid: { left: 8, right: 12, top: poucos ? 24 : 10, bottom: 4, containLabel: true },
      tooltip: {
        trigger: "item",
        formatter: (p: { name: string; value: number }) =>
          `${p.name}<br/>${reais(p.value)} (${((p.value / total) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%)`,
      },
      xAxis: {
        type: "category", data: ordenadas.map((f) => f.categoria),
        axisLabel: {
          color: c.suave, interval: 0, rotate: 30, hideOverlap: true,
          formatter: (n: string) => (n.length > 11 ? `${n.slice(0, 10)}…` : n),
        },
        axisTick: { show: false }, axisLine: { lineStyle: { color: c.borda } },
      },
      yAxis: {
        type: "value", axisLabel: { color: c.suave, formatter: curto },
        splitLine: { lineStyle: { color: c.borda } },
      },
      series: [{
        type: "bar", barMaxWidth: 46,
        data: ordenadas.map((f, i) => ({ value: f.total, itemStyle: { color: cores[i], borderRadius: [4, 4, 0, 0] } })),
        label: { show: poucos, position: "top", color: c.suave, formatter: (p: { value: number }) => curto(p.value) },
      }],
    });
    const redimensionar = () => grafico.resize();
    window.addEventListener("resize", redimensionar);
    return () => { window.removeEventListener("resize", redimensionar); grafico.dispose(); };
  }, [fatias, tema]);

  if (!fatias.length) return <p className="vazio">Sem lançamentos neste mês.</p>;
  return (
    <div className="barras-cat">
      <div ref={ref} className="barras-grafico" />
      <ul className="legenda">
        {ordenadas.map((f, i) => (
          <li key={f.categoria_id}><i style={{ background: cores[i] }} />{f.categoria}
            <span>{reais(f.total)}</span></li>
        ))}
      </ul>
    </div>
  );
}
