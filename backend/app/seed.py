"""Dados iniciais: plano de categorias, instituições e a conta Carteira.

Roda só uma vez (quando não há categorias). Projetos como CERCO FELINO
viram TAGS na importação do Mobills, não categorias.
"""
from __future__ import annotations

import sqlite3

DESPESAS = {
    "Alimentação": ("#16a34a", ["Mercado", "Hortifruti", "Frutas", "Legumes", "Verduras",
                                "Carnes", "Laticínios", "Padaria",
                                "Bebidas", "Restaurante e lanche"]),
    "Casa": ("#0ea5e9", ["Limpeza", "Manutenção", "Energia, água e gás", "Internet e telefone"]),
    "Transporte": ("#6366f1", ["Combustível", "Estacionamento", "Manutenção do veículo",
                               "Impostos do veículo"]),
    "Saúde": ("#ef4444", ["Farmácia", "Consultas", "Dentista", "Plano de saúde"]),
    "Animais": ("#f59e0b", ["Ração", "Areia e higiene", "Veterinário"]),
    "Educação": ("#a855f7", []),
    "Lazer": ("#ec4899", []),
    "Vestuário": ("#14b8a6", []),
    "Eletrônicos": ("#eab308", []),
    "Taxas e serviços": ("#64748b", ["Cartório", "DETRAN", "Tarifas bancárias"]),
    "Doações": ("#84cc16", []),
    "Outras despesas": ("#9ca3af", []),
}
# Despesas fixas (contas da casa); as demais são variáveis. Mesma lista da migração 007.
FIXAS = ("Energia, água e gás", "Internet e telefone", "Plano de saúde")
RECEITAS = {
    "Salário": "#16a34a",
    "Rendimentos": "#0ea5e9",
    "Reembolsos": "#a855f7",
    "Outras receitas": "#9ca3af",
}
INSTITUICOES = [("C6 Bank", "336"), ("Itaú", "341"), ("Banco do Brasil", "001"),
                ("Mercado Pago", "323"), ("Dinheiro em espécie", None)]


def popular(con: sqlite3.Connection) -> bool:
    if con.execute("SELECT COUNT(*) FROM categoria").fetchone()[0]:
        return False
    with con:
        for nome, (cor, filhas) in DESPESAS.items():
            mae = con.execute("INSERT INTO categoria (nome, tipo, cor) VALUES (?, 'despesa', ?)",
                              (nome, cor)).lastrowid
            con.executemany(
                "INSERT INTO categoria (nome, tipo, cor, pai_id) VALUES (?, 'despesa', ?, ?)",
                [(f, cor, mae) for f in filhas])
        if any(c[1] == "fixa" for c in con.execute("PRAGMA table_info(categoria)")):
            con.execute(f"UPDATE categoria SET fixa = 1 WHERE tipo = 'despesa' AND nome IN "
                        f"({', '.join('?' for _ in FIXAS)})", FIXAS)
        con.executemany("INSERT INTO categoria (nome, tipo, cor) VALUES (?, 'receita', ?)",
                        RECEITAS.items())
        con.executemany("INSERT OR IGNORE INTO instituicao (nome, codigo) VALUES (?, ?)",
                        INSTITUICOES)
        especie = con.execute("SELECT id FROM instituicao WHERE nome = 'Dinheiro em espécie'"
                              ).fetchone()[0]
        con.execute("INSERT OR IGNORE INTO conta (nome, instituicao_id, tipo, cor) "
                    "VALUES ('Carteira', ?, 'carteira', '#84cc16')", (especie,))
    return True
