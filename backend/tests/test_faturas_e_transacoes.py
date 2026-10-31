from datetime import date

import pytest

from app.services import faturas, painel
from app.services.transacoes import NovaTransacao, RegraViolada, criar


@pytest.mark.parametrize("compra,fech,venc,esperado", [
    (date(2026, 10, 2), 3, 10, "2026-10"),    # antes do fechamento: vence no mesmo mês
    (date(2026, 10, 3), 3, 10, "2026-11"),    # no dia do fechamento: próxima fatura
    (date(2026, 10, 20), 25, 5, "2026-11"),   # vence dia 5: cai no mês seguinte ao fechamento
    (date(2026, 10, 28), 25, 5, "2026-12"),   # depois do fechamento de 25/10: fatura de dezembro
    (date(2026, 12, 20), 15, 1, "2027-02"),   # virada de ano: fecha 15/01, vence 01/02
    (date(2026, 2, 27), 31, 10, "2026-03"),   # dia 31 em fevereiro fecha em 28/02
])
def test_competencia_da_fatura(compra, fech, venc, esperado):
    assert faturas.competencia(compra, fech, venc) == esperado


def _cenario(con):
    """Contas e cartão parecidos com os do João (valores de exemplo)."""
    with con:
        c6 = con.execute("INSERT INTO conta (nome, tipo, saldo_inicial_centavos, data_saldo_inicial) "
                         "VALUES ('C6 Bank', 'corrente', 42029, '2026-10-01')").lastrowid
        inv = con.execute("INSERT INTO conta (nome, tipo, saldo_inicial_centavos, data_saldo_inicial, "
                          "compoe_saldo_disponivel) VALUES ('C6 Invest', 'investimento', 110626, "
                          "'2026-10-01', 0)").lastrowid
        bb = con.execute("INSERT INTO cartao (nome, bandeira, final, limite_centavos, dia_fechamento, "
                         "dia_vencimento) VALUES ('BB JU', 'Visa', '3756', 2227900, 3, 10)").lastrowid
    cat = con.execute("SELECT id FROM categoria WHERE nome = 'Mercado'").fetchone()[0]
    return c6, inv, bb, cat


def test_transferencia_cria_duas_pernas_e_nao_muda_patrimonio(con):
    c6, inv, _, _ = _cenario(con)
    antes = painel.resumo(con, "2026-10")["patrimonio"]
    ids = criar(con, NovaTransacao("transferencia", "Aplicação", 10000, date(2026, 10, 28),
                                   conta_id=c6, conta_destino_id=inv))
    assert len(ids) == 2
    r = painel.resumo(con, "2026-10")
    assert r["patrimonio"] == antes
    assert r["saldo_disponivel"] == 42029 - 10000
    assert r["despesas"] == 0  # transferência não é despesa


def test_saldo_disponivel_separa_investimentos(con):
    _cenario(con)
    r = painel.resumo(con, "2026-10")
    assert r["saldo_disponivel"] == 42029          # só a conta corrente
    assert r["patrimonio"] == 42029 + 110626       # corrente + investimento


def test_despesa_cartao_parcelada_e_pagamento_nao_contam_em_dobro(con):
    c6, _, bb, cat = _cenario(con)
    criar(con, NovaTransacao("despesa_cartao", "Geladeira", 100001, date(2026, 10, 2),
                             cartao_id=bb, parcelas=3, categoria_id=cat))
    valores = [r[0] for r in con.execute(
        "SELECT valor_centavos FROM transacao ORDER BY parcela")]
    assert valores == [33335, 33333, 33333] and sum(valores) == 100001
    comps = [r[0] for r in con.execute(
        "SELECT f.competencia FROM transacao t JOIN fatura f ON f.id = t.fatura_id ORDER BY parcela")]
    assert comps == ["2026-10", "2026-11", "2026-12"]

    criar(con, NovaTransacao("pagamento_fatura", "Fatura BB", 33335, date(2026, 10, 10),
                             conta_id=c6, cartao_id=bb, fatura_competencia="2026-10"))
    datas = [r[0] for r in con.execute("SELECT data FROM transacao WHERE tipo = 'despesa_cartao' ORDER BY parcela")]
    assert datas == ["2026-10-02", "2026-11-02", "2026-12-02"]
    out = painel.resumo(con, "2026-10")
    assert out["despesas"] == 33335                      # só a 1ª parcela em outubro
    assert painel.resumo(con, "2026-11")["despesas"] == 33333
    cartao = out["cartoes"][0]
    assert cartao["fatura_situacao"] == "paga"
    assert cartao["limite_disponivel"] == 2227900 - (100001 - 33335)
    assert out["saldo_disponivel"] == 42029 - 33335      # pagamento saiu da conta


def test_pagamento_sem_fatura_fechada_e_recusado(con):
    c6, _, bb, _ = _cenario(con)
    with pytest.raises(RegraViolada):
        criar(con, NovaTransacao("pagamento_fatura", "Fatura", 100, date(2026, 10, 1),
                                 conta_id=c6, cartao_id=bb))


def test_despesa_com_itens_divide_por_categoria(con):
    c6, _, _, mercado = _cenario(con)
    limpeza = con.execute("SELECT id FROM categoria WHERE nome = 'Limpeza'").fetchone()[0]
    (tid,) = criar(con, NovaTransacao("despesa", "SUPERMERCADO PERIM", 2694, date(2026, 10, 9),
                                      conta_id=c6))
    with con:
        con.executemany(
            "INSERT INTO item (transacao_id, seq, descricao_lida, quantidade_milesimos, "
            "preco_unitario_centavos, desconto_centavos, valor_total_centavos, categoria_id) "
            "VALUES (?, ?, ?, 1000, ?, ?, ?, ?)",
            [(tid, 1, "MANTEIGA ITALAT C/SAL 30/200G", 898, 0, 898, mercado),
             (tid, 2, "BATATA CONG UAI 7/2K", 2180, 182, 2180, mercado),
             (tid, 3, "DET BARRA LIMAO", 229, 0, 229, limpeza)])
    por_cat = {r["categoria"]: r["total"] for r in painel.despesas_por_categoria(con, "2026-10")}
    assert por_cat == {"Alimentação": 898 + 1998, "Casa": 229}
