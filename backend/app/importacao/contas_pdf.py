"""Lê os PDFs das contas da casa e grava a ficha de cada fatura no lançamento já pago.

Uso (Windows): scripts\\importar_contas.bat  (lê D:\\...\\Contas\\2026; simula, pede S, grava)

Sem API paga: o texto sai do próprio PDF (pypdf). Hoje lê a EDP Escelsa; os outros
emissores entram um a um, cada um com o seu leitor.

Ponte da conta de luz (o que o leitor separa):
    total = energia (consumo − créditos da Solar) + bandeira + iluminação pública
            + serviços de terceiros + multa/juros
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .. import db, seed
from ..services import contas_casa

MESES = {m: i for i, m in enumerate(
    ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"), 1)}
DINHEIRO = r"(\d{1,3}(?:\.\d{3})*,\d{2})"
NUM = r"(\d+(?:\.\d{3})*,\d+)"


def _centavos(txt: str) -> int:
    return int(txt.replace(".", "").replace(",", ""))


def _num(txt: str) -> float:
    return float(txt.replace(".", "").replace(",", "."))


def texto_do_pdf(caminho: Path, senha: str | None = None) -> str:
    """Texto do PDF mantendo o layout das colunas. Erro claro se pedir senha."""
    from pypdf import PdfReader
    r = PdfReader(str(caminho))
    if r.is_encrypted and not r.decrypt(senha or ""):
        raise PermissionError(f"{caminho.name}: PDF protegido por senha")
    return "\n".join(p.extract_text(extraction_mode="layout") for p in r.pages)


@dataclass
class Fatura:
    emissor: str
    tipo: str
    referencia: str                 # AAAA-MM do consumo
    vencimento: str                 # AAAA-MM-DD
    total_centavos: int
    ficha: dict = field(default_factory=dict)
    historico: list[tuple[str, float, int]] = field(default_factory=list)   # (AAAA-MM, consumo, valor)
    arquivo: str = ""


def ler_escelsa(t: str) -> Fatura:
    """Fatura da EDP Espírito Santo (Escelsa). Layout de 2025-2026."""
    m = re.search(r"\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)/(\d{4})\s+(\d{2})/(\d{2})/(\d{4})"
                  r"\s+(?:R\$\s*)?" + DINHEIRO, t)
    if not m:
        raise ValueError("não achei mês de referência, vencimento e total")
    mes, ano, dd, mm, aaaa, total = m.groups()
    consumo = re.search(r"TUSD - Energia Ativa Fornecida\s+kWh\s+" + NUM, t)
    # Créditos da Solar abatidos (uma linha por lote de crédito; a TE repete os mesmos kWh).
    injetado = sum(_num(q) for q in re.findall(r"TUSD - En\. At\. Inj\.[^\n]*?kWh\s+" + NUM + "-", t))
    # Bandeira: valor líquido (adicional − parte abatida pelos créditos) e a cor predominante.
    bandeira_valor, kwh_por_cor = 0, {}
    for cor, inj, qtd, _preco, valor, neg in re.findall(
            r"Adicional Bandeira (Amarela|Vermelha|Escassez\w*)( Energia Inj\.)?\s+kWh\s+" + NUM + r"-?\s+"
            + NUM + r"\s+" + DINHEIRO + r"(-?)", t):
        bandeira_valor += -_centavos(valor) if neg else _centavos(valor)
        if not inj:
            kwh_por_cor[cor] = kwh_por_cor.get(cor, 0) + _num(qtd)
    if kwh_por_cor:
        cor = max(kwh_por_cor, key=kwh_por_cor.get)
        bandeira = {"Amarela": "amarela", "Vermelha": "vermelha2" if re.search(r"(?i)patamar 2|PTM 2", t)
                    else "vermelha1"}.get(cor, "escassez")
    else:
        bandeira = "verde"

    def linha_fixa(rotulo: str) -> int | None:
        achou = re.search(rotulo + r"[^\n]*?" + DINHEIRO + r"\s+0,00000000", t)
        return _centavos(achou.group(1)) if achou else None

    multa = sum(_centavos(v) for v in re.findall(
        r"(?:Multa|Juros|Atualiza\w+ Monet\w+)[^\n]*?" + DINHEIRO + r"\s+0,00000000", t))
    historico = []
    for mm2, aa2, kwh, valor in re.findall(r"^\s*(\d{2})/(\d{2})\s+(\d+)\s+" + DINHEIRO + r"\s*$", t, re.M):
        historico.append((f"20{aa2}-{mm2}", float(kwh), _centavos(valor)))
    ref = f"{ano}-{MESES[mes]:02d}"
    return Fatura(
        emissor="EDP Escelsa", tipo="energia", referencia=ref, vencimento=f"{aaaa}-{mm}-{dd}",
        total_centavos=_centavos(total), historico=historico,
        ficha={"tipo": "energia", "referencia": ref,
               "consumo": _num(consumo.group(1)) if consumo else None,
               "kwh_compensado": round(injetado, 4) or None, "bandeira": bandeira,
               "bandeira_centavos": bandeira_valor or None,
               "cip_centavos": linha_fixa(r"Ilum\. P[úu]blica"),
               "terceiros_centavos": linha_fixa(r"Seguro"), "multa_juros_centavos": multa or None})


LEITORES = [  # (como reconhecer o emissor no texto, leitor)
    (re.compile(r"EDP ES DISTRIB DE ENERGIA"), ler_escelsa),
]
# Descrição do lançamento no app, por emissor (o Mobills usou nomes variados).
PADROES_LANCAMENTO = {"EDP Escelsa": "%ESCELSA%"}


def ler(caminho: Path, senha: str | None = None) -> Fatura | None:
    t = texto_do_pdf(caminho, senha)
    for reconhece, leitor in LEITORES:
        if reconhece.search(t):
            f = leitor(t)
            f.arquivo = caminho.name
            return f
    return None


def achar_lancamento(con: sqlite3.Connection, f: Fatura) -> sqlite3.Row | None:
    """O pagamento desta fatura: mesmo emissor e valor, perto do vencimento (atraso de até 40 dias)."""
    venc = date.fromisoformat(f.vencimento)
    return con.execute(
        """SELECT * FROM transacao
           WHERE tipo IN ('despesa', 'despesa_cartao') AND upper(descricao) LIKE ?
             AND valor_centavos = ? AND date(COALESCE(vencimento, data)) BETWEEN ? AND ?
           ORDER BY abs(julianday(COALESCE(vencimento, data)) - julianday(?)) LIMIT 1""",
        (PADROES_LANCAMENTO[f.emissor], f.total_centavos, (venc - timedelta(days=10)).isoformat(),
         (venc + timedelta(days=40)).isoformat(), f.vencimento)).fetchone()


def executar(con: sqlite3.Connection, pasta: Path, simular: bool = True,
             senhas: dict[str, str] | None = None) -> tuple[dict, str]:
    linhas, cont = [], {"lidas": 0, "gravadas": 0, "sem_lancamento": 0, "ignoradas": 0, "com_senha": 0}
    historico: dict[tuple[str, str], tuple[float, int]] = {}
    for pdf in sorted(pasta.glob("*.pdf")):
        try:
            f = ler(pdf, (senhas or {}).get(pdf.name))
        except PermissionError:
            cont["com_senha"] += 1
            linhas.append(f"  🔒 {pdf.name}: protegido por senha (fica para depois)")
            continue
        except Exception as e:  # um PDF ruim não pode parar a carga dos outros
            cont["ignoradas"] += 1
            linhas.append(f"  ⚠ {pdf.name}: não consegui ler ({e})")
            continue
        if f is None:
            cont["ignoradas"] += 1
            continue
        cont["lidas"] += 1
        for ref, consumo, valor in f.historico:
            historico[(f.tipo, ref)] = (consumo, valor)
        t = achar_lancamento(con, f)
        fc = f.ficha
        resumo = (f"{f.emissor:12} {f.referencia}  vence {f.vencimento[8:]}/{f.vencimento[5:7]}  "
                  f"R$ {f.total_centavos / 100:>8.2f}  {fc.get('consumo') or 0:>5.0f} kWh  "
                  f"Solar {fc.get('kwh_compensado') or 0:>5.0f} kWh  {fc.get('bandeira') or '':9}  "
                  f"ilum. R$ {(fc.get('cip_centavos') or 0) / 100:.2f}")
        if t is None:
            cont["sem_lancamento"] += 1
            linhas.append(f"  ✗ {resumo}  → sem lançamento de mesmo valor no app")
            continue
        cont["gravadas"] += 1
        linhas.append(f"  ✓ {resumo}  → lançamento de {t['data'][8:]}/{t['data'][5:7]}")
        if not simular:
            contas_casa.gravar(con, t["id"], {**fc, "arquivo": f.arquivo})
            if not t["vencimento"] and t["pago"] and t["data"] != f.vencimento:
                with con:
                    con.execute("UPDATE transacao SET vencimento = ? WHERE id = ?", (f.vencimento, t["id"]))
    if not simular and historico:
        with con:
            con.executemany(
                "INSERT INTO conta_historico (tipo, referencia, consumo, valor_centavos) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (tipo, referencia) DO UPDATE SET consumo = excluded.consumo, "
                "valor_centavos = excluded.valor_centavos",
                [(tipo, ref, c, v) for (tipo, ref), (c, v) in historico.items()])
    cab = "SIMULAÇÃO (nada gravado)" if simular else "GRAVADO"
    texto = "\n".join([
        f"Contas da casa — leitura dos PDFs em {pasta} — {cab}", "",
        *linhas, "",
        f"Faturas lidas: {cont['lidas']} · fichas {'a gravar' if simular else 'gravadas'}: {cont['gravadas']} · "
        f"sem lançamento: {cont['sem_lancamento']} · com senha: {cont['com_senha']} · "
        f"outros emissores (ainda sem leitor): {cont['ignoradas']}",
        f"Histórico de consumo (13 meses por fatura): {len(historico)} meses",
    ])
    return cont, texto


def main(argv: list[str] | None = None) -> int:
    from ..config import carregar
    from ..services import backup

    p = argparse.ArgumentParser(description="Lê os PDFs das contas da casa e grava as fichas.")
    p.add_argument("pasta", type=Path)
    p.add_argument("--simular", action="store_true", help="não grava; só mostra o relatório")
    p.add_argument("--saida", type=Path, help="salva o relatório neste arquivo .txt")
    a = p.parse_args(argv)
    cfg = carregar()
    con = db.conectar(cfg.arquivo_banco)
    db.migrar(con)
    seed.popular(con)
    if not a.simular:
        print(f"Backup antes da leitura: {backup.fazer(con, cfg.pasta_backup)}")
    _, texto = executar(con, a.pasta, simular=a.simular)
    print(texto)
    if a.saida:
        a.saida.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
