"""Painel de energia: junta a fatura da EDP Escelsa e a cobrança da EDP Solar de cada mês de consumo.

Ideia (como um custo-padrão de fábrica): custo da energia do mês = Escelsa + Solar.
- Escelsa: taxa mínima (50 kWh do bifásico) + iluminação pública + seguro + bandeira. Quase fixa.
- Solar: créditos (kWh acima do mínimo) com 10% de desconto. O desconto é a economia.
Dividindo pelo consumo, sai o preço real do kWh da casa.
"""
import sqlite3
from datetime import date


def _menos_um_ano(ref: str) -> str:
    return f"{int(ref[:4]) - 1}{ref[4:]}"


def _dias(de: str | None, ate: str | None) -> int | None:
    if not de or not ate:
        return None
    return (date.fromisoformat(ate) - date.fromisoformat(de)).days


def painel(con: sqlite3.Connection, meses: int = 12) -> dict:
    linhas = con.execute(
        """SELECT f.tipo, f.referencia, f.consumo, f.kwh_compensado, f.bandeira, f.bandeira_centavos,
                  f.cip_centavos, f.terceiros_centavos, f.multa_juros_centavos, f.desconto_centavos,
                  t.valor_centavos, t.data, t.vencimento, t.pago
           FROM conta_ficha f JOIN transacao t ON t.id = f.transacao_id
           WHERE f.tipo IN ('energia', 'energia_solar') AND f.referencia IS NOT NULL
           ORDER BY f.referencia""").fetchall()
    por_mes: dict[str, dict] = {}
    for r in linhas:
        m = por_mes.setdefault(r["referencia"], {
            "referencia": r["referencia"], "consumo": None, "kwh_compensado": None,
            "escelsa_centavos": 0, "solar_centavos": 0, "fixos_centavos": 0, "seguro_centavos": 0, "bandeira": None,
            "bandeira_centavos": 0, "multa_centavos": 0, "economia_centavos": 0,
            "dias_atraso": 0, "tem_escelsa": False, "tem_solar": False})
        m["multa_centavos"] += r["multa_juros_centavos"] or 0
        atraso = _dias(r["vencimento"], r["data"]) if r["pago"] else None
        if atraso and atraso > 0:
            m["dias_atraso"] = max(m["dias_atraso"], atraso)
        if r["tipo"] == "energia":
            m["tem_escelsa"] = True
            m["escelsa_centavos"] += r["valor_centavos"]
            m["consumo"] = r["consumo"]
            m["kwh_compensado"] = r["kwh_compensado"]
            m["bandeira"] = r["bandeira"]
            m["bandeira_centavos"] += r["bandeira_centavos"] or 0
            m["fixos_centavos"] += (r["cip_centavos"] or 0) + (r["terceiros_centavos"] or 0)
            m["seguro_centavos"] += r["terceiros_centavos"] or 0
        else:
            m["tem_solar"] = True
            m["solar_centavos"] += r["valor_centavos"]
            m["economia_centavos"] += r["desconto_centavos"] or 0
            if m["consumo"] is None:
                m["consumo"] = r["consumo"]

    historico = {r["referencia"]: r["consumo"] for r in con.execute(
        "SELECT referencia, consumo FROM conta_historico WHERE tipo = 'energia'")}

    # Só meses com a fatura da Escelsa: sem ela o consumo e a parte fixa ficam incompletos.
    lista = [m for m in por_mes.values() if m["tem_escelsa"]][-meses:]
    for m in lista:
        m["total_centavos"] = m["escelsa_centavos"] + m["solar_centavos"]
        c = m["consumo"]
        m["custo_kwh"] = round(m["total_centavos"] / c) if c else None
        # Preço só da energia: tira iluminação pública e seguro, que não dependem do consumo.
        m["custo_kwh_energia"] = round((m["total_centavos"] - m["fixos_centavos"]) / c) if c else None
        m["consumo_ano_anterior"] = historico.get(_menos_um_ano(m["referencia"]))
        m["completo"] = m["tem_solar"]

    serie = [{"referencia": r, "consumo": historico[r]} for r in sorted(historico)][-24:]

    def soma(campo: str) -> int:
        return sum(m[campo] for m in lista)

    consumo = sum(m["consumo"] or 0 for m in lista)
    anterior = [m["consumo_ano_anterior"] for m in lista if m["consumo_ano_anterior"] is not None]
    comparaveis = [m for m in lista if m["consumo_ano_anterior"] is not None]
    variacao = None
    if comparaveis:
        agora = sum(m["consumo"] or 0 for m in comparaveis)
        antes = sum(m["consumo_ano_anterior"] for m in comparaveis)
        variacao = round((agora / antes - 1) * 100, 1) if antes else None
    resumo = {
        "meses": len(lista),
        "total_centavos": soma("total_centavos"),
        "consumo": consumo,
        "custo_kwh": round(soma("total_centavos") / consumo) if consumo else None,
        "custo_kwh_energia": round((soma("total_centavos") - soma("fixos_centavos")) / consumo) if consumo else None,
        "economia_solar_centavos": soma("economia_centavos"),
        "fixos_centavos": soma("fixos_centavos"),
        "seguro_centavos": soma("seguro_centavos"),
        "bandeira_centavos": soma("bandeira_centavos"),
        "multa_centavos": soma("multa_centavos"),
        "meses_com_atraso": sum(1 for m in lista if m["dias_atraso"] > 0),
        "variacao_consumo_pct": variacao,
        "meses_comparados": len(anterior),
    }
    return {"meses": lista, "historico": serie, "resumo": resumo}
