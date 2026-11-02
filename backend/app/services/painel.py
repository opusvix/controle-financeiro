"""Saldos e números do Dashboard. As fórmulas estão em docs/METRICAS.md.

Cada número tem UMA definição, usada em todas as telas (no Mobills o card
de Despesas e o gráfico de Despesas mostravam valores diferentes).
"""
from __future__ import annotations

import calendar
import sqlite3

from .transacoes import EFEITO_SQL


def _limites_mes(competencia: str) -> tuple[str, str]:
    ano, mes = map(int, competencia.split("-"))
    return f"{competencia}-01", f"{competencia}-{calendar.monthrange(ano, mes)[1]:02d}"


def saldos_contas(con: sqlite3.Connection, ate: str | None = None) -> list[dict]:
    """Saldo atual (só pagas) e previsto (pagas + pendentes) por conta ativa."""
    filtro_data = "AND t.data <= :ate" if ate else ""
    sql = f"""
        SELECT c.id, c.nome, c.tipo, c.cor, c.compoe_saldo_disponivel,
               c.saldo_inicial_centavos
                 + COALESCE(SUM(CASE WHEN t.pago = 1 THEN {EFEITO_SQL} END), 0) AS saldo_atual,
               c.saldo_inicial_centavos
                 + COALESCE(SUM({EFEITO_SQL}), 0) AS saldo_previsto
        FROM conta c
        LEFT JOIN transacao t
               ON t.conta_id = c.id AND t.data >= c.data_saldo_inicial {filtro_data}
        WHERE c.ativa = 1
        GROUP BY c.id
        ORDER BY c.nome
    """
    return [dict(r) for r in con.execute(sql, {"ate": ate})]


def despesas_por_categoria(con: sqlite3.Connection, competencia: str) -> list[dict]:
    """Despesas do mês por categoria-mãe. Compras com itens usam a categoria de cada item."""
    ini, fim = _limites_mes(competencia)
    sql = """
        WITH base AS (
            -- transações sem itens: a categoria da transação
            -- crédito no cartão (estorno, cashback) abate a despesa da sua categoria
            SELECT t.categoria_id AS cat,
                   CASE WHEN t.tipo = 'credito_cartao' THEN -t.valor_centavos
                        ELSE t.valor_centavos END AS valor
            FROM transacao t
            WHERE t.tipo IN ('despesa', 'despesa_cartao', 'credito_cartao') AND t.ignorar = 0
              AND t.data BETWEEN :ini AND :fim
              AND NOT EXISTS (SELECT 1 FROM item i WHERE i.transacao_id = t.id)
            UNION ALL
            -- transações com itens: valor líquido de cada item na sua categoria
            SELECT COALESCE(i.categoria_id, t.categoria_id),
                   i.valor_total_centavos - i.desconto_centavos
            FROM item i JOIN transacao t ON t.id = i.transacao_id
            WHERE t.tipo IN ('despesa', 'despesa_cartao') AND t.ignorar = 0
              AND t.data BETWEEN :ini AND :fim
        )
        SELECT COALESCE(mae.id, c.id) AS categoria_id,
               COALESCE(mae.nome, c.nome, 'Sem categoria') AS categoria,
               COALESCE(mae.cor, c.cor, '#6b7280') AS cor,
               SUM(base.valor) AS total
        FROM base
        LEFT JOIN categoria c ON c.id = base.cat
        LEFT JOIN categoria mae ON mae.id = c.pai_id
        GROUP BY 1, 2, 3
        ORDER BY total DESC
    """
    return [dict(r) for r in con.execute(sql, {"ini": ini, "fim": fim})]


def receitas_por_categoria(con: sqlite3.Connection, competencia: str) -> list[dict]:
    ini, fim = _limites_mes(competencia)
    sql = """
        SELECT COALESCE(c.id, 0) AS categoria_id, COALESCE(c.nome, 'Sem categoria') AS categoria,
               COALESCE(c.cor, '#6b7280') AS cor, SUM(t.valor_centavos) AS total
        FROM transacao t LEFT JOIN categoria c ON c.id = t.categoria_id
        WHERE t.tipo = 'receita' AND t.ignorar = 0 AND t.data BETWEEN :ini AND :fim
        GROUP BY 1, 2, 3 ORDER BY total DESC
    """
    return [dict(r) for r in con.execute(sql, {"ini": ini, "fim": fim})]


