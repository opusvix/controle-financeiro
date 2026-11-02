"""Fatura de um cartão: lançamentos, pagamentos e conferência com o banco."""
from __future__ import annotations

import sqlite3
from datetime import date

from . import faturas
from .transacoes import RegraViolada


def _cartao(con: sqlite3.Connection, cartao_id: int):
    c = con.execute("SELECT * FROM cartao WHERE id = ?", (cartao_id,)).fetchone()
    if c is None:
        raise RegraViolada("Cartão não encontrado")
    return c


def _datas(cartao, competencia: str) -> tuple[str, str]:
    """(fechamento, vencimento) da fatura que vence no mês 'competencia'."""
    ano, mes = map(int, competencia.split("-"))
    venc = faturas._dia(ano, mes, cartao["dia_vencimento"])
    fech = faturas._dia(ano, mes, cartao["dia_fechamento"])
    if fech >= venc:   # fecha no mês anterior ao vencimento
        fech = faturas._dia(*((ano - 1, 12) if mes == 1 else (ano, mes - 1)), cartao["dia_fechamento"])
    return fech.isoformat(), venc.isoformat()


def detalhe(con: sqlite3.Connection, cartao_id: int, competencia: str) -> dict:
    """Fatura com vencimento no mês 'competencia' (AAAA-MM), mesmo que ainda vazia."""
    c = _cartao(con, cartao_id)
    f = con.execute("SELECT * FROM fatura WHERE cartao_id = ? AND competencia = ?",
                    (cartao_id, competencia)).fetchone()
    if f:
        fechamento, vencimento = f["data_fechamento"], f["data_vencimento"]
    else:
        fechamento, vencimento = _datas(c, competencia)

    lancamentos, pagamentos = [], []
    if f:
        sql = """
            SELECT t.id, t.tipo, t.descricao, t.valor_centavos, t.data, t.categoria_id,
                   c.nome AS categoria, t.parcela, t.total_parcelas, t.conferido, t.observacao,
                   t.conta_id, co.nome AS conta,
                   (SELECT COUNT(*) FROM item i WHERE i.transacao_id = t.id) AS itens
            FROM transacao t
            LEFT JOIN categoria c ON c.id = t.categoria_id
            LEFT JOIN conta co ON co.id = t.conta_id
            WHERE t.fatura_id = ? ORDER BY t.data, t.id
        """
        for r in con.execute(sql, (f["id"],)):
            (lancamentos if r["tipo"] == "despesa_cartao" else pagamentos).append(dict(r))

    total = sum(t["valor_centavos"] for t in lancamentos)
    pago = sum(t["valor_centavos"] for t in pagamentos)
    conferido = sum(t["valor_centavos"] for t in lancamentos if t["conferido"])
    hoje = date.today().isoformat()
    situacao = ("sem lançamentos" if total == 0 else "paga" if pago >= total
                else "aberta" if hoje < fechamento else "fechada")
    banco = f["valor_banco_centavos"] if f else None
    return {
        "cartao": {"id": c["id"], "nome": c["nome"], "final": c["final"], "bandeira": c["bandeira"],
                   "conta_pagamento_id": c["conta_pagamento_id"]},
        "competencia": competencia, "fatura_id": f["id"] if f else None,
        "data_fechamento": fechamento, "data_vencimento": vencimento,
        "total": total, "pago": pago, "a_pagar": max(total - pago, 0),
        "conferido": conferido, "situacao": situacao,
        "valor_banco": banco, "diferenca_banco": None if banco is None else total - banco,
        "lancamentos": lancamentos, "pagamentos": pagamentos,
    }


def informar_valor_banco(con: sqlite3.Connection, cartao_id: int, competencia: str,
                         valor: int | None) -> None:
    f = con.execute("SELECT id FROM fatura WHERE cartao_id = ? AND competencia = ?",
                    (cartao_id, competencia)).fetchone()
    if f is None:
        raise RegraViolada("Esta fatura ainda não tem lançamentos")
    with con:
        con.execute("UPDATE fatura SET valor_banco_centavos = ? WHERE id = ?", (valor, f["id"]))


def fatura_por_competencia(con: sqlite3.Connection, cartao_id: int, competencia: str) -> int:
    """Obtém (ou cria) a fatura de uma competência; usada para mover um lançamento."""
    f = con.execute("SELECT id FROM fatura WHERE cartao_id = ? AND competencia = ?",
                    (cartao_id, competencia)).fetchone()
    if f:
        return f["id"]
    fech, venc = _datas(_cartao(con, cartao_id), competencia)
    return con.execute("INSERT INTO fatura (cartao_id, competencia, data_fechamento, data_vencimento) "
                       "VALUES (?, ?, ?, ?)", (cartao_id, competencia, fech, venc)).lastrowid
