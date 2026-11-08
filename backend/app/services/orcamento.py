"""Orçamento × realizado: teto de gasto por categoria em cada competência (mês),
comparado com o quanto já foi gasto. A tabela `orcamento` (categoria_id, competencia,
valor_centavos) já existe desde a migração 001.

O "realizado" reusa EXATAMENTE a mesma conta do Dashboard (painel.despesas_por_categoria),
então orçado e realizado falam a mesma língua: itens de cupom entram na categoria de cada item,
estornos abatem a despesa e lançamentos marcados "ignorar" ficam de fora. O teto é guardado por
categoria-MÃE, porque o painel soma as despesas na categoria-mãe.
"""
from __future__ import annotations

import sqlite3
from datetime import date


def _mes_anterior(competencia: str) -> str:
    ano, mes = map(int, competencia.split("-"))
    return f"{ano - 1}-12" if mes == 1 else f"{ano}-{mes - 1:02d}"


def ver(con: sqlite3.Connection, competencia: str) -> dict:
    """Linhas de orçado × realizado da competência, mais o total.

    Lista toda categoria-mãe de despesa que tenha teto no mês OU gasto no mês.
    """
    from . import painel
    realizado = {r["categoria_id"]: r for r in painel.despesas_por_categoria(con, competencia)}
    orcados = {r["categoria_id"]: r["valor_centavos"] for r in con.execute(
        "SELECT categoria_id, valor_centavos FROM orcamento WHERE competencia = ?", (competencia,))}
    maes = {r["id"]: dict(r) for r in con.execute(
        "SELECT id, nome, cor FROM categoria WHERE tipo = 'despesa' AND pai_id IS NULL")}

    ids = set(orcados) | {cid for cid in realizado if cid in maes}
    linhas = []
    for cid in ids:
        info = maes.get(cid) or {}
        orcado = orcados.get(cid, 0)
        gasto = (realizado.get(cid) or {}).get("total", 0) or 0
        linhas.append({
            "categoria_id": cid,
            "categoria": info.get("nome") or (realizado.get(cid) or {}).get("categoria", "Sem categoria"),
            "cor": info.get("cor") or (realizado.get(cid) or {}).get("cor", "#6b7280"),
            "orcado_centavos": orcado,
            "realizado_centavos": gasto,
            "saldo_centavos": orcado - gasto,
            "pct": round(gasto / orcado * 100) if orcado else None,
        })
    # Com teto primeiro (quem tem planejamento), depois por maior gasto.
    linhas.sort(key=lambda l: (l["orcado_centavos"] == 0, -l["realizado_centavos"]))

    orcado_tot = sum(l["orcado_centavos"] for l in linhas)
    realizado_tot = sum(l["realizado_centavos"] for l in linhas if l["orcado_centavos"] > 0)
    total = {"orcado_centavos": orcado_tot, "realizado_centavos": realizado_tot,
             "saldo_centavos": orcado_tot - realizado_tot,
             "pct": round(realizado_tot / orcado_tot * 100) if orcado_tot else None}
    return {"competencia": competencia, "linhas": linhas, "total": total}


def definir(con: sqlite3.Connection, categoria_id: int, competencia: str, valor_centavos: int) -> None:
    """Grava (ou atualiza) o teto da categoria na competência. Valor 0 ou negativo remove.

    Quem chama envolve em `with con:` para o commit, como o resto do app.
    """
    if valor_centavos and valor_centavos > 0:
        con.execute(
            "INSERT INTO orcamento (categoria_id, competencia, valor_centavos) VALUES (?, ?, ?) "
            "ON CONFLICT(categoria_id, competencia) DO UPDATE SET valor_centavos = excluded.valor_centavos",
            (categoria_id, competencia, valor_centavos))
    else:
        con.execute("DELETE FROM orcamento WHERE categoria_id = ? AND competencia = ?",
                    (categoria_id, competencia))


def copiar_do_mes_anterior(con: sqlite3.Connection, competencia: str) -> int:
    """Traz para esta competência os tetos do mês anterior que ainda não existem aqui.
    Facilita o 'defina uma vez e repita'. Devolve quantos tetos foram copiados."""
    anterior = _mes_anterior(competencia)
    cur = con.execute(
        "INSERT INTO orcamento (categoria_id, competencia, valor_centavos) "
        "SELECT categoria_id, ?, valor_centavos FROM orcamento o WHERE o.competencia = ? "
        "AND NOT EXISTS (SELECT 1 FROM orcamento n WHERE n.categoria_id = o.categoria_id "
        "               AND n.competencia = ?)",
        (competencia, anterior, competencia))
    return cur.rowcount
