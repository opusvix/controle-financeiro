"""Dados fictícios para a versão de DEMONSTRAÇÃO.

Uma família imaginária ("Família Demonstração") com contas, cartões, um par de
meses de lançamentos, faturas, contas fixas e dois cupons de hortifruti — para
todas as telas aparecerem cheias, SEM nunca usar os dados reais do usuário.

Só roda quando o app está em modo demo (CF_MODO_DEMO=1), sobre um banco próprio
(financeiro_demo.db). `garantir` semeia se estiver vazio; `reiniciar` apaga tudo
e semeia de novo (é o botão "Reiniciar demonstração").
"""
from __future__ import annotations

import sqlite3
from datetime import date

from . import seed
from .services import faturas
from .services import transacoes as tx
from .services.transacoes import NovaTransacao

# Tabelas de dados que o "Reiniciar demonstração" limpa (o schema e _migracao ficam).
_TABELAS_DADOS = [
    "transacao_tag", "item", "transacao", "fatura", "cartao",
    "conta_ficha", "conta_historico", "conta", "documento", "estabelecimento",
    "produto_alias", "produto", "grupo_produto", "orcamento", "plano_item",
    "filtro_salvo", "tag", "categoria", "instituicao", "configuracao", "backup_log",
]


def _cat(con: sqlite3.Connection, nome: str) -> int:
    return con.execute("SELECT id FROM categoria WHERE nome = ? ORDER BY pai_id IS NOT NULL, id "
                       "LIMIT 1", (nome,)).fetchone()[0]


def _conta(con: sqlite3.Connection, nome: str, saldo_centavos: int, abertura: date,
           tipo: str = "corrente", cor: str = "#6b7280") -> int:
    inst = con.execute("SELECT id FROM instituicao WHERE nome = ?", (nome,)).fetchone()
    return con.execute(
        "INSERT INTO conta (nome, instituicao_id, tipo, saldo_inicial_centavos, "
        "data_saldo_inicial, cor) VALUES (?, ?, ?, ?, ?, ?)",
        (nome, inst["id"] if inst else None, tipo, saldo_centavos, abertura.isoformat(), cor)
    ).lastrowid


