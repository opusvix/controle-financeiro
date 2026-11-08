"""Orçamento × realizado: teto por categoria-mãe e competência, comparado com o gasto do mês."""
from datetime import date

from app.services import orcamento
from app.services import transacoes as tx
from app.services.transacoes import NovaTransacao


def _conta(con):
    return con.execute("SELECT id FROM conta WHERE nome = 'Carteira'").fetchone()[0]


def _cat(con, nome):
    return con.execute("SELECT id FROM categoria WHERE nome = ?", (nome,)).fetchone()[0]


def test_orcado_realizado_por_categoria_mae(con):
    conta = _conta(con)
    alim = _cat(con, "Alimentação")      # categoria-mãe
    merc = _cat(con, "Mercado")          # subcategoria de Alimentação
    with con:
        orcamento.definir(con, alim, "2026-11", 50000)      # teto R$ 500 em nov/26
    tx.criar(con, NovaTransacao(tipo="despesa", descricao="Feira", valor_centavos=12000,
                                data=date(2026, 11, 10), conta_id=conta, categoria_id=merc))

    r = orcamento.ver(con, "2026-11")
    linha = next(l for l in r["linhas"] if l["categoria_id"] == alim)
    assert linha["orcado_centavos"] == 50000
    assert linha["realizado_centavos"] == 12000      # gasto na subcategoria soma na mãe
    assert linha["saldo_centavos"] == 38000
    assert linha["pct"] == 24
    assert r["total"]["orcado_centavos"] == 50000
    assert r["total"]["realizado_centavos"] == 12000


def test_teto_vale_por_competencia(con):
    alim = _cat(con, "Alimentação")
    with con:
        orcamento.definir(con, alim, "2026-11", 50000)
    # Em dez/26 não há teto nem gasto: a categoria não aparece.
    r = orcamento.ver(con, "2026-12")
    assert all(l["categoria_id"] != alim for l in r["linhas"])


def test_definir_e_remover_teto(con):
    alim = _cat(con, "Alimentação")
    with con:
        orcamento.definir(con, alim, "2026-11", 30000)
    assert con.execute("SELECT valor_centavos FROM orcamento WHERE categoria_id = ? AND competencia = ?",
                       (alim, "2026-11")).fetchone()[0] == 30000
    with con:
        orcamento.definir(con, alim, "2026-11", 0)          # valor 0 remove
    assert con.execute("SELECT 1 FROM orcamento WHERE categoria_id = ? AND competencia = ?",
                       (alim, "2026-11")).fetchone() is None


def test_copiar_nao_sobrescreve_teto_existente(con):
    alim = _cat(con, "Alimentação")
    with con:
        orcamento.definir(con, alim, "2026-11", 50000)
        orcamento.definir(con, alim, "2026-12", 60000)      # dez já tem teto próprio
    with con:
        copiados = orcamento.copiar_do_mes_anterior(con, "2026-12")
    # Alimentação já tinha teto em dez, então não é sobrescrito; nada a copiar.
    assert copiados == 0
    assert con.execute("SELECT valor_centavos FROM orcamento WHERE categoria_id = ? AND competencia = ?",
                       (alim, "2026-12")).fetchone()[0] == 60000


def test_copiar_traz_teto_que_faltava(con):
    alim = _cat(con, "Alimentação")
    with con:
        orcamento.definir(con, alim, "2026-11", 50000)
    with con:
        copiados = orcamento.copiar_do_mes_anterior(con, "2026-12")   # dez não tinha nada
    assert copiados == 1
    assert con.execute("SELECT valor_centavos FROM orcamento WHERE categoria_id = ? AND competencia = ?",
                       (alim, "2026-12")).fetchone()[0] == 50000


def test_endpoint_orcamento(cliente):
    con = cliente.app.state.con
    alim = _cat(con, "Alimentação")
    assert cliente.put("/api/orcamento", json={
        "categoria_id": alim, "competencia": "2026-11", "valor_centavos": 40000}).status_code == 200
    g = cliente.get("/api/orcamento?competencia=2026-11")
    assert g.status_code == 200
    linha = next(l for l in g.json()["linhas"] if l["categoria_id"] == alim)
    assert linha["orcado_centavos"] == 40000
