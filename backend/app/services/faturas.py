"""Em qual fatura cai uma compra no cartão.

Regra (a mesma dos bancos brasileiros): compras feitas NO dia do fechamento
ou depois dele vão para a fatura seguinte. A competência da fatura é o mês
do vencimento ('AAAA-MM').
"""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date


def _dia(ano: int, mes: int, dia: int) -> date:
    """Data com o dia limitado ao fim do mês (dia 31 em fevereiro -> 28/29)."""
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def _mes_seguinte(d: date) -> tuple[int, int]:
    return (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)


def datas_da_fatura(compra: date, dia_fechamento: int, dia_vencimento: int) -> tuple[date, date]:
    """Devolve (data_fechamento, data_vencimento) da fatura onde a compra cai."""
    fechamento = _dia(compra.year, compra.month, dia_fechamento)
    if compra >= fechamento:
        fechamento = _dia(*_mes_seguinte(compra), dia_fechamento)
    vencimento = _dia(fechamento.year, fechamento.month, dia_vencimento)
    if vencimento <= fechamento:
        vencimento = _dia(*_mes_seguinte(fechamento), dia_vencimento)
    return fechamento, vencimento


def competencia(compra: date, dia_fechamento: int, dia_vencimento: int) -> str:
    _, vencimento = datas_da_fatura(compra, dia_fechamento, dia_vencimento)
    return f"{vencimento:%Y-%m}"


def somar_meses(d: date, meses: int) -> date:
    ano, mes = d.year + (d.month - 1 + meses) // 12, (d.month - 1 + meses) % 12 + 1
    return _dia(ano, mes, d.day)


def obter_ou_criar_fatura(con: sqlite3.Connection, cartao_id: int, compra: date) -> int:
    c = con.execute(
        "SELECT dia_fechamento, dia_vencimento FROM cartao WHERE id = ?", (cartao_id,)
    ).fetchone()
    if c is None:
        raise ValueError(f"Cartão {cartao_id} não existe")
    fechamento, vencimento = datas_da_fatura(compra, c["dia_fechamento"], c["dia_vencimento"])
    comp = f"{vencimento:%Y-%m}"
    linha = con.execute(
        "SELECT id FROM fatura WHERE cartao_id = ? AND competencia = ?", (cartao_id, comp)
    ).fetchone()
    if linha:
        return linha["id"]
    cur = con.execute(
        "INSERT INTO fatura (cartao_id, competencia, data_fechamento, data_vencimento) "
        "VALUES (?, ?, ?, ?)",
        (cartao_id, comp, fechamento.isoformat(), vencimento.isoformat()),
    )
    return cur.lastrowid
