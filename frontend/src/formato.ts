// Formatação brasileira e conversão de valores digitados.

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export const reais = (centavos: number) => brl.format(centavos / 100);

/** "1.234,56" | "8,98" | "8.98" -> centavos. Devolve null se não for número. */
export function paraCentavos(texto: string): number | null {
  let t = texto.replace(/[R$\s]/g, "");
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  const [inteiro, dec = ""] = t.split(".");
  return Number(inteiro) * 100 + Number((dec + "00").slice(0, 2));
}

export const dataBR = (iso: string) => iso.split("-").reverse().join("/");

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
  "setembro", "outubro", "novembro", "dezembro"];

export const nomeMes = (comp: string) => {
  const [a, m] = comp.split("-").map(Number);
  return `${MESES[m - 1]} ${a}`;
};

export const hojeISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export const mesAtual = () => hojeISO().slice(0, 7);

export function somarMes(comp: string, n: number) {
  const [a, m] = comp.split("-").map(Number);
  const total = a * 12 + (m - 1) + n;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}
