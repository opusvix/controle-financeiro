"""Contas da casa: ficha de cada fatura (consumo, bandeira, multa) e despesas fixas x variáveis.

Ponte de variação de uma conta de consumo: valor = volume x preço + penalidades.
A ficha guarda o volume (consumo) e as penalidades (multa e juros); o preço sai da divisão.
"""
from __future__ import annotations

import sqlite3

from .transacoes import RegraViolada

TIPOS = ("energia", "energia_solar", "agua", "internet", "telefone", "saude", "outra")
CAMPOS = ("tipo", "referencia", "consumo", "kwh_compensado", "bandeira", "bandeira_centavos",
          "multa_juros_centavos", "vidas", "observacao", "cip_centavos", "terceiros_centavos", "arquivo", "desconto_centavos")
# Campos que fazem sentido em cada tipo (o resto é limpo ao gravar).
POR_TIPO = {
    "energia": {"consumo", "kwh_compensado", "bandeira", "bandeira_centavos", "cip_centavos",
                "terceiros_centavos"},
    "energia_solar": {"kwh_compensado", "consumo", "desconto_centavos"},
    "agua": {"consumo"},
    "saude": {"vidas"},
}
COMUNS = {"tipo", "referencia", "multa_juros_centavos", "observacao", "arquivo"}


def _mes_anterior(data: str) -> str:
    ano, mes = int(data[:4]), int(data[5:7])
    ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return f"{ano}-{mes:02d}"


def obter(con: sqlite3.Connection, transacao_id: int) -> dict:
    """Ficha gravada; senão, sugestão copiada da última ficha da mesma conta (tipo, vidas)."""
    t = con.execute("SELECT * FROM transacao WHERE id = ?", (transacao_id,)).fetchone()
    if t is None:
        raise RegraViolada("Transação não encontrada")
    f = con.execute("SELECT * FROM conta_ficha WHERE transacao_id = ?", (transacao_id,)).fetchone()
    if f:
        return {**dict(f), "gravada": True}
    # A mesma conta em outros meses: mesma recorrência ou, no histórico importado, mesma descrição.
    ultima = con.execute(
        """SELECT f.* FROM conta_ficha f JOIN transacao o ON o.id = f.transacao_id
           WHERE o.id != :id AND ((:rec IS NOT NULL AND o.recorrencia_id = :rec)
                                  OR upper(trim(o.descricao)) = upper(trim(:desc)))
           ORDER BY o.data DESC LIMIT 1""",
        {"id": transacao_id, "rec": t["recorrencia_id"], "desc": t["descricao"]}).fetchone()
    sugestao = {k: None for k in CAMPOS}
    sugestao.update(transacao_id=transacao_id, gravada=False,
                    referencia=_mes_anterior(t["vencimento"] or t["data"]))
    if ultima:
        sugestao.update(tipo=ultima["tipo"], vidas=ultima["vidas"])
    return sugestao


def gravar(con: sqlite3.Connection, transacao_id: int, dados: dict) -> dict:
    t = con.execute("SELECT tipo FROM transacao WHERE id = ?", (transacao_id,)).fetchone()
    if t is None:
        raise RegraViolada("Transação não encontrada")
    if t["tipo"] not in ("despesa", "despesa_cartao"):
        raise RegraViolada("A ficha da conta vale só para despesas")
    validos = COMUNS | POR_TIPO.get(dados["tipo"], set())
    # Campo que não veio (ex.: a tela não edita a iluminação pública lida do PDF) fica como estava.
    atual = con.execute("SELECT * FROM conta_ficha WHERE transacao_id = ?", (transacao_id,)).fetchone()
    valores = {k: (dados[k] if k in dados else (atual[k] if atual else None)) if k in validos else None
               for k in CAMPOS}
    if valores["observacao"] is not None:
        valores["observacao"] = valores["observacao"].strip() or None
    cols = ", ".join(CAMPOS)
    with con:
        con.execute(
            f"INSERT INTO conta_ficha (transacao_id, {cols}) VALUES (?, {', '.join('?' for _ in CAMPOS)}) "
            f"ON CONFLICT (transacao_id) DO UPDATE SET {', '.join(f'{k} = excluded.{k}' for k in CAMPOS)}",
            (transacao_id, *valores.values()))
    return obter(con, transacao_id)
