from datetime import date

import pytest
from openpyxl import Workbook

from app.importacao import mobills
from app.services import transacoes


@pytest.fixture
def planilha(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Receitas e Despesas"
    ws.append(["Data", "Descrição", "Valor", "Conta", "Situação", "Categoria", "Subcategoria", "Tags"])
    linhas = [
        ("01/10/2026", "Salário", 5000.0, "2 - Itaú", "Paga", "Salário", None, ""),
        ("02/10/2026", "PERIM", -123.45, "1 - C6 Bank 1118", "Paga", "Supermercado", None, None),
        ("02/10/2026", "PERIM", -123.45, "1 - C6 Bank 1118", "Paga", "Supermercado", None, None),
        ("03/10/2026", "Quilão", -50.1, "1 - C6 Bank 1118", "Paga", "Supermercado", "Quilão", ""),
        ("04/10/2026", "Tela gatil", -300.0, "1 - C6 Bank 1118", "Paga", "CERCO FELINO", None, ""),
        ("05/10/2026", "Geladeira - 12x (2/12)", -250.0, "4 - Bco Brasil JU 3756", "Paga",
         "Casa", "Eletro", "ignorar transação"),
        ("06/10/2026", "Rendimento", 10.5, "C6 Invest - CDB 102% CDI", "Paga", "Investimentos", None, ""),
        ("Total", None, 4163.5, None, None, None, None, None),
    ]
    for ln in linhas:
        ws.append(ln)
    t = wb.create_sheet("Transferências")
    t.append(["Data", "Conta origem", "Conta destino", "Valor", "Tags"])
    t.append(["07/10/2026", "2 - Itaú", "1 - C6 Bank 1118", 1000.0, ""])
    arq = tmp_path / "mobills.xlsx"
    wb.save(arq)
    return arq


def test_le_planilha_e_ignora_total(planilha):
    linhas, avisos = mobills.ler(planilha)
    assert len(linhas) == 8
    assert len({ln.origem_id for ln in linhas}) == 8      # PERIM repetido ganha ids distintos
    assert any("linha 9" in a for a in avisos)


def test_importa_com_mapa_tags_e_parcelas(con, planilha):
    rel, texto = mobills.executar(con, planilha)
    assert rel.importadas == 8 and rel.por_tipo["transferencia"] == 1
    assert rel.ignoradas_relatorio == 1 and rel.parceladas == 1

    cat = lambda desc: con.execute(  # noqa: E731
        "SELECT c.nome, p.nome AS mae FROM transacao t JOIN categoria c ON c.id = t.categoria_id "
        "LEFT JOIN categoria p ON p.id = c.pai_id WHERE t.descricao = ? LIMIT 1", (desc,)).fetchone()
    assert tuple(cat("PERIM")) == ("Mercado", "Alimentação")
    assert tuple(cat("Quilão")) == ("Hortifruti", "Alimentação")
    assert tuple(cat("Tela gatil")) == ("Outras despesas", None)
    assert tuple(cat("Rendimento")) == ("Rendimentos", None)
    tag = con.execute("SELECT g.nome FROM transacao t JOIN transacao_tag x ON x.transacao_id = t.id "
                      "JOIN tag g ON g.id = x.tag_id WHERE t.descricao = 'Tela gatil'").fetchone()
    assert tag["nome"] == "CERCO FELINO"

    geladeira = con.execute("SELECT * FROM transacao WHERE descricao LIKE 'Geladeira%'").fetchone()
    assert (geladeira["parcela"], geladeira["total_parcelas"], geladeira["ignorar"]) == (2, 12, 1)

    invest = con.execute("SELECT * FROM conta WHERE nome LIKE 'C6 Invest%'").fetchone()
    assert invest["tipo"] == "investimento" and invest["compoe_saldo_disponivel"] == 0
    assert invest["data_saldo_inicial"] == "2026-10-01"

    from app.services.painel import saldos_contas
    saldos = {c["nome"]: c["saldo_atual"] for c in saldos_contas(con)}
    assert saldos["2 - Itaú"] == 500000 - 100000
    assert saldos["1 - C6 Bank 1118"] == -12345 * 2 - 5010 - 30000 + 100000
    assert "DE-PARA" in texto


def test_reimportar_nao_duplica(con, planilha):
    mobills.executar(con, planilha)
    rel, _ = mobills.executar(con, planilha)
    assert rel.importadas == 0 and rel.ja_existiam == 8
    assert con.execute("SELECT COUNT(*) FROM transacao").fetchone()[0] == 9   # 7 + 2 pernas


def test_simulacao_nao_grava(con, planilha):
    rel, texto = mobills.executar(con, planilha, simular=True)
    assert rel.importadas == 8 and texto.startswith("SIMULAÇÃO")
    assert con.execute("SELECT COUNT(*) FROM transacao").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM conta").fetchone()[0] == 1       # só a Carteira


def test_reajuste_de_saldo(con, planilha):
    mobills.executar(con, planilha)
    itau = con.execute("SELECT id FROM conta WHERE nome = '2 - Itaú'").fetchone()["id"]
    r = transacoes.reajustar_saldo(con, itau, 123456, date(2026, 10, 31))
    assert r["saldo_anterior"] == 400000 and r["diferenca"] == 123456 - 400000
    r2 = transacoes.reajustar_saldo(con, itau, 123456, date(2026, 10, 31))
    assert r2["diferenca"] == 0 and r2["transacao_id"] is None


def test_api_reajuste(cliente):
    conta = cliente.post("/api/contas", json={"nome": "Teste", "data_saldo_inicial": "2026-01-01"}).json()
    r = cliente.post(f"/api/contas/{conta['id']}/reajuste", json={"saldo_centavos": -500, "data": "2026-10-31"})
    assert r.status_code == 201 and r.json()["diferenca"] == -500
    assert cliente.post("/api/contas/999/reajuste", json={"saldo_centavos": 1}).status_code == 404


def test_conversoes_viram_transferencia_ajuste_e_pulam_a_outra_perna(con, planilha):
    mapa = mobills.carregar_mapa()
    mapa["conversoes"] = [
        {"data": "2026-10-06", "conta": "C6 Invest - CDB 102% CDI", "valor": 10.5, "vira": "ajuste"},
        {"data": "2026-10-02", "conta": "1 - C6 Bank 1118", "valor": -123.45, "vira": "transferencia",
         "destino": "C6 Invest - CDB 102% CDI", "valor_transferido": 120.00,
         "diferenca_categoria": "Taxas e serviços > IR"},
        {"data": "2026-10-03", "conta": "1 - C6 Bank 1118", "valor": -50.1, "vira": "pular"},
    ]
    rel, texto = mobills.executar(con, planilha, mapa)
    assert rel.por_tipo["ajuste"] == 1 and rel.por_tipo["pulada"] == 1
    # As duas linhas PERIM idênticas casam com a regra: viram 2 transferências + 2 diferenças.
    assert rel.por_tipo["transferencia"] == 3
    dif = con.execute("SELECT valor_centavos, c.nome FROM transacao t JOIN categoria c "
                      "ON c.id = t.categoria_id WHERE descricao LIKE '%(diferença)'").fetchall()
    assert [tuple(d) for d in dif] == [(345, "IR"), (345, "IR")]
    assert "CONVERTIDAS" in texto
    # Reimportar não duplica nada.
    rel2, _ = mobills.executar(con, planilha, mapa)
    assert rel2.importadas == 0


def test_reajuste_futuro_vira_ajuste(con, tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Receitas e Despesas"
    ws.append(["Data", "Descrição", "Valor", "Conta", "Situação", "Categoria", "Subcategoria", "Tags"])
    ws.append(["01/05/2025", "Acerto antigo", 10.0, "X", "Paga", "Reajuste", None, ""])
    ws.append(["05/11/2026", "Acerto novo", -7.0, "X", "Paga", "Reajuste", None, ""])
    arq = tmp_path / "r.xlsx"
    wb.save(arq)
    rel, _ = mobills.executar(con, arq)
    assert rel.por_tipo == {"receita": 1, "ajuste": 1}
