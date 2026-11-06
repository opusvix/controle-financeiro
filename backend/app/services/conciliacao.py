"""Conciliação bancária: lê um extrato OFX e cruza com os lançamentos da conta.

Classifica cada linha do extrato e cada lançamento em quatro baldes:
- casado: bate data (± tolerância) e valor exato;
- divergência: valor próximo (provável mesmo lançamento, revisar);
- só no banco: veio no extrato mas não está lançado;
- só no app: está lançado mas não apareceu no extrato.

O efeito de cada lançamento no saldo da conta usa a MESMA conta do resto do app
(transacoes.EFEITO_SQL), então o sinal bate com o do extrato (negativo = saiu).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date

from . import transacoes as tx
from .transacoes import EFEITO_SQL

# Tipos que mexem no saldo de uma conta (e por isso aparecem no extrato bancário).
# Cartão (despesa_cartao/credito_cartao) não entra: só o pagamento da fatura sai da conta.
_TIPOS_CONTA = ("receita", "despesa", "pagamento_fatura", "transferencia", "ajuste")


class OFXInvalido(ValueError):
    """Arquivo que não dá para ler como extrato OFX (vira HTTP 422)."""


def _tag(bloco: str, nome: str) -> str:
    m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
    return m.group(1).strip() if m else ""


def ler_ofx(conteudo: bytes) -> list[dict]:
    """Extrai as transações (STMTTRN) do OFX. Valor em centavos, com sinal."""
    texto = conteudo.decode("latin-1", errors="replace")
    blocos = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", texto, re.S | re.I)
    if not blocos:
        raise OFXInvalido("Não encontrei lançamentos (STMTTRN) no arquivo. "
                          "Confira se é um extrato exportado em OFX.")
    linhas: list[dict] = []
    for i, b in enumerate(blocos):
        dt = _tag(b, "DTPOSTED")[:8]
        valor = _tag(b, "TRNAMT").replace(",", ".")
        if len(dt) != 8 or not valor:
            continue
        try:
            d = date(int(dt[:4]), int(dt[4:6]), int(dt[6:8]))
            centavos = round(float(valor) * 100)
        except ValueError:
            continue
        descricao = _tag(b, "MEMO") or _tag(b, "NAME") or "(sem descrição)"
        linhas.append({"fitid": _tag(b, "FITID") or f"linha{i}", "data": d.isoformat(),
                       "valor_centavos": centavos, "descricao": descricao})
    if not linhas:
        raise OFXInvalido("O arquivo parece OFX, mas nenhuma linha tinha data e valor válidos.")
    return linhas


def _dias(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def conciliar(con: sqlite3.Connection, conta_id: int, linhas: list[dict],
              tolerancia_dias: int = 3) -> dict:
    """Cruza as linhas do extrato com os lançamentos da conta no período do extrato."""
    if not linhas:
        raise OFXInvalido("Extrato sem linhas para conciliar.")
    datas = [l["data"] for l in linhas]
    ini, fim = min(datas), max(datas)
    marcas = ", ".join("?" for _ in _TIPOS_CONTA)
    rows = con.execute(f"""
        SELECT t.id, t.descricao, t.data, t.conferido, t.tipo, ({EFEITO_SQL}) AS efeito
        FROM transacao t
        WHERE t.conta_id = ? AND t.tipo IN ({marcas})
          AND date(t.data) BETWEEN date(?, ?) AND date(?, ?)
        ORDER BY t.data, t.id
    """, (conta_id, *_TIPOS_CONTA, ini, f"-{tolerancia_dias} days",
          fim, f"+{tolerancia_dias} days")).fetchall()
    app = [dict(r) for r in rows]
    usados: set[int] = set()

    def achar(valor: int, data: str, exato: bool) -> dict | None:
        melhor, melhor_dist = None, None
        for a in app:
            if a["id"] in usados or _dias(a["data"], data) > tolerancia_dias:
                continue
            if exato:
                if a["efeito"] != valor:
                    continue
            else:
                if (a["efeito"] > 0) != (valor > 0):   # sinais diferentes: não é o mesmo
                    continue
                margem = max(200, round(abs(valor) * 0.05))   # até 5% ou R$ 2,00
                if abs(a["efeito"] - valor) > margem:
                    continue
            dist = _dias(a["data"], data)
            if melhor is None or dist < melhor_dist:
                melhor, melhor_dist = a, dist
        return melhor

    for ln in linhas:   # 1ª passada: casamento exato
        a = achar(ln["valor_centavos"], ln["data"], exato=True)
        if a:
            usados.add(a["id"])
            ln["_app"] = a
    for ln in linhas:   # 2ª passada: divergências no que sobrou
        if "_app" not in ln:
            a = achar(ln["valor_centavos"], ln["data"], exato=False)
            if a:
                usados.add(a["id"])
                ln["_div"] = a

    casados, divergencias, so_banco = [], [], []
    for ln in linhas:
        if "_app" in ln:
            casados.append({"banco": _ofx_pub(ln), "app": _app_pub(ln["_app"])})
        elif "_div" in ln:
            divergencias.append({"banco": _ofx_pub(ln), "app": _app_pub(ln["_div"]),
                                 "diferenca_centavos": ln["valor_centavos"] - ln["_div"]["efeito"]})
        else:
            so_banco.append(_ofx_pub(ln))
    so_app = [_app_pub(a) for a in app if a["id"] not in usados]

    return {"conta_id": conta_id, "ini": ini, "fim": fim, "tolerancia_dias": tolerancia_dias,
            "casados": casados, "divergencias": divergencias,
            "so_banco": so_banco, "so_app": so_app,
            "resumo": {"linhas_extrato": len(linhas), "casados": len(casados),
                       "divergencias": len(divergencias), "so_banco": len(so_banco),
                       "so_app": len(so_app)}}


def aplicar(con: sqlite3.Connection, conta_id: int, conferir_ids: list[int],
            criar: list[dict]) -> dict:
    """Marca como conferidos os lançamentos casados e cria os que faltavam (do extrato)."""
    conferidos = 0
    for id_ in conferir_ids:
        tx.editar(con, id_, {"conferido": 1})
        conferidos += 1
    criados = 0
    for linha in criar:
        valor = int(linha["valor_centavos"])
        quando = linha["data"]
        if not isinstance(quando, date):
            quando = date.fromisoformat(quando)
        nova = tx.NovaTransacao(
            tipo="receita" if valor > 0 else "despesa",
            descricao=(linha.get("descricao") or "").strip() or "Lançamento do extrato",
            valor_centavos=abs(valor),
            data=quando,
            conta_id=conta_id,
            categoria_id=linha.get("categoria_id"),
        )
        ids = tx.criar(con, nova)
        for id_ in ids:
            tx.editar(con, id_, {"conferido": 1})
        criados += 1
    return {"conferidos": conferidos, "criados": criados}


def _ofx_pub(ln: dict) -> dict:
    return {"fitid": ln["fitid"], "data": ln["data"],
            "valor_centavos": ln["valor_centavos"], "descricao": ln["descricao"]}


def _app_pub(a: dict) -> dict:
    return {"id": a["id"], "data": a["data"], "descricao": a["descricao"],
            "valor_centavos": a["efeito"], "tipo": a["tipo"], "conferido": a["conferido"]}
