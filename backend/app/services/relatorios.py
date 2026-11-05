"""Relatórios (Fase 4): números ao longo de um período, não de um mês só.

O Dashboard responde "como estou este mês". O relatório responde "como foi ao
longo do tempo": evolução de receitas × despesas, para onde o dinheiro foi por
categoria mês a mês, e quanto cada projeto (tag) custou no período.

As definições são as MESMAS do Dashboard (docs/METRICAS.md): despesa por regime
de competência (data da compra), itens de cupom na categoria de cada item pelo
valor líquido, e crédito no cartão (estorno/cashback) abatendo a despesa.
"""
from __future__ import annotations

import sqlite3
from datetime import date

# Despesa por mês e categoria, com a mesma base do Dashboard (sem transação ignorada).
_DESPESA_MES_CAT = """
    SELECT strftime('%Y-%m', t.data) AS mes, t.categoria_id AS cat,
           CASE WHEN t.tipo = 'credito_cartao' THEN -t.valor_centavos ELSE t.valor_centavos END AS valor
    FROM transacao t
    WHERE t.tipo IN ('despesa', 'despesa_cartao', 'credito_cartao') AND t.ignorar = 0
      AND t.data BETWEEN :ini AND :fim
      AND NOT EXISTS (SELECT 1 FROM item i WHERE i.transacao_id = t.id)
    UNION ALL
    SELECT strftime('%Y-%m', t.data), COALESCE(i.categoria_id, t.categoria_id),
           i.valor_total_centavos - i.desconto_centavos
    FROM item i JOIN transacao t ON t.id = i.transacao_id
    WHERE t.tipo IN ('despesa', 'despesa_cartao') AND t.ignorar = 0
      AND t.data BETWEEN :ini AND :fim
"""


def _meses_entre(ini: str, fim: str) -> list[str]:
    """Lista de competências 'AAAA-MM' de ini a fim, inclusive, mesmo as sem lançamento."""
    a, m = int(ini[:4]), int(ini[5:7])
    fa, fm = int(fim[:4]), int(fim[5:7])
    out = []
    while (a, m) <= (fa, fm):
        out.append(f"{a:04d}-{m:02d}")
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return out


def periodo(con: sqlite3.Connection, ini: str, fim: str) -> dict:
    p = {"ini": ini, "fim": fim}
    meses = _meses_entre(ini, fim)

    receita_mes = dict(con.execute(
        """SELECT strftime('%Y-%m', data) AS mes, SUM(valor_centavos)
           FROM transacao WHERE tipo = 'receita' AND ignorar = 0
             AND data BETWEEN :ini AND :fim GROUP BY mes""", p).fetchall())
    despesa_mes = dict(con.execute(
        f"WITH base AS ({_DESPESA_MES_CAT}) SELECT mes, SUM(valor) FROM base GROUP BY mes", p).fetchall())

    serie = [{"competencia": mes,
              "receitas": receita_mes.get(mes, 0) or 0,
              "despesas": despesa_mes.get(mes, 0) or 0,
              "resultado": (receita_mes.get(mes, 0) or 0) - (despesa_mes.get(mes, 0) or 0)}
             for mes in meses]

    # Despesas por categoria-mãe no período, com a fatia de cada mês (para barras empilhadas).
    linhas = con.execute(f"""
        WITH base AS ({_DESPESA_MES_CAT})
        SELECT base.mes,
               COALESCE(mae.id, c.id, 0) AS categoria_id,
               COALESCE(mae.nome, c.nome, 'Sem categoria') AS categoria,
               COALESCE(mae.cor, c.cor, '#6b7280') AS cor,
               SUM(base.valor) AS total
        FROM base
        LEFT JOIN categoria c ON c.id = base.cat
        LEFT JOIN categoria mae ON mae.id = c.pai_id
        GROUP BY 1, 2, 3, 4""", p).fetchall()
    cats: dict[int, dict] = {}
    for r in linhas:
        c = cats.setdefault(r["categoria_id"], {
            "categoria_id": r["categoria_id"], "categoria": r["categoria"], "cor": r["cor"],
            "total": 0, "por_mes": {}})
        c["total"] += r["total"]
        c["por_mes"][r["mes"]] = c["por_mes"].get(r["mes"], 0) + r["total"]
    total_despesas = sum(c["total"] for c in cats.values())
    por_categoria = sorted(cats.values(), key=lambda c: c["total"], reverse=True)
    for c in por_categoria:
        c["pct"] = round(c["total"] / total_despesas * 100, 1) if total_despesas else 0.0
        c["serie"] = [c["por_mes"].get(mes, 0) for mes in meses]
        del c["por_mes"]

    # Projetos (tags) são por transação, então somam o valor da transação, não dos itens.
    por_tag = [dict(r) for r in con.execute("""
        SELECT tg.nome AS tag, tg.cor,
               SUM(CASE WHEN t.tipo = 'credito_cartao' THEN -t.valor_centavos
                        ELSE t.valor_centavos END) AS total,
               COUNT(DISTINCT t.id) AS lancamentos
        FROM transacao t
        JOIN transacao_tag tt ON tt.transacao_id = t.id
        JOIN tag tg ON tg.id = tt.tag_id
        WHERE t.tipo IN ('despesa', 'despesa_cartao', 'credito_cartao') AND t.ignorar = 0
          AND t.data BETWEEN :ini AND :fim
        GROUP BY tg.id HAVING total <> 0 ORDER BY total DESC""", p).fetchall()]

    receitas = sum(s["receitas"] for s in serie)
    despesas = sum(s["despesas"] for s in serie)
    n = len(meses)
    resumo = {
        "meses": n, "receitas": receitas, "despesas": despesas, "resultado": receitas - despesas,
        "media_receitas_mes": round(receitas / n) if n else 0,
        "media_despesas_mes": round(despesas / n) if n else 0,
        "taxa_poupanca_pct": round((receitas - despesas) / receitas * 100, 1) if receitas else None,
        "mes_maior_despesa": max(serie, key=lambda s: s["despesas"])["competencia"] if serie else None,
    }
    return {"ini": ini, "fim": fim, "meses": serie, "por_categoria": por_categoria,
            "por_tag": por_tag, "resumo": resumo}


def atalho(con: sqlite3.Connection, meses: int) -> dict:
    """Período dos últimos N meses, terminando no mês corrente."""
    hoje = date.today()
    fim = f"{hoje:%Y-%m}-{_ultimo_dia(hoje.year, hoje.month):02d}"
    a, m = hoje.year, hoje.month - (meses - 1)
    while m <= 0:
        a, m = a - 1, m + 12
    return periodo(con, f"{a:04d}-{m:02d}-01", fim)


def _ultimo_dia(ano: int, mes: int) -> int:
    import calendar
    return calendar.monthrange(ano, mes)[1]
