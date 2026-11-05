"""Relatórios (Fase 4): evolução mensal, despesas por categoria no tempo e por projeto (tag)."""
from app.services import relatorios, transacoes
from datetime import date

from app.services.transacoes import NovaTransacao


def _conta(con):
    return con.execute("SELECT id FROM conta WHERE nome = 'Carteira'").fetchone()[0]


def _cat(con, nome):
    return con.execute("SELECT id FROM categoria WHERE nome = ?", (nome,)).fetchone()[0]


def _tag(con, nome):
    return con.execute("INSERT INTO tag (nome) VALUES (?)", (nome,)).lastrowid


def test_meses_entre_inclui_vazios():
    assert relatorios._meses_entre("2026-09-01", "2026-11-30") == ["2026-09", "2026-10", "2026-11"]
    assert relatorios._meses_entre("2026-12-01", "2027-02-10") == ["2026-12", "2027-01", "2027-02"]


def test_evolucao_mensal_e_categorias(con):
    conta = _conta(con)
    merc, farm = _cat(con, "Mercado"), _cat(con, "Farmácia")
    transacoes.criar(con, NovaTransacao(tipo="receita", descricao="Salário", valor_centavos=500000,
                                        data=date(2026, 9, 5), conta_id=conta, categoria_id=_cat(con, "Salário")))
    transacoes.criar(con, NovaTransacao(tipo="despesa", descricao="Compra", valor_centavos=30000,
                                        data=date(2026, 9, 10), conta_id=conta, categoria_id=merc))
    transacoes.criar(con, NovaTransacao(tipo="despesa", descricao="Remédio", valor_centavos=8000,
                                        data=date(2026, 10, 2), conta_id=conta, categoria_id=farm))

    r = relatorios.periodo(con, "2026-09-01", "2026-10-31")
    assert [m["competencia"] for m in r["meses"]] == ["2026-09", "2026-10"]
    set_ = r["meses"][0]
    assert set_["receitas"] == 500000 and set_["despesas"] == 30000 and set_["resultado"] == 470000
    assert r["meses"][1]["despesas"] == 8000
    assert r["resumo"]["receitas"] == 500000 and r["resumo"]["despesas"] == 38000
    assert r["resumo"]["resultado"] == 462000 and r["resumo"]["mes_maior_despesa"] == "2026-09"
    # categorias-mãe: Alimentação (Mercado) e Saúde (Farmácia)
    nomes = {c["categoria"]: c for c in r["por_categoria"]}
    assert nomes["Alimentação"]["total"] == 30000 and nomes["Alimentação"]["serie"] == [30000, 0]
    assert nomes["Saúde"]["serie"] == [0, 8000]
    assert round(sum(c["pct"] for c in r["por_categoria"])) == 100


def test_credito_cartao_abate_e_tag_agrupa(con):
    conta = _conta(con)
    merc = _cat(con, "Mercado")
    projeto = _tag(con, "CERCO FELINO")
    transacoes.criar(con, NovaTransacao(tipo="despesa", descricao="Ração", valor_centavos=20000,
                                        data=date(2026, 11, 3), conta_id=conta, categoria_id=merc,
                                        tags=[projeto]))
    # estorno (crédito no cartão) abate a despesa
    cartao = con.execute("INSERT INTO cartao (nome, bandeira, final, limite_centavos, dia_fechamento, dia_vencimento) "
                         "VALUES ('C6','visa','1234',500000,1,10)").lastrowid
    transacoes.criar(con, NovaTransacao(tipo="credito_cartao", descricao="Estorno", valor_centavos=5000,
                                        data=date(2026, 11, 4), cartao_id=cartao, categoria_id=merc))

    r = relatorios.periodo(con, "2026-11-01", "2026-11-30")
    aliment = next(c for c in r["por_categoria"] if c["categoria"] == "Alimentação")
    assert aliment["total"] == 15000            # 20000 − 5000 de estorno
    assert r["resumo"]["despesas"] == 15000
    tag = r["por_tag"][0]
    assert tag["tag"] == "CERCO FELINO" and tag["total"] == 20000 and tag["lancamentos"] == 1