def _cartao(con: sqlite3.Connection, nome: str, bandeira: str, final: str, fecha: int,
            vence: int, conta_pagamento_id: int, cor: str) -> int:
    return con.execute(
        "INSERT INTO cartao (nome, bandeira, final, limite_centavos, dia_fechamento, "
        "dia_vencimento, conta_pagamento_id, cor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (nome, bandeira, final, 800000, fecha, vence, conta_pagamento_id, cor)).lastrowid


def _estab(con: sqlite3.Connection, nome: str, cidade: str = "Vitória", uf: str = "ES") -> int:
    return con.execute("INSERT INTO estabelecimento (nome, cidade, uf) VALUES (?, ?, ?)",
                       (nome, cidade, uf)).lastrowid


def _despesa(con, descricao, centavos, data_, conta_id, categoria, *, pago=True,
             tags=None, estab=None):
    return tx.criar(con, NovaTransacao(
        tipo="despesa", descricao=descricao, valor_centavos=centavos, data=data_,
        conta_id=conta_id, categoria_id=_cat(con, categoria), pago=pago,
        estabelecimento_id=estab, tags=tags or []))[0]


def _no_cartao(con, descricao, centavos, data_, cartao_id, categoria, *, parcelas=1):
    return tx.criar(con, NovaTransacao(
        tipo="despesa_cartao", descricao=descricao, valor_centavos=centavos, data=data_,
        cartao_id=cartao_id, categoria_id=_cat(con, categoria), parcelas=parcelas))


def _itens(con: sqlite3.Connection, transacao_id: int, estab_id: int, data_: str,
           linhas: list[tuple]) -> None:
    """linhas: (descricao_lida, qtd_milesimos, unidade, preco_unit_centavos, categoria)."""
    for seq, (desc, qtd, un, preco, categoria) in enumerate(linhas, start=1):
        total = round(preco * qtd / 1000)
        con.execute(
            "INSERT INTO item (transacao_id, documento_id, seq, descricao_lida, "
            "quantidade_milesimos, unidade, preco_unitario_centavos, valor_total_centavos, "
            "categoria_id) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)",
            (transacao_id, seq, desc, qtd, un, preco, total, _cat(con, categoria)))


def construir(con: sqlite3.Connection, hoje: date | None = None) -> None:
    """Monta o conjunto de demonstração. Pressupõe o banco já migrado."""
    hoje = hoje or date.today()
    seed.popular(con)  # categorias, instituições e a Carteira

    def dia(offset_meses: int, d: int) -> date:
        base = faturas.somar_meses(date(hoje.year, hoje.month, 1), offset_meses)
        return date(base.year, base.month, d)

    with con:
        abertura = dia(-3, 1)
        c6 = _conta(con, "C6 Bank", 120000, abertura, cor="#111111")
        bb = _conta(con, "Banco do Brasil", 80000, abertura, cor="#f7d417")
        carteira = con.execute("SELECT id FROM conta WHERE nome = 'Carteira'").fetchone()[0]

        mc = _cartao(con, "C6 Mastercard", "Mastercard", "1234", 28, 10, c6, "#111111")
        visa = _cartao(con, "BB Visa", "Visa", "5678", 2, 12, bb, "#f7d417")

        reforma = con.execute("INSERT INTO tag (nome, cor) VALUES ('Reforma', '#C25A12')"
                              ).lastrowid

        # Salário e contas fixas nos últimos 3 meses. O mês corrente fica a pagar.
        for m in (-3, -2, -1, 0):
            pago_mes = m < 0
            tx.criar(con, NovaTransacao(tipo="receita", descricao="Salário",
                     valor_centavos=650000, data=dia(m, 5), conta_id=c6,
                     categoria_id=_cat(con, "Salário"), pago=pago_mes))
            _despesa(con, "Conta de luz", 18540, dia(m, 10), c6, "Energia, água e gás",
                     pago=pago_mes)
            _despesa(con, "Internet + telefone", 11990, dia(m, 15), c6,
                     "Internet e telefone", pago=pago_mes)
            _despesa(con, "Plano de saúde", 52380, dia(m, 8), c6, "Plano de saúde",
                     pago=pago_mes)

        # Despesas variáveis dos últimos dois meses.
        _despesa(con, "Supermercado", 21045, dia(-2, 6), c6, "Mercado")
        _despesa(con, "Supermercado", 18030, dia(-1, 9), c6, "Mercado")
        _despesa(con, "Feira do bairro", 9560, dia(-1, 22), carteira, "Hortifruti")
        _despesa(con, "Restaurante", 6800, dia(-1, 14), c6, "Restaurante e lanche")
        _despesa(con, "Lanchonete", 4250, dia(0, 3), carteira, "Restaurante e lanche")
        _despesa(con, "Posto de gasolina", 25000, dia(-1, 18), c6, "Combustível")
        _despesa(con, "Farmácia", 8320, dia(-1, 11), bb, "Farmácia")
        _despesa(con, "Pintura da sala", 34000, dia(-1, 20), bb, "Manutenção",
                 tags=[reforma])
        _despesa(con, "Material de construção", 12750, dia(0, 2), bb, "Manutenção",
                 tags=[reforma])

        # Compras no cartão (criam as faturas automaticamente).
        _no_cartao(con, "Streaming de vídeo", 3990, dia(-2, 20), mc, "Lazer")
        _no_cartao(con, "Streaming de vídeo", 3990, dia(-1, 20), mc, "Lazer")
        _no_cartao(con, "Compra online", 12900, dia(-1, 12), mc, "Eletrônicos")
        _no_cartao(con, "Fone de ouvido", 30000, dia(-2, 25), mc, "Eletrônicos", parcelas=3)
        _no_cartao(con, "Livraria", 8900, dia(-1, 7), visa, "Educação")
        _no_cartao(con, "Posto (crédito)", 15000, dia(-1, 16), visa, "Combustível")

        # Paga a fatura mais antiga já fechada do Mastercard.
        fat = con.execute(
            "SELECT competencia, data_vencimento FROM fatura WHERE cartao_id = ? "
            "AND data_fechamento <= ? ORDER BY competencia LIMIT 1", (mc, hoje.isoformat())
        ).fetchone()
        if fat:
            total = con.execute(
                "SELECT COALESCE(SUM(CASE WHEN tipo = 'credito_cartao' THEN -valor_centavos "
                "ELSE valor_centavos END), 0) FROM transacao WHERE cartao_id = ? AND "
                "fatura_id = (SELECT id FROM fatura WHERE cartao_id = ? AND competencia = ?)",
                (mc, mc, fat["competencia"])).fetchone()[0]
            if total > 0:
                venc = date.fromisoformat(fat["data_vencimento"])
                pago_fat = venc <= hoje
                tx.criar(con, NovaTransacao(
                    tipo="pagamento_fatura", descricao="Pagamento de fatura",
                    valor_centavos=total, data=venc, conta_id=c6, cartao_id=mc,
                    fatura_competencia=fat["competencia"], pago=pago_fat))

        # Dois cupons de hortifruti, em lojas e datas diferentes: histórico de preços.
        hortifruti = _estab(con, "Hortifruti do Bairro")
        mercado = _estab(con, "Supermercado Economia")
        d1 = dia(-1, 13)
        t1 = _despesa(con, "Hortifruti do Bairro", 4786, d1, c6, "Hortifruti",
                      estab=hortifruti)
        _itens(con, t1, hortifruti, d1.isoformat(), [
            ("LARANJA PERA KG", 2130, "kg", 399, "Frutas"),
            ("BANANA PRATA KG", 1240, "kg", 549, "Frutas"),
            ("TOMATE KG", 980, "kg", 699, "Legumes"),
        ])
        d2 = dia(0, 4)
        t2 = _despesa(con, "Supermercado Economia", 5930, d2, c6, "Hortifruti",
                      estab=mercado)
        _itens(con, t2, mercado, d2.isoformat(), [
            ("LARANJA PERA KG", 1890, "kg", 359, "Frutas"),
            ("BANANA PRATA KG", 1500, "kg", 599, "Frutas"),
            ("ALFACE UN", 2000, "un", 249, "Verduras"),
        ])


def _vazio(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT COUNT(*) FROM transacao").fetchone()[0] == 0


def garantir(con: sqlite3.Connection, hoje: date | None = None) -> bool:
    """Semeia a demonstração só se o banco ainda estiver vazio. Devolve se semeou."""
    if not _vazio(con):
        return False
    construir(con, hoje)
    return True


def reiniciar(con: sqlite3.Connection, hoje: date | None = None) -> None:
    """Apaga os dados e semeia de novo (botão 'Reiniciar demonstração')."""
    con.execute("PRAGMA foreign_keys = OFF")
    try:
        with con:
            for tabela in _TABELAS_DADOS:
                con.execute(f"DELETE FROM {tabela}")
    finally:
        con.execute("PRAGMA foreign_keys = ON")
    construir(con, hoje)