def cartoes(con: sqlite3.Connection, competencia: str) -> list[dict]:
    """Fatura do mês e limite disponível por cartão ativo."""
    sql = """
        SELECT ca.id, ca.nome, ca.bandeira, ca.final, ca.cor, ca.limite_centavos,
               f.data_vencimento,
               COALESCE((SELECT SUM(CASE WHEN tipo = 'credito_cartao' THEN -valor_centavos
                                         ELSE valor_centavos END) FROM transacao
                         WHERE tipo IN ('despesa_cartao', 'credito_cartao') AND fatura_id = f.id), 0)
                 AS fatura_total,
               COALESCE((SELECT SUM(valor_centavos) FROM transacao
                         WHERE tipo = 'pagamento_fatura' AND fatura_id = f.id), 0) AS fatura_paga,
               COALESCE((SELECT SUM(CASE WHEN tipo = 'credito_cartao' THEN -valor_centavos
                                         ELSE valor_centavos END) FROM transacao
                         WHERE tipo IN ('despesa_cartao', 'credito_cartao') AND cartao_id = ca.id), 0)
             - COALESCE((SELECT SUM(valor_centavos) FROM transacao
                         WHERE tipo = 'pagamento_fatura' AND cartao_id = ca.id), 0) AS em_aberto
        FROM cartao ca
        LEFT JOIN fatura f ON f.cartao_id = ca.id AND f.competencia = :comp
        WHERE ca.ativo = 1
        ORDER BY ca.nome
    """
    linhas = []
    for r in con.execute(sql, {"comp": competencia}):
        d = dict(r)
        d["limite_disponivel"] = d["limite_centavos"] - d["em_aberto"]
        d["fatura_situacao"] = (
            "sem fatura" if d["fatura_total"] == 0
            else "paga" if d["fatura_paga"] >= d["fatura_total"]
            else "aberta"
        )
        linhas.append(d)
    return linhas


def resumo(con: sqlite3.Connection, competencia: str) -> dict:
    ini, fim = _limites_mes(competencia)
    # Previsto = até o fim do mês escolhido (contas a pagar de meses seguintes não entram).
    contas = saldos_contas(con, fim)
    soma = con.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor_centavos END), 0) AS receitas,
          COALESCE(SUM(CASE WHEN tipo IN ('despesa', 'despesa_cartao') THEN valor_centavos
                            WHEN tipo = 'credito_cartao' THEN -valor_centavos END), 0)
            AS despesas,
          COALESCE(SUM(CASE WHEN tipo = 'despesa' AND pago = 0 THEN valor_centavos END), 0)
            AS despesas_pendentes,
          COALESCE(SUM(CASE WHEN tipo = 'receita' AND pago = 0 THEN valor_centavos END), 0)
            AS receitas_pendentes
        FROM transacao WHERE ignorar = 0 AND data BETWEEN ? AND ?
        """,
        (ini, fim),
    ).fetchone()
    lista_cartoes = cartoes(con, competencia)
    return {
        "competencia": competencia,
        "saldo_disponivel": sum(c["saldo_atual"] for c in contas if c["compoe_saldo_disponivel"]),
        "patrimonio": sum(c["saldo_atual"] for c in contas),
        "receitas": soma["receitas"],
        "despesas": soma["despesas"],
        "cartoes_fatura_mes": sum(c["fatura_total"] for c in lista_cartoes),
        "pendencias": {
            "despesas": soma["despesas_pendentes"],
            "receitas": soma["receitas_pendentes"],
        },
        "contas": contas,
        "cartoes": lista_cartoes,
        "receitas_por_categoria": receitas_por_categoria(con, competencia),
        "despesas_por_categoria": despesas_por_categoria(con, competencia),
    }
