"""Exportação do relatório (Fase 4) para Excel (.xlsx)."""
import io

from openpyxl import load_workbook

from app.services import relatorio_export


def _dados_exemplo():
    return {
        "ini": "2026-09-01", "fim": "2026-10-31",
        "meses": [
            {"competencia": "2026-09", "receitas": 500000, "despesas": 30000, "resultado": 470000},
            {"competencia": "2026-10", "receitas": 0, "despesas": 8000, "resultado": -8000},
        ],
        "por_categoria": [
            {"categoria_id": 1, "categoria": "Alimentação", "cor": "#fff", "total": 30000,
             "pct": 78.9, "serie": [30000, 0]},
            {"categoria_id": 2, "categoria": "Saúde", "cor": "#fff", "total": 8000,
             "pct": 21.1, "serie": [0, 8000]},
        ],
        "por_tag": [{"tag": "CERCO FELINO", "cor": "#fff", "total": 20000, "lancamentos": 1}],
        "resumo": {
            "meses": 2, "receitas": 500000, "despesas": 38000, "resultado": 462000,
            "media_receitas_mes": 250000, "media_despesas_mes": 19000,
            "taxa_poupanca_pct": 92.4, "mes_maior_despesa": "2026-09",
        },
    }


def test_montar_xlsx_abas_e_valores():
    conteudo = relatorio_export.montar_xlsx(_dados_exemplo())
    wb = load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == ["Resumo", "Mês a mês", "Por categoria", "Por projeto"]

    # Mês a mês: valores em REAIS (não centavos) e linha de total.
    mm = wb["Mês a mês"]
    assert mm["A1"].value == "Mês" and mm["A2"].value == "set/26"
    assert mm["B2"].value == 5000.0 and mm["C2"].value == 300.0 and mm["D2"].value == 4700.0
    # Número com separador de milhar, SEM "R$" (pedido do João).
    assert "R$" not in mm["B2"].number_format and mm["B2"].number_format == "#,##0.00"
    total = mm[mm.max_row]
    assert total[0].value == "Total" and total[2].value == 380.0

    # Por categoria: colunas de total, % e um mês.
    cat = wb["Por categoria"]
    assert cat["A1"].value == "Categoria" and cat["A2"].value == "Alimentação"
    assert cat["B2"].value == 300.0 and cat["C2"].value == 78.9

    # Por projeto (tag).
    proj = wb["Por projeto"]
    assert proj["A2"].value == "CERCO FELINO" and proj["B2"].value == 200.0


def test_sem_tags_omite_aba_projeto():
    d = _dados_exemplo()
    d["por_tag"] = []
    wb = load_workbook(io.BytesIO(relatorio_export.montar_xlsx(d)))
    assert "Por projeto" not in wb.sheetnames


def test_endpoint_export_xlsx(cliente):
    r = cliente.get("/api/relatorios/export.xlsx?meses=3")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert ".xlsx" in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert "Resumo" in wb.sheetnames and "Mês a mês" in wb.sheetnames
