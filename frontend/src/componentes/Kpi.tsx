import { reais } from "../formato";

export default function Kpi({ titulo, valor, cor, dica }: {
  titulo: string; valor: number; cor: string; dica?: string;
}) {
  return (
    <div className="kpi" title={dica}>
      <i style={{ background: cor }} />
      <div><span>{titulo}</span><strong>{reais(valor)}</strong></div>
    </div>
  );
}
