/** Tema claro/escuro do app, com botão de escolha.
 *
 * O tema fica num atributo `data-tema` no <html> ("claro" ou nada = escuro) e
 * é lembrado no localStorage. O index.html aplica o tema salvo antes do React
 * subir, para não haver "piscada". Os gráficos (ECharts) leem as cores pelas
 * variáveis CSS e se redesenham quando o tema muda (evento cf-tema-mudou).
 */
import { useEffect, useState } from "react";

export type Tema = "claro" | "escuro";

const CHAVE = "cf-tema";
const EVENTO = "cf-tema-mudou";

export function temaAtual(): Tema {
  return document.documentElement.getAttribute("data-tema") === "claro" ? "claro" : "escuro";
}

export function aplicarTema(t: Tema): void {
  const raiz = document.documentElement;
  if (t === "claro") raiz.setAttribute("data-tema", "claro");
  else raiz.removeAttribute("data-tema");
  try { localStorage.setItem(CHAVE, t); } catch { /* modo anônimo, etc. */ }
  window.dispatchEvent(new Event(EVENTO));
}

export function alternarTema(): void {
  aplicarTema(temaAtual() === "claro" ? "escuro" : "claro");
}

/** Hook que devolve o tema atual e re-renderiza quando ele muda. */
export function useTema(): Tema {
  const [t, setT] = useState<Tema>(temaAtual);
  useEffect(() => {
    const aoMudar = () => setT(temaAtual());
    window.addEventListener(EVENTO, aoMudar);
    return () => window.removeEventListener(EVENTO, aoMudar);
  }, []);
  return t;
}

/** Cores dos gráficos lidas das variáveis CSS do tema vigente. */
export function coresGrafico(): { texto: string; suave: string; borda: string; painel: string } {
  const s = getComputedStyle(document.documentElement);
  const ler = (nome: string, padrao: string) => s.getPropertyValue(nome).trim() || padrao;
  return {
    texto: ler("--texto", "#ececf1"),
    suave: ler("--suave", "#a1a1aa"),
    borda: ler("--borda", "#3a3a41"),
    painel: ler("--painel", "#26262b"),
  };
}
