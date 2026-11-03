import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Cadastros from "./telas/Cadastros";
import Fatura from "./telas/Fatura";
import Cartoes from "./telas/Cartoes";
import Configuracoes from "./telas/Configuracoes";
import Contas from "./telas/Contas";
import Cupons from "./telas/Cupons";
import Dashboard from "./telas/Dashboard";
import Precos from "./telas/Precos";
import Transacoes from "./telas/Transacoes";

const MENU = [
  ["/", "Dashboard"], ["/contas", "Contas"], ["/transacoes", "Transações"], ["/cupons", "Cupons"],
  ["/precos", "Preços"], ["/cartoes", "Cartões de crédito"], ["/cadastros", "Cadastros"],
  ["/configuracoes", "Configurações"],
] as const;

export default function App() {
  return (
    <div className="app">
      <nav className="menu">
        <div className="marca">Controle<br />Financeiro</div>
        {MENU.map(([rota, nome]) => (
          <NavLink key={rota} to={rota} end={rota === "/"}>{nome}</NavLink>
        ))}
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/contas" element={<Contas />} />
          <Route path="/transacoes" element={<Transacoes />} />
          <Route path="/cupons" element={<Cupons />} />
          <Route path="/precos" element={<Precos />} />
          <Route path="/cartoes" element={<Cartoes />} />
          <Route path="/cartoes/:id" element={<Fatura />} />
          <Route path="/cadastros" element={<Cadastros />} />
          <Route path="/configuracoes" element={<Configuracoes />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
