"""Exporta o relatório (Fase 4) para uma planilha Excel (.xlsx).

Recebe o mesmo dicionário que `relatorios.periodo`/`atalho` devolvem (valores em
centavos) e monta um arquivo com quatro abas: Resumo, Mês a mês, Por categoria e
Por projeto. Os valores vão como NÚMERO em reais (não texto), com formato de moeda,
para que dê para somar, filtrar e cruzar na própria planilha.
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MOEDA = 'R$ #,##0.00'          # em Excel pt-BR aparece como R$ 1.234,56
PCT = '0.0"%"'

_NEGRITO = Font(bold=True)
_CAB_FILL = PatternFill("solid", fgColor="E8EAF0")
_DIR = Alignment(horizontal="right")


def _rotulo(comp: str) -> str:
    """'2026-11' -> 'nov/26'."""
    return f"{MES[int(comp[5:7]) - 1]}/{comp[2:4]}"


def _reais(centavos: int | None) -> float:
    return round((centavos or 0) / 100, 2)


def _cabecalho(ws: Worksheet, titulos: list[str]) -> None:
    ws.append(titulos)
    for c in ws[ws.max_row]:
        c.font = _NEGRITO
        c.fill = _CAB_FILL


def _largura(ws: Worksheet, larguras: list[int]) -> None:
    for i, w in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def montar_xlsx(d: dict) -> bytes:
    resumo = d["resumo"]
    meses = d["meses"]
    wb = Workbook()

    # --- Resumo ---------------------------------------------------------------
    ws = wb.active
    ws.title = "Resumo"
    ws.append(["Relatório de finanças"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["Período", f"{d['ini']} a {d['fim']}"])
    ws.append(["Meses", resumo["meses"]])
    ws.append([])
    linhas = [
        ("Receitas", _reais(resumo["receitas"]), f'{_reais(resumo["media_receitas_mes"])}'),
        ("Despesas", _reais(resumo["despesas"]), f'{_reais(resumo["media_despesas_mes"])}'),
        ("Resultado", _reais(resumo["resultado"]), ""),
    ]
    _cabecalho(ws, ["", "Total", "Média/mês"])
    for nome, total, media in linhas:
        ws.append([nome, total, float(media) if media else None])
        ws.cell(ws.max_row, 2).number_format = MOEDA
        if media:
            ws.cell(ws.max_row, 3).number_format = MOEDA
    ws.append([])
    tp = resumo["taxa_poupanca_pct"]
    ws.append(["Taxa de poupança", tp if tp is not None else "—"])
    if tp is not None:
        ws.cell(ws.max_row, 2).number_format = PCT
    mmd = resumo["mes_maior_despesa"]
    ws.append(["Mês de maior despesa", _rotulo(mmd) if mmd else "—"])
    _largura(ws, [24, 16, 14])

    # --- Mês a mês ------------------------------------------------------------
    ws = wb.create_sheet("Mês a mês")
    _cabecalho(ws, ["Mês", "Receitas", "Despesas", "Resultado"])
    for m in meses:
        ws.append([_rotulo(m["competencia"]), _reais(m["receitas"]),
                   _reais(m["despesas"]), _reais(m["resultado"])])
        for col in (2, 3, 4):
            ws.cell(ws.max_row, col).number_format = MOEDA
    # Linha de totais
    ws.append(["Total", _reais(resumo["receitas"]), _reais(resumo["despesas"]),
               _reais(resumo["resultado"])])
    for c in ws[ws.max_row]:
        c.font = _NEGRITO
    for col in (2, 3, 4):
        ws.cell(ws.max_row, col).number_format = MOEDA
    ws.freeze_panes = "A2"
    _largura(ws, [12, 16, 16, 16])

    # --- Por categoria --------------------------------------------------------
    ws = wb.create_sheet("Por categoria")
    rotulos_mes = [_rotulo(m["competencia"]) for m in meses]
    _cabecalho(ws, ["Categoria", "Total", "% das despesas", "Média/mês", *rotulos_mes])
    n = max(resumo["meses"], 1)
    for c in d["por_categoria"]:
        linha = [c["categoria"], _reais(c["total"]), c["pct"],
                 _reais(round(c["total"] / n)), *[_reais(v) for v in c["serie"]]]
        ws.append(linha)
        r = ws.max_row
        ws.cell(r, 2).number_format = MOEDA
        ws.cell(r, 3).number_format = PCT
        for col in range(4, 5 + len(rotulos_mes)):
            ws.cell(r, col).number_format = MOEDA
    ws.freeze_panes = "B2"
    _largura(ws, [22, 14, 14, 12] + [11] * len(rotulos_mes))

    # --- Por projeto (tags) ---------------------------------------------------
    if d["por_tag"]:
        ws = wb.create_sheet("Por projeto")
        _cabecalho(ws, ["Projeto (etiqueta)", "Total", "Lançamentos"])
        for t in d["por_tag"]:
            ws.append([t["tag"], _reais(t["total"]), t["lancamentos"]])
            ws.cell(ws.max_row, 2).number_format = MOEDA
        ws.freeze_panes = "A2"
        _largura(ws, [26, 16, 14])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
