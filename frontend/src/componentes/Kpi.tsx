import { reais } from "../formato";

export default function Kpi({ titulo, valor, cor = "#6b7280", dica, texto }: {
  titulo: string; valor: number; cor?: string; dica?: string; texto?: string;
}) {
  return (
    <div className="kpi" title={dica}>
      <i style={{ background: cor }} />
      <div><span>{titulo}</span><strong>{texto ?? reais(valor)}</strong></div>
    </div>
  );
}
