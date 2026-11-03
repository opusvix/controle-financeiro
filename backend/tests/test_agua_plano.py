"""CESAN (água), Unimed (plano de saúde) e índices: leitura dos PDFs e painéis."""
from pathlib import Path

from app.importacao import contas_pdf
from app.services import agua, indices, plano

DADOS = Path(__file__).parent / "dados"


def _txt(nome):
    return (DADOS / nome).read_text(encoding="utf-8")


def test_le_a_cesan_nos_dois_layouts():
    f = contas_pdf.ler_cesan(_txt("cesan_amostra.txt"))
    assert (f.referencia, f.vencimento, f.total_centavos) == ("2026-09", "2026-10-13", 14751)
    assert f.ficha["consumo"] == 14.0
    assert f.ficha["fixo_centavos"] == 4975 + 3980          # água + esgoto, parte fixa
    assert ("2025-09", 16.0, None) in f.historico
    v = contas_pdf.ler_cesan(_txt("cesan_antiga_amostra.txt"))
    assert (v.referencia, v.vencimento, v.total_centavos) == ("2026-02", "2026-03-13", 15046)
    assert (v.ficha["consumo"], v.ficha["fixo_centavos"]) == (18.0, 4489 + 3591)


def test_le_a_unimed_por_beneficiario():
    f = contas_pdf.ler_unimed(_txt("unimed_amostra.txt"))
    assert (f.referencia, f.vencimento, f.total_centavos) == ("2026-10", "2026-10-30", 98962)
    assert f.ficha["vidas"] == 3
    assert len(f.itens) == 6 and sum(v for *_, v in f.itens) == 98962
    assert ("FULANO DE TAL", "MENSALIDADE", 28699) in f.itens


def _conta(con):
    con.execute("INSERT INTO conta(nome, tipo) VALUES ('X', 'corrente')")
    return con.execute("SELECT max(id) FROM conta").fetchone()[0]


def _mes_plano(con, conta, ref, itens):
    total = sum(v for *_, v in itens)
    con.execute("INSERT INTO transacao(tipo, descricao, valor_centavos, data, conta_id, pago) "
                "VALUES ('despesa', 'UNIMED', ?, ?, ?, 1)", (total, f"{ref}-30", conta))
    tid = con.execute("SELECT max(id) FROM transacao").fetchone()[0]
    con.execute("INSERT INTO conta_ficha(transacao_id, tipo, referencia, vidas) VALUES (?, 'saude', ?, 2)", (tid, ref))
    con.executemany("INSERT INTO plano_item VALUES (?, ?, ?, ?)", [(tid, b, i, v) for b, i, v in itens])


def test_separa_faixa_etaria_do_reajuste_anual_e_compara_com_indices(con):
    conta = _conta(con)
    _mes_plano(con, conta, "2026-01", [("ANA X", "MENSALIDADE", 30000), ("BIA X", "MENSALIDADE", 20000)])
    _mes_plano(con, conta, "2026-02", [("ANA X", "MENSALIDADE", 30000), ("BIA X", "MENSALIDADE", 23000)])
    _mes_plano(con, conta, "2026-08", [("ANA X", "MENSALIDADE", 31533), ("BIA X", "MENSALIDADE", 24175)])
    # IPCA de 0,4% ao mês de ago/25 a jul/26 → 4,91% em 12 meses
    fake = {indices.SERIES["IPCA"]: [{"data": f"01/{indices._somar_mes('2025-08', i)[5:]}/"
                                             f"{indices._somar_mes('2025-08', i)[:4]}", "valor": "0.4"}
                                     for i in range(12)]}
    r = indices.atualizar(con, baixar=lambda url: fake.get(int(url.split("sgs.")[1].split("/")[0]), []))
    assert r["IPCA"]["meses"] == 12 and r["IPCA"]["ultimo"] == "2026-07"

    ev = plano.painel(con)["eventos"]
    assert [(e["referencia"], e["tipo"]) for e in ev] == [("2026-02", "faixa_etaria"), ("2026-08", "anual")]
    assert ev[0]["quem"] == ["Bia"] and ev[0]["detalhe"][0]["percentual"] == 15.0
    anual = ev[1]
    assert anual["percentual"] == 5.11 and anual["teto_ans"]["percentual"] == 5.11
    assert anual["acima_do_teto"] is False
    ipca = next(c for c in anual["comparacao"] if c["indice"] == "IPCA")
    assert ipca["percentual"] == 4.91 and ipca["periodo"] == "2025-08 a 2026-07"
    assert next(c for c in anual["comparacao"] if c["indice"] == "INPC")["percentual"] is None


def test_painel_da_agua_separa_fixo_e_variavel(con):
    conta = _conta(con)
    con.execute("INSERT INTO transacao(tipo, descricao, valor_centavos, data, conta_id, pago) "
                "VALUES ('despesa', 'CESAN', 14751, '2026-10-16', ?, 1)", (conta,))
    tid = con.execute("SELECT max(id) FROM transacao").fetchone()[0]
    con.execute("INSERT INTO conta_ficha(transacao_id, tipo, referencia, consumo, fixo_centavos) "
                "VALUES (?, 'agua', '2026-09', 14, 8955)", (tid,))
    con.execute("INSERT INTO conta_historico(tipo, referencia, consumo) VALUES ('agua', '2025-09', 16)")
    d = agua.painel(con)
    m = d["meses"][0]
    assert (m["fixo_centavos"], m["variavel_centavos"], m["custo_m3"]) == (8955, 14751 - 8955, round(14751 / 14))
    assert d["resumo"]["variacao_consumo_pct"] == -12.5
