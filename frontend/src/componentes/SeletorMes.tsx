import { nomeMes, somarMes } from "../formato";

export default function SeletorMes({ mes, aoMudar }: { mes: string; aoMudar: (m: string) => void }) {
  return (
    <div className="seletor-mes">
      <button onClick={() => aoMudar(somarMes(mes, -1))} aria-label="Mês anterior">‹</button>
      <span>{nomeMes(mes)}</span>
      <button onClick={() => aoMudar(somarMes(mes, 1))} aria-label="Próximo mês">›</button>
    </div>
  );
}
