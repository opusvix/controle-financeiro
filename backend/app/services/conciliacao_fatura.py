"""Conciliação da FATURA do cartão: cruza o arquivo da fatura com o que foi lançado.

Diferente da conciliação bancária, aqui o par NÃO é por data: na fatura a data é
a da compra original (uma parcela 5/12 traz a data de meses atrás), mas no app a
parcela é reconhecida na competência da fatura. Então o escopo é a competência
(cartão + mês) e a âncora do casamento é o VALOR; a data e a parcela só servem de
desempate quando dois valores são iguais.

Valores com sinal do ponto de vista da fatura: compra (despesa_cartao) positivo,
crédito/estorno (credito_cartao) negativo.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from . import fatura_cartao
from . import transacoes as tx


def _dias(a: str, b: str) -> int:
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except ValueError:
        return 10**6


def _sinal_app(t: dict) -> int:
    return -t["valor_centavos"] if t["tipo"] == "credito_cartao" else t["valor_centavos"]


def _app_pub(t: dict) -> dict:
    return {"id": t["id"], "data": t["data"], "descricao": t["descricao"],
            "valor_centavos": _sinal_app(t), "tipo": t["tipo"],
            "parcela": t["parcela"], "total_parcelas": t["total_parcelas"],
            "conferido": t["conferido"]}


def _lin_pub(chave: str, l: dict) -> dict:
    return {"chave": chave, "data": l["data"], "descricao": l["descricao"],
            "valor_centavos": l["valor_centavos"], "parcela": l["parcela"],
            "total_parcelas": l["total_parcelas"], "final": l.get("final") or ""}


def conciliar(con: sqlite3.Connection, cartao_id: int, competencia: str, lido: dict) -> dict:
    det = fatura_cartao.detalhe(con, cartao_id, competencia)
    app = [t for t in det["lancamentos"] if t["tipo"] in ("despesa_cartao", "credito_cartao")]
    usados: set[int] = set()

    # Cada linha ganha uma chave estável para o front referenciar.
    linhas = [dict(l, _chave=f"l{i}") for i, l in enumerate(lido["linhas"])]

    def achar(valor: int, data: str, exato: bool) -> dict | None:
        melhor, melhor_dist = None, None
        for t in app:
            if t["id"] in usados:
                continue
            ef = _sinal_app(t)
            if exato:
                if ef != valor:
                    continue
            else:
                if (ef > 0) != (valor > 0):
                    continue
                if abs(ef - valor) > max(200, round(abs(valor) * 0.05)):
                    continue
            dist = _dias(t["data"], data)
            if melhor is None or dist < melhor_dist:
                melhor, melhor_dist = t, dist
        return melhor

    for ln in linhas:                         # 1ª passada: valor exato
        a = achar(ln["valor_centavos"], ln["data"], exato=True)
        if a:
            usados.add(a["id"]); ln["_app"] = a
    for ln in linhas:                         # 2ª passada: valor próximo
        if "_app" not in ln:
            a = achar(ln["valor_centavos"], ln["data"], exato=False)
            if a:
                usados.add(a["id"]); ln["_div"] = a

    casados, divergencias, so_fatura = [], [], []
    for ln in linhas:
        if "_app" in ln:
            casados.append({"fatura": _lin_pub(ln["_chave"], ln), "app": _app_pub(ln["_app"])})
        elif "_div" in ln:
            divergencias.append({"fatura": _lin_pub(ln["_chave"], ln), "app": _app_pub(ln["_div"]),
                                 "diferenca_centavos": ln["valor_centavos"] - _sinal_app(ln["_div"])})
        else:
            so_fatura.append(_lin_pub(ln["_chave"], ln))
    so_app = [_app_pub(t) for t in app if t["id"] not in usados]

    extrato = lido["total_compras"]
    return {
        "cartao": det["cartao"], "competencia": competencia, "fatura_id": det["fatura_id"],
        "casados": casados, "divergencias": divergencias, "so_fatura": so_fatura, "so_app": so_app,
        "pagamentos": [{"data": p["data"], "descricao": p["descricao"],
                        "valor_centavos": p["valor_centavos"]} for p in lido["pagamentos"]],
        "totais": {"app": det["total"], "extrato": extrato, "diferenca": det["total"] - extrato},
        "resumo": {"linhas_fatura": len(linhas), "casados": len(casados),
                   "divergencias": len(divergencias), "so_fatura": len(so_fatura),
                   "so_app": len(so_app), "pagamentos": len(lido["pagamentos"])},
    }


def aplicar(con: sqlite3.Connection, cartao_id: int, competencia: str,
            conferir_ids: list[int], criar: list[dict], valor_banco: int | None = None,
            ajustar: list[dict] | None = None) -> dict:
    """Marca casados como conferidos, ajusta valores divergentes, lança o que faltou
    NA FATURA e grava o total do extrato."""
    # Ajuste de valor (ex.: diferença de R$ 0,01 numa divergência): acerta o valor
    # do lançamento para o da fatura e já o dá por conferido. O valor vem COM SINAL
    # do ponto de vista da fatura; guardamos o módulo (o tipo despesa/crédito não muda,
    # pois uma divergência só casa linhas de mesmo sinal).
    ajustados = 0
    for item in (ajustar or []):
        alvo = int(item["valor_centavos"])
        tx.editar(con, int(item["id"]), {"valor_centavos": abs(alvo), "conferido": 1})
        ajustados += 1
    conferidos = 0
    for id_ in conferir_ids:
        tx.editar(con, id_, {"conferido": 1})
        conferidos += 1
    criados = 0
    for linha in criar:
        valor = int(linha["valor_centavos"])            # com sinal
        credito = valor < 0
        quando = linha["data"]
        if not isinstance(quando, date):
            quando = date.fromisoformat(quando)
        nova = tx.NovaTransacao(
            tipo="credito_cartao" if credito else "despesa_cartao",
            descricao=(linha.get("descricao") or "").strip() or "Lançamento da fatura",
            valor_centavos=abs(valor), data=quando, cartao_id=cartao_id,
            fatura_competencia=competencia, parcelas=1,
            categoria_id=linha.get("categoria_id"))
        for id_ in tx.criar(con, nova):
            tx.editar(con, id_, {"conferido": 1})
        criados += 1
    gravou_banco = False
    if valor_banco is not None:
        try:
            fatura_cartao.informar_valor_banco(con, cartao_id, competencia, valor_banco)
            gravou_banco = True
        except Exception:
            gravou_banco = False
    return {"conferidos": conferidos, "ajustados": ajustados, "criados": criados,
            "valor_banco_gravado": gravou_banco}
