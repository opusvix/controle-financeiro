"""Índices de preço (Banco Central, SGS) e teto da ANS: a régua para medir um reajuste.

Analogia: o reajuste do plano é o "preço" que subiu; os índices são o termômetro da inflação
no mesmo período (12 meses até o mês anterior ao reajuste). Se o plano subiu mais que o
termômetro, ficou mais caro de verdade.
"""
import json
import sqlite3
import urllib.request
from typing import Callable

# Códigos das séries no SGS do Banco Central (variação % no mês).
SERIES = {"IPCA": 433, "INPC": 188, "IGP-M": 189, "IGP-DI": 190, "IPC-Fipe": 193}
URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=01/01/2018"


def _baixar(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "controle-financeiro"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def atualizar(con: sqlite3.Connection, baixar: Callable[[str], list[dict]] = _baixar) -> dict:
    """Baixa as séries do Banco Central e grava (ou corrige) mês a mês. Precisa de internet."""
    resultado = {}
    for nome, codigo in SERIES.items():
        try:
            dados = baixar(URL.format(codigo=codigo))
            linhas = [(nome, f"{d['data'][6:10]}-{d['data'][3:5]}", float(d["valor"])) for d in dados]
            with con:
                con.executemany("INSERT INTO indice_mensal (indice, mes, valor) VALUES (?, ?, ?) "
                                "ON CONFLICT (indice, mes) DO UPDATE SET valor = excluded.valor", linhas)
            resultado[nome] = {"meses": len(linhas), "ultimo": max((m for _, m, _ in linhas), default=None)}
        except Exception as e:  # sem internet ou série fora do ar: segue com as outras
            resultado[nome] = {"erro": str(e)}
    return resultado


def _somar_mes(mes: str, n: int) -> str:
    a, m = int(mes[:4]), int(mes[5:7]) - 1 + n
    return f"{a + m // 12}-{m % 12 + 1:02d}"


def acumulado_12m(con: sqlite3.Connection, indice: str, ate: str) -> float | None:
    """Variação % acumulada nos 12 meses que terminam em `ate` (AAAA-MM). None se faltar mês."""
    meses = [_somar_mes(ate, -i) for i in range(12)]
    valores = dict(con.execute(
        f"SELECT mes, valor FROM indice_mensal WHERE indice = ? AND mes IN ({','.join('?' * 12)})",
        (indice, *meses)).fetchall())
    if len(valores) < 12:
        return None
    fator = 1.0
    for v in valores.values():
        fator *= 1 + v / 100
    return round((fator - 1) * 100, 2)


def teto_ans(con: sqlite3.Connection, mes: str) -> dict | None:
    """Teto da ANS do ciclo (maio a abril) que contém o mês do reajuste."""
    ano = int(mes[:4]) if int(mes[5:7]) >= 5 else int(mes[:4]) - 1
    r = con.execute("SELECT * FROM teto_ans WHERE ciclo_inicio = ?", (f"{ano}-05",)).fetchone()
    return dict(r) if r else None


def situacao(con: sqlite3.Connection) -> dict:
    return {nome: con.execute("SELECT max(mes) FROM indice_mensal WHERE indice = ?", (nome,)).fetchone()[0]
            for nome in SERIES}
