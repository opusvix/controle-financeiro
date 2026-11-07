import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type APagar } from "../api";
import Kpi from "../componentes/Kpi";
import PagarConta from "../componentes/PagarConta";
import PainelAgua from "../componentes/PainelAgua";
import PainelEnergia from "../componentes/PainelEnergia";
import PainelPlano from "../componentes/PainelPlano";
import Rosca from "../componentes/Rosca";
import SeletorMes from "../componentes/SeletorMes";
import { useDados } from "../componentes/useDados";
import { dataBR, hojeISO, mesAtual, reais } from "../formato";

export default function Dashboard() {
  const [mes, setMes] = useState(mesAtual());
  const { dados: p, erro, recarregar } = useDados(() => api.painel(mes), [mes]);
  const aPagar = useDados(() => api.aPagar(30), []);
  const [pagando, setPagando] = useState<APagar | null>(null);
  const hoje = hojeISO();

  return (
    <>
      <header className="topo">
        <h1>Dashboard</h1>
        <SeletorMes mes={mes} aoMudar={setMes} />
      </header>
      {erro && <p className="erro">{erro}</p>}
      {p && (
        <>
          <section className="kpis">
            <Kpi titulo="Saldo disponível" valor={p.saldo_disponivel} cor="#3b82f6"
                 dica="Contas correntes e carteira. Investimentos ficam no Patrimônio." />
            <Kpi titulo="Patrimônio" valor={p.patrimonio} cor="#F38433"
                 dica="Saldo disponível + investimentos." />
            <Kpi titulo="Receitas" valor={p.receitas} cor="#22c55e" />
            <Kpi titulo="Despesas" valor={p.despesas} cor="#ef4444"
                 dica="Pela data da compra (competência). Pagamento de fatura não entra." />
            <Kpi titulo="Cartões (fatura do mês)" valor={p.cartoes_fatura_mes} cor="#14b8a6" />
          </section>

          <section className="grade-2">
            <div className="cartao-painel">
              <h3>Receitas por categoria</h3>
              <Rosca fatias={p.receitas_por_categoria} />
            </div>
            <div className="cartao-painel">
              <h3>Despesas por categoria</h3>
              <Rosca fatias={p.despesas_por_categoria} />
              <FixasVariaveis {...p.fixas_variaveis} />
            </div>
          </section>

          <section className="largura-toda"><PainelEnergia /></section>
          <section className="largura-toda"><PainelAgua /></section>
          <section className="largura-toda"><PainelPlano /></section>

          <section className="grade-2">
            <div className="cartao-painel">
              <h3>Minhas contas</h3>
              {p.contas.map((c) => (
                <div key={c.id} className="linha-conta">
                  <i style={{ background: c.cor }} />
                  <strong>{c.nome}</strong>
                  <dl>
                    <dt>Saldo atual</dt><dd className={c.saldo_atual < 0 ? "neg" : "pos"}>{reais(c.saldo_atual)}</dd>
                    <dt>Saldo previsto</dt><dd className={c.saldo_previsto < 0 ? "neg" : "pos"}>{reais(c.saldo_previsto)}</dd>
                  </dl>
                </div>
              ))}
              <Link to="/contas" className="ver-mais">Ver contas</Link>
            </div>
            <div className="coluna">
              <div className="cartao-painel">
                <h3>Pendências e alertas</h3>
                <dl className="pendencias">
                  <dt>Despesas a pagar no mês</dt><dd className="neg">{reais(p.pendencias.despesas)}</dd>
                  <dt>Receitas a receber no mês</dt><dd className="pos">{reais(p.pendencias.receitas)}</dd>
                </dl>
              </div>
              <div className="cartao-painel">
                <h3>Contas a pagar e receber · próximos 30 dias</h3>
                {aPagar.dados?.length === 0 && <p className="vazio">Nada pendente. 🎉</p>}
                <ul className="lista-apagar">
                  {aPagar.dados?.map((t) => (
                    <li key={t.id} className={t.data < hoje ? "atrasada" : ""}>
                      <span>{t.descricao}<small>{t.data < hoje ? "atrasada · " : ""}vence {dataBR(t.data)}{t.conta ? ` · ${t.conta}` : ""}</small></span>
                      <span className={t.tipo === "receita" ? "pos" : "neg"}>{reais(t.tipo === "receita" ? t.valor_centavos : -t.valor_centavos)}</span>
                      <button className="pagar" onClick={() => setPagando(t)}>{t.tipo === "receita" ? "Receber" : "Pagar"}</button>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="cartao-painel">
                <h3>Cartões de crédito</h3>
                {p.cartoes.length === 0 && <p className="vazio">Nenhum cartão cadastrado.</p>}
                {p.cartoes.map((c) => {
                  const usado = c.limite_centavos ? 1 - c.limite_disponivel / c.limite_centavos : 0;
                  return (
                    <div key={c.id} className="linha-cartao">
                      <div><strong>{c.nome}</strong> <small>{c.bandeira} final {c.final}</small></div>
                      <div className="fatura">
                        <span className={`situacao ${c.fatura_situacao.replace(" ", "-")}`}>
                          {c.fatura_situacao === "sem fatura" ? "Sem fatura no mês" : `Fatura ${c.fatura_situacao}`}</span>
                        <span className="neg">{reais(c.fatura_total)}</span>
                        {c.data_vencimento && <small>vence {dataBR(c.data_vencimento)}</small>}
                      </div>
                      <div className="barra"><b style={{ width: `${Math.min(100, usado * 100)}%` }} /></div>
                      <small>Limite disponível {reais(c.limite_disponivel)}</small>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        </>
      )}
      {pagando && <PagarConta transacao={pagando} aoFechar={() => setPagando(null)}
        aoSalvar={() => { setPagando(null); aPagar.recarregar(); recarregar(); }} />}
    </>
  );
}

/** Quanto das despesas do mês é fixo (contas da casa) e quanto é variável. */
function FixasVariaveis({ fixas, variaveis }: { fixas: number; variaveis: number }) {
  const total = fixas + variaveis;
  if (total <= 0) return null;
  const pct = (v: number) => `${Math.round((v / total) * 100)}%`;
  return (
    <div className="fixas-var" title="A marca fixa/variável fica na categoria (Cadastros).">
      <div className="barra-fv"><b style={{ width: pct(fixas) }} /><b style={{ width: pct(variaveis) }} /></div>
      <dl>
        <div><dt>Fixas (contas da casa)</dt><dd>{reais(fixas)} · {pct(fixas)}</dd></div>
        <div><dt>Variáveis</dt><dd>{reais(variaveis)} · {pct(variaveis)}</dd></div>
      </dl>
    </div>
  );
}
