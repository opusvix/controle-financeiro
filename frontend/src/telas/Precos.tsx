import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type ProdutoPreco } from "../api";
import { useDados } from "../componentes/useDados";
import { dataBR, reais } from "../formato";

const porUnidade = (centavos: number, unidade: string) => `${reais(centavos)}/${unidade}`;
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

/**
 * Preços (Fase 3): cada produto dos cupons ao longo do tempo e entre as lojas, sem marca.
 * Comparar quantidades diferentes só é justo pelo preço por unidade base (R$/kg, R$/l, R$/un),
 * então é esse o número que a tela mostra.
 */
export default function Precos() {
  const { dados, erro } = useDados(() => api.precos(), []);
  if (erro) return <><header className="topo"><h1>Preços</h1></header><p className="erro">{erro}</p></>;
  if (!dados) return <><header className="topo"><h1>Preços</h1></header><p className="suave">Carregando…</p></>;

  const { grupos, resumo: r } = dados;
  return (
    <>
      <header className="topo"><h1>Preços</h1></header>
      <p className="dica" style={{ marginTop: -8, maxWidth: 680 }}>
        Aqui cada produto que você registra nos cupons vira uma série de preço. A comparação é pelo
        <b> preço por unidade</b> (R$/kg, R$/l ou R$/un), que é o único jeito justo de comparar compras
        de pesos diferentes — e <b>sem marca</b>, para enxergar só o produto.
      </p>

      {r.produtos === 0 ? (
        <div className="cartao-painel espaco">
          <p className="vazio">Ainda não há preços para comparar.</p>
          <p className="dica">Registre cupons na tela <Link to="/cupons">Cupons</Link> (mesmo os já lançados,
            com a opção “Só registrar os preços”). A partir de duas compras do mesmo produto, a variação aparece aqui.</p>
        </div>
      ) : (
        <>
          <div className="energia-kpis">
            <div><span>Produtos acompanhados</span><strong>{r.produtos}</strong>
              <small>{r.com_historico} com 2+ compras</small></div>
            <div><span>Compras registradas</span><strong>{r.compras}</strong>
              <small>itens de cupom</small></div>
            <div><span>Lojas</span><strong>{r.lojas}</strong>
              <small>comparadas entre si</small></div>
            <div><span>Movimento de preço</span>
              <strong><span className="neg">↑{r.subindo}</span> <span className="pos">↓{r.caindo}</span></strong>
              <small>subindo × caindo (última compra)</small></div>
          </div>

          {grupos.map((g) => (
            <section key={g.categoria} className="cartao-painel espaco">
              <h3>{g.categoria}{g.categoria_mae && g.categoria_mae !== g.categoria && (
                <small> · {g.categoria_mae}</small>)}</h3>
              <table className="tabela">
                <thead><tr>
                  <th>Produto</th><th className="num">Preço agora</th><th className="num">Variação</th>
                  <th>Mais barato</th><th className="num">Compras</th><th></th>
                </tr></thead>
                <tbody>
                  {g.produtos.map((p) => <Produto key={p.nome + p.unidade} p={p} />)}
                </tbody>
              </table>
            </section>
          ))}

          <p className="dica">
            A <b>variação</b> compara a compra mais recente com a anterior do mesmo produto. Preço subindo
            aparece em <span className="neg">vermelho</span> (pesa no bolso); caindo, em <span className="pos">verde</span>.
            Abra uma linha para ver o histórico e o preço em cada loja.
          </p>
        </>
      )}
    </>
  );
}

function Produto({ p }: { p: ProdutoPreco }) {
  const [aberto, setAberto] = useState(false);
  const v = p.variacao_pct;
  return (
    <>
      <tr className="grupo-cartao" onClick={() => setAberto(!aberto)}>
        <td>{p.nome} <small>({p.unidade})</small></td>
        <td className="num">{porUnidade(p.preco_atual_centavos, p.unidade)}
          <small className="dica-linha">{dataBR(p.data_atual)} · {p.loja_atual}</small></td>
        <td className="num">{v == null
          ? <small className="suave">1ª compra</small>
          : <b className={v > 0 ? "neg" : v < 0 ? "pos" : "suave"}>{v > 0 ? "↑" : v < 0 ? "↓" : "="} {pct(v)}</b>}
          {p.preco_anterior_centavos != null && (
            <small className="dica-linha">antes {reais(p.preco_anterior_centavos)}</small>)}</td>
        <td>{p.lojas > 1 && p.melhor_loja
          ? <>{p.melhor_loja} <small className="dica-linha">{porUnidade(p.por_loja[0].preco_centavos, p.unidade)}</small></>
          : <small className="suave">uma loja só</small>}</td>
        <td className="num">{p.compras}</td>
        <td className="num"><span className="seta">{aberto ? "▾" : "▸"}</span></td>
      </tr>
      {aberto && (
        <tr className="filho"><td colSpan={6}>
          <Detalhe p={p} />
        </td></tr>
      )}
    </>
  );
}

function Detalhe({ p }: { p: ProdutoPreco }) {
  const serie = p.serie;
  return (
    <div className="preco-detalhe">
      <Sparkline p={p} />
      <div className="preco-colunas">
        <div>
          <b>Histórico</b>
          <ul className="chips">
            {serie.map((s, i) => (
              <li key={i}>{dataBR(s.data)} · {porUnidade(s.preco_centavos, p.unidade)}
                <small> · {s.loja}</small></li>
            ))}
          </ul>
        </div>
        {p.por_loja.length > 1 && (
          <div>
            <b>Preço em cada loja (última compra)</b>
            <ul className="chips">
              {p.por_loja.map((l) => (
                <li key={l.loja} className={l.loja === p.melhor_loja ? "melhor" : ""}>
                  {l.loja} · {porUnidade(l.preco_centavos, p.unidade)}
                  {l.loja === p.melhor_loja && <small> ✓ mais barato</small>}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="dica">
          Média {porUnidade(p.media_centavos, p.unidade)} · menor {porUnidade(p.menor_centavos, p.unidade)}{" "}
          ({dataBR(p.menor_data)}) · maior {porUnidade(p.maior_centavos, p.unidade)}.
        </div>
      </div>
    </div>
  );
}

/** Mini-gráfico de linha (SVG) da série de preços, da compra mais antiga à mais recente. */
function Sparkline({ p }: { p: ProdutoPreco }) {
  const vals = p.serie.map((s) => s.preco_centavos);
  if (vals.length < 2) return null;
  const w = 260, h = 56, pad = 6;
  const min = Math.min(...vals), max = Math.max(...vals);
  const faixa = max - min || 1;
  const x = (i: number) => pad + (i * (w - 2 * pad)) / (vals.length - 1);
  const y = (val: number) => h - pad - ((val - min) / faixa) * (h - 2 * pad);
  const d = vals.map((val, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(val).toFixed(1)}`).join(" ");
  const sobe = vals[vals.length - 1] > vals[0];
  const cor = sobe ? "var(--vermelho, #ef4444)" : "var(--verde, #22c55e)";
  return (
    <svg className="preco-spark" viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="img"
      aria-label="evolução do preço">
      <path d={d} fill="none" stroke={cor} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {vals.map((val, i) => <circle key={i} cx={x(i)} cy={y(val)} r={2.5} fill={cor} />)}
    </svg>
  );
}
