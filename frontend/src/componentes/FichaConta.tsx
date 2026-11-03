import { useEffect, useState } from "react";
import { api, type Ficha, type TipoFicha } from "../api";
import { paraCentavos, reais } from "../formato";

/**
 * Ficha da conta: o que a fatura diz além do valor (consumo, bandeira, multa e juros).
 * Valor = volume × preço + penalidades: com o consumo, o app calcula o preço por kWh ou m³.
 */
export const TIPOS: { tipo: TipoFicha; nome: string }[] = [
  { tipo: "energia", nome: "Energia (EDP Escelsa)" },
  { tipo: "energia_solar", nome: "Energia solar (créditos EDP Solar)" },
  { tipo: "agua", nome: "Água (CESAN)" },
  { tipo: "internet", nome: "Internet" },
  { tipo: "telefone", nome: "Telefone" },
  { tipo: "saude", nome: "Plano de saúde" },
  { tipo: "outra", nome: "Outra conta da casa" },
];
const BANDEIRAS = [["verde", "Verde"], ["amarela", "Amarela"], ["vermelha1", "Vermelha patamar 1"],
  ["vermelha2", "Vermelha patamar 2"], ["escassez", "Escassez hídrica"]];

export type FichaForm = {
  tipo: string; referencia: string; consumo: string; kwh_compensado: string; bandeira: string;
  bandeira_valor: string; multa: string; vidas: string;
  cip: number | null; terceiros: number | null; arquivo: string | null;   // só leitura (vêm do PDF)
};

const num = (v: number | null) => (v == null ? "" : String(v).replace(".", ","));
const din = (c: number | null) => (c == null ? "" : (c / 100).toFixed(2).replace(".", ","));

function paraForm(f: Ficha): FichaForm {
  return {
    tipo: f.tipo ?? "", referencia: f.referencia ?? "", consumo: num(f.consumo),
    kwh_compensado: num(f.kwh_compensado), bandeira: f.bandeira ?? "",
    bandeira_valor: din(f.bandeira_centavos), multa: din(f.multa_juros_centavos), vidas: num(f.vidas),
    cip: f.cip_centavos, terceiros: f.terceiros_centavos, arquivo: f.arquivo,
  };
}

const numero = (t: string) => (t.trim() === "" ? null : Number(t.replace(/\./g, "").replace(",", ".")));
const centavos = (t: string) => (t.trim() === "" ? null : paraCentavos(t));

/** Grava a ficha (ou apaga, se o tipo ficou vazio). Lança erro com mensagem amigável. */
export async function gravarFicha(id: number, f: FichaForm, tinha: boolean) {
  if (!f.tipo) { if (tinha) await api.apagarFicha(id); return; }
  const d = {
    tipo: f.tipo, referencia: f.referencia || null, consumo: numero(f.consumo),
    kwh_compensado: numero(f.kwh_compensado), bandeira: f.bandeira || null,
    bandeira_centavos: centavos(f.bandeira_valor), multa_juros_centavos: centavos(f.multa),
    vidas: numero(f.vidas),
  };
  for (const [k, v] of Object.entries(d))
    if (typeof v === "number" && Number.isNaN(v)) throw new Error(`Número inválido na ficha (${k}).`);
  await api.gravarFicha(id, d);
}

/** Carrega a ficha gravada (ou a sugestão do mês anterior da mesma conta). */
export function useFicha(id: number) {
  const [form, setForm] = useState<FichaForm | null>(null);
  const [gravada, setGravada] = useState(false);
  useEffect(() => {
    api.ficha(id).then((f) => { setForm(paraForm(f)); setGravada(f.gravada); }).catch(() => setForm(null));
  }, [id]);
  return { form, setForm, gravada };
}

export default function FichaConta({ form: f, aoMudar, valorCentavos }: {
  form: FichaForm; aoMudar: (f: FichaForm) => void; valorCentavos: number | null;
}) {
  const muda = (campo: keyof FichaForm, v: string) => aoMudar({ ...f, [campo]: v });
  const consumo = numero(f.consumo);
  const vidas = numero(f.vidas);
  const unidade = f.tipo === "agua" ? "m³" : "kWh";
  const preco = valorCentavos && consumo ? reais(Math.round(valorCentavos / consumo)) : null;
  return (
    <fieldset className="ficha-conta">
      <legend>Ficha da conta</legend>
      <div className="duas">
        <label>Tipo
          <select value={f.tipo} onChange={(e) => muda("tipo", e.target.value)}>
            <option value="">(sem ficha)</option>
            {TIPOS.map((t) => <option key={t.tipo} value={t.tipo}>{t.nome}</option>)}
          </select></label>
        {f.tipo && <label>Mês de consumo
          <input type="month" value={f.referencia} onChange={(e) => muda("referencia", e.target.value)} /></label>}
      </div>
      {(f.tipo === "energia" || f.tipo === "agua") && (
        <div className="duas">
          <label>Consumo ({unidade})
            <input inputMode="decimal" value={f.consumo} onChange={(e) => muda("consumo", e.target.value)} /></label>
          {f.tipo === "energia" && <label>kWh compensados (Solar)
            <input inputMode="decimal" value={f.kwh_compensado} onChange={(e) => muda("kwh_compensado", e.target.value)} /></label>}
        </div>
      )}
      {f.tipo === "energia_solar" && (
        <label>kWh de créditos
          <input inputMode="decimal" value={f.kwh_compensado} onChange={(e) => muda("kwh_compensado", e.target.value)} /></label>
      )}
      {f.tipo === "energia" && (
        <div className="duas">
          <label>Bandeira tarifária
            <select value={f.bandeira} onChange={(e) => muda("bandeira", e.target.value)}>
              <option value="">—</option>
              {BANDEIRAS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
            </select></label>
          <label>Adicional de bandeira (R$)
            <input inputMode="decimal" value={f.bandeira_valor} onChange={(e) => muda("bandeira_valor", e.target.value)} /></label>
        </div>
      )}
      {f.tipo === "saude" && (
        <label>Vidas no plano
          <input inputMode="numeric" value={f.vidas} onChange={(e) => muda("vidas", e.target.value)} /></label>
      )}
      {f.tipo && (
        <label>Multa e juros por atraso (R$)
          <input inputMode="decimal" value={f.multa} onChange={(e) => muda("multa", e.target.value)} /></label>
      )}
      {f.tipo === "energia" && (f.cip != null || f.terceiros != null) && (
        <p className="dica">Iluminação pública {reais(f.cip ?? 0)} · serviços de terceiros (seguro) {reais(f.terceiros ?? 0)}
          {" "}— não dependem do consumo.</p>)}
      {f.arquivo && <p className="dica">Lida do PDF {f.arquivo}.</p>}
      {preco && <p className="dica">Preço efetivo: <b>{preco} por {unidade}</b> (valor ÷ consumo).</p>}
      {f.tipo === "saude" && valorCentavos && vidas ? (
        <p className="dica">Custo por vida: <b>{reais(Math.round(valorCentavos / vidas))}</b>.</p>) : null}
    </fieldset>
  );
}
