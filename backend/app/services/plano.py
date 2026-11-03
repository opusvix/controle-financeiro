"""Reajuste do plano de saúde: o que subiu, por quê (anual × faixa etária) e contra quais índices.

Plano INDIVIDUAL/FAMILIAR: o reajuste anual tem teto da ANS. Mudança de faixa etária é
outra regra (tabela do contrato) e não entra na comparação com a inflação.
"""
import sqlite3
from collections import defaultdict

from . import indices

TOLERANCIA_PP = 0.15   # itens que sobem o "mesmo %" (arredondamento de centavos)


def _pct(novo: int, velho: int) -> float:
    return round((novo / velho - 1) * 100, 2)


def painel(con: sqlite3.Connection) -> dict:
    meses = con.execute(
        """SELECT f.referencia, t.id, t.valor_centavos, t.descricao, f.vidas
           FROM conta_ficha f JOIN transacao t ON t.id = f.transacao_id
           WHERE f.tipo = 'saude' AND f.referencia IS NOT NULL ORDER BY f.referencia""").fetchall()
    itens = defaultdict(dict)
    for r in con.execute(
            """SELECT f.referencia, p.beneficiario, p.item, p.valor_centavos FROM plano_item p
               JOIN conta_ficha f ON f.transacao_id = p.transacao_id WHERE f.tipo = 'saude'"""):
        itens[r["referencia"]][(r["beneficiario"], r["item"])] = r["valor_centavos"]

    serie = [{"referencia": m["referencia"], "total_centavos": m["valor_centavos"], "vidas": m["vidas"],
              "itens": [{"beneficiario": b.split()[0].capitalize(), "item": i.capitalize(), "valor_centavos": v}
                        for (b, i), v in sorted(itens.get(m["referencia"], {}).items())]}
             for m in meses]

    eventos = []
    for antes, depois in zip(meses, meses[1:]):
        ra, rd = antes["referencia"], depois["referencia"]
        if depois["valor_centavos"] == antes["valor_centavos"]:
            continue
        ia, idp = itens.get(ra, {}), itens.get(rd, {})
        mudaram = {k: _pct(idp[k], ia[k]) for k in ia.keys() & idp.keys() if idp[k] != ia[k] and ia[k]}
        todos = ia.keys() & idp.keys()
        pcts = list(mudaram.values())
        anual = bool(todos) and len(mudaram) == len(todos) and max(pcts) - min(pcts) <= TOLERANCIA_PP
        if not todos:   # sem os itens do PDF: só o total
            anual = None
        ev = {"referencia": rd, "antes_centavos": antes["valor_centavos"], "depois_centavos": depois["valor_centavos"],
              "percentual": _pct(depois["valor_centavos"], antes["valor_centavos"]),
              "diferenca_mes_centavos": depois["valor_centavos"] - antes["valor_centavos"],
              "tipo": "anual" if anual else "faixa_etaria" if anual is False else "desconhecido",
              "quem": sorted({b.split()[0].capitalize() for (b, _i) in mudaram}) if anual is False else [],
              "detalhe": [{"beneficiario": b.split()[0].capitalize(), "item": i.capitalize(),
                           "antes_centavos": ia[(b, i)], "depois_centavos": idp[(b, i)], "percentual": pc}
                          for (b, i), pc in sorted(mudaram.items())]}
        if ev["tipo"] != "faixa_etaria":
            ate = indices._somar_mes(rd, -1)          # 12 meses até o mês anterior ao reajuste
            teto = indices.teto_ans(con, rd)
            ev["teto_ans"] = teto
            ev["comparacao"] = [{"indice": nome, "percentual": indices.acumulado_12m(con, nome, ate),
                                 "periodo": f"{indices._somar_mes(ate, -11)} a {ate}"} for nome in indices.SERIES]
            if teto:
                ev["acima_do_teto"] = ev["percentual"] > teto["percentual"] + 0.01
        eventos.append(ev)
    return {"meses": serie, "eventos": eventos, "indices_ate": indices.situacao(con)}
