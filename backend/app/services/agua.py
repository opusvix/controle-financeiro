"""Painel da água (CESAN): parte fixa × variável, preço médio do m³ e consumo × ano anterior."""
import sqlite3


def painel(con: sqlite3.Connection, meses: int = 12) -> dict:
    linhas = con.execute(
        """SELECT f.referencia, f.consumo, f.fixo_centavos, f.multa_juros_centavos, t.valor_centavos,
                  t.data, t.vencimento, t.pago
           FROM conta_ficha f JOIN transacao t ON t.id = f.transacao_id
           WHERE f.tipo = 'agua' AND f.referencia IS NOT NULL ORDER BY f.referencia""").fetchall()[-meses:]
    historico = {r["referencia"]: r["consumo"] for r in con.execute(
        "SELECT referencia, consumo FROM conta_historico WHERE tipo = 'agua'")}
    lista = []
    for r in linhas:
        fixo = r["fixo_centavos"] or 0
        c = r["consumo"]
        ano_ant = f"{int(r['referencia'][:4]) - 1}{r['referencia'][4:]}"
        lista.append({
            "referencia": r["referencia"], "consumo": c, "total_centavos": r["valor_centavos"],
            "fixo_centavos": fixo, "variavel_centavos": r["valor_centavos"] - fixo,
            "multa_centavos": r["multa_juros_centavos"] or 0,
            "custo_m3": round(r["valor_centavos"] / c) if c else None,
            "variavel_m3": round((r["valor_centavos"] - fixo) / c) if c else None,
            "consumo_ano_anterior": historico.get(ano_ant),
            "pago_com_atraso": bool(r["pago"] and r["vencimento"] and r["data"] > r["vencimento"]),
        })
    total = sum(m["total_centavos"] for m in lista)
    consumo = sum(m["consumo"] or 0 for m in lista)
    comp = [m for m in lista if m["consumo_ano_anterior"]]
    antes = sum(m["consumo_ano_anterior"] for m in comp)
    resumo = {
        "meses": len(lista), "total_centavos": total, "consumo": consumo,
        "custo_m3": round(total / consumo) if consumo else None,
        "fixo_centavos": sum(m["fixo_centavos"] for m in lista),
        "multa_centavos": sum(m["multa_centavos"] for m in lista),
        "variacao_consumo_pct": round((sum(m["consumo"] or 0 for m in comp) / antes - 1) * 100, 1) if antes else None,
        "meses_comparados": len(comp),
    }
    return {"meses": lista, "resumo": resumo}
