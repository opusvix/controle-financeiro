import type { ReactNode } from "react";

export default function Modal({ titulo, aoFechar, children }: {
  titulo: string; aoFechar: () => void; children: ReactNode;
}) {
  return (
    <div className="modal-fundo" onMouseDown={aoFechar}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-label={titulo}>
        <header><h2>{titulo}</h2><button className="fechar" onClick={aoFechar} aria-label="Fechar">×</button></header>
        {children}
      </div>
    </div>
  );
}
