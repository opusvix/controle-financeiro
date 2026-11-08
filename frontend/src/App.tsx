import { useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { alternarTema, useTema } from "./tema";
import { useDados } from "./componentes/useDados";
import Ajuda from "./telas/Ajuda";
import Cadastros from "./telas/Cadastros";
import Fatura from "./telas/Fatura";
import Cartoes from "./telas/Cartoes";
import Conciliacao from "./telas/Conciliacao";
import Configuracoes from "./telas/Configuracoes";
import Contas from "./telas/Contas";
import Cupons from "./telas/Cupons";
import Dashboard from "./telas/Dashboard";
import Precos from "./telas/Precos";
import Relatorios from "./telas/Relatorios";
import Transacoes from "./telas/Transacoes";

const MENU = [
  ["/", "Dashboard"], ["/contas", "Contas"], ["/transacoes", "Transações"], ["/cupons", "Cupons"],
  ["/precos", "Preços"], ["/relatorios", "Relatórios"], ["/cartoes", "Cartões de crédito"],
  ["/conciliacao", "Conciliação"], ["/cadastros", "Cadastros"], ["/configuracoes", "Configurações"],
  ["/ajuda", "Ajuda"],
] as const;

function SeloDemo() {
  const saude = useDados(api.saude);
  const [reiniciando, setReiniciando] = useState(false);
  if (!saude.dados?.modo_demo) return null;

  async function reiniciar() {
    if (!confirm("Isto apaga tudo que você mexeu e volta a demonstração ao estado de exemplo. Continuar?"))
      return;
    setReiniciando(true);
    try {
      await api.reiniciarDemo();
      location.reload();   // recarrega para todas as telas pegarem os dados novos
    } catch (e) {
      alert((e as Error).message);
      setReiniciando(false);
    }
  }

  return (
    <div className="bloco-demo">
      <span className="selo-demo">Demonstração</span>
      <button className="btn-demo" onClick={reiniciar} disabled={reiniciando}>
        {reiniciando ? "Reiniciando…" : "↺ Reiniciar demonstração"}
      </button>
    </div>
  );
}

export default function App() {
  const tema = useTema();
  return (
    <div className="app">
      <nav className="menu">
        <div className="marca">Controle<br />Financeiro</div>
        <SeloDemo />
        {MENU.map(([rota, nome]) => (
          <NavLink key={rota} to={rota} end={rota === "/"}>{nome}</NavLink>
        ))}
        <button className="btn-tema" onClick={alternarTema}
          title="Alternar entre tema claro e escuro">
          {tema === "claro" ? "☾ Tema escuro" : "☀ Tema claro"}
        </button>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/contas" element={<Contas />} />
          <Route path="/transacoes" element={<Transacoes />} />
          <Route path="/cupons" element={<Cupons />} />
          <Route path="/precos" element={<Precos />} />
          <Route path="/relatorios" element={<Relatorios />} />
          <Route path="/cartoes" element={<Cartoes />} />
          <Route path="/cartoes/:id" element={<Fatura />} />
          <Route path="/conciliacao" element={<Conciliacao />} />
          <Route path="/cadastros" element={<Cadastros />} />
          <Route path="/configuracoes" element={<Configuracoes />} />
          <Route path="/ajuda" element={<Ajuda />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
