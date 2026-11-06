"""Conciliação bancária: leitura do OFX e cruzamento com os lançamentos da conta."""
from datetime import date

import pytest

from app.services import conciliacao
from app.services import transacoes as tx
from app.services.transacoes import NovaTransacao

OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261103120000<TRNAMT>-62.85<FITID>a1<MEMO>FRESCOR HORTIFRUTI</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261105<TRNAMT>1000.00<FITID>a2<NAME>SALARIO</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261105<TRNAMT>-45.10<FITID>a3<MEMO>MERCADO X</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261104<TRNAMT>-99.99<FITID>a4<MEMO>TARIFA</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def _conta(con):
    return con.execute("SELECT id FROM conta WHERE nome = 'Carteira'").fetchone()[0]


def _cat(con, nome):
    return con.execute("SELECT id FROM categoria WHERE nome = ?", (nome,)).fetchone()[0]


def test_ler_ofx_extrai_linhas_com_sinal():
    linhas = conciliacao.ler_ofx(OFX.encode("latin-1"))
    assert len(linhas) == 4
    assert linhas[0] == {"fitid": "a1", "data": "2026-11-03",
                         "valor_centavos": -6285, "descricao": "FRESCOR HORTIFRUTI"}
    assert linhas[1]["valor_centavos"] == 100000 and linhas[1]["descricao"] == "SALARIO"  # via NAME


def test_ler_ofx_rejeita_arquivo_invalido():
    with pytest.raises(conciliacao.OFXInvalido):
        conciliacao.ler_ofx(b"isto nao e um OFX")


def test_conciliar_quatro_baldes(con):
    conta = _conta(con)
    merc = _cat(con, "Mercado")
    tx.criar(con, NovaTransacao(tipo="despesa", descricao="Frescor", valor_centavos=6285,
                                data=date(2026, 11, 3), conta_id=conta, categoria_id=merc))   # casa a1
    tx.criar(con, NovaTransacao(tipo="receita", descricao="Salário", valor_centavos=100000,
                                data=date(2026, 11, 5), conta_id=conta,
                                categoria_id=_cat(con, "Salário")))                            # casa a2
    tx.criar(con, NovaTransacao(tipo="despesa", descricao="Mercadinho", valor_centavos=4500,
                                data=date(2026, 11, 5), conta_id=conta, categoria_id=merc))    # diverge a3
    tx.criar(con, NovaTransacao(tipo="despesa", descricao="Só no app", valor_centavos=3000,
                                data=date(2026, 11, 4), conta_id=conta, categoria_id=merc))    # só app

    r = conciliacao.conciliar(con, conta, conciliacao.ler_ofx(OFX.encode("latin-1")))
    assert r["resumo"] == {"linhas_extrato": 4, "casados": 2, "divergencias": 1,
                           "so_banco": 1, "so_app": 1}
    assert r["so_banco"][0]["fitid"] == "a4"                       # tarifa 99,99
    assert r["divergencias"][0]["diferenca_centavos"] == -10      # -45,10 vs -45,00
    # o lançamento casado traz o id para marcar conferido depois
    assert all("id" in c["app"] for c in r["casados"])


def test_aplicar_confere_e_cria(con):
    conta = _conta(con)
    merc = _cat(con, "Mercado")
    [tid] = tx.criar(con, NovaTransacao(tipo="despesa", descricao="X", valor_centavos=5000,
                                        data=date(2026, 11, 3), conta_id=conta, categoria_id=merc))
    saida = conciliacao.aplicar(con, conta, conferir_ids=[tid], criar=[
        {"data": "2026-11-04", "valor_centavos": -9999, "descricao": "TARIFA", "categoria_id": merc}])
    assert saida == {"conferidos": 1, "criados": 1, "renomeados": 0}
    assert con.execute("SELECT conferido FROM transacao WHERE id = ?", (tid,)).fetchone()[0] == 1
    nova = con.execute("SELECT tipo, valor_centavos, conferido FROM transacao "
                       "WHERE descricao = 'TARIFA'").fetchone()
    assert tuple(nova) == ("despesa", 9999, 1)


def test_aplicar_renomeia_lancamento_existente(con):
    conta = _conta(con)
    merc = _cat(con, "Mercado")
    [tid] = tx.criar(con, NovaTransacao(tipo="despesa", descricao="COMPRA DEBITO 123",
                                        valor_centavos=5000, data=date(2026, 11, 3),
                                        conta_id=conta, categoria_id=merc))
    saida = conciliacao.aplicar(con, conta, conferir_ids=[tid], criar=[],
                                renomear=[{"id": tid, "descricao": "  Mercado da esquina  "}])
    assert saida == {"conferidos": 1, "criados": 0, "renomeados": 1}
    row = con.execute("SELECT descricao, conferido FROM transacao WHERE id = ?", (tid,)).fetchone()
    assert tuple(row) == ("Mercado da esquina", 1)   # texto aparado e conferido


def test_endpoint_analisar_e_aplicar(cliente):
    con = cliente.app.state.con
    conta = _conta(con)
    r = cliente.post("/api/conciliacao/analisar",
                     files={"arquivo": ("extrato.ofx", OFX.encode("latin-1"), "application/x-ofx")},
                     data={"conta_id": str(conta), "tolerancia_dias": "3"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["resumo"]["linhas_extrato"] == 4 and corpo["resumo"]["so_banco"] == 4

    ap = cliente.post("/api/conciliacao/aplicar", json={
        "conta_id": conta, "conferir_ids": [],
        "criar": [{"data": "2026-11-05", "valor_centavos": 100000, "descricao": "SALARIO"}]})
    assert ap.status_code == 200 and ap.json()["criados"] == 1
