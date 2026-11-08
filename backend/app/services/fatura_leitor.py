"""Leitura do arquivo da fatura do cartão (o extrato que o banco/app exporta).

Lê o CSV do C6 e o PDF do Banco do Brasil e do Mercado Pago. Cada banco tem seu
formato, então a leitura é por banco: `ler(nome_arquivo, conteudo, competencia)`
escolhe o leitor certo (pela extensão e, no PDF, pelo nome do banco no texto) e
devolve sempre o mesmo formato normalizado, para a conciliação não precisar saber
de onde veio.

Valores em centavos, COM SINAL do ponto de vista da fatura:
  compra = positivo; crédito/estorno = negativo.
A linha de pagamento da fatura (ex.: "Inclusao de Pagamento") NÃO é compra:
sai numa lista à parte, porque ela vira "Pagamento de fatura" na conta, não um
item da fatura.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import datetime


class FaturaInvalida(ValueError):
    """Arquivo que não dá para ler como fatura (vira HTTP 422)."""


def _sem_acento(s: str) -> str:
    base = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in base if not unicodedata.combining(c)).strip().casefold()


def _centavos(txt: str) -> int | None:
    """Aceita '367.66', '-2010.66' e também '1.234,56' (formato brasileiro)."""
    t = (txt or "").strip().replace("R$", "").replace(" ", "")
    if not t:
        return None
    if "," in t and "." in t:          # 1.234,56 -> milhar '.', decimal ','
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:                     # 1234,56 -> decimal ','
        t = t.replace(",", ".")
    try:
        return round(float(t) * 100)
    except ValueError:
        return None


def _parcela(txt: str) -> tuple[int | None, int | None]:
    t = (txt or "").strip()
    if "/" in t:
        a, _, b = t.partition("/")
        try:
            return int(a), int(b)
        except ValueError:
            return None, None
    return None, None


def ler_c6_csv(conteudo: bytes) -> dict:
    texto = conteudo.decode("utf-8-sig", errors="replace")
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    campos = {_sem_acento(k): k for k in (leitor.fieldnames or [])}
    obrig = ["data de compra", "descricao", "valor (em r$)"]
    if not all(c in campos for c in obrig):
        raise FaturaInvalida(
            "Não reconheci as colunas da fatura do C6. Esperava 'Data de Compra', "
            "'Descrição' e 'Valor (em R$)' separadas por ponto e vírgula.")

    def col(row: dict, nome: str) -> str:
        chave = campos.get(_sem_acento(nome))
        return (row.get(chave) or "").strip() if chave else ""

    linhas: list[dict] = []
    pagamentos: list[dict] = []
    for row in leitor:
        dstr, vstr = col(row, "Data de Compra"), col(row, "Valor (em R$)")
        centavos = _centavos(vstr)
        if not dstr or centavos is None:
            continue
        try:
            data = datetime.strptime(dstr, "%d/%m/%Y").date().isoformat()
        except ValueError:
            continue
        descricao = col(row, "Descrição") or "(sem descrição)"
        pnum, ptot = _parcela(col(row, "Parcela"))
        linha = {"data": data, "descricao": descricao, "valor_centavos": centavos,
                 "parcela": pnum, "total_parcelas": ptot,
                 "final": col(row, "Final do Cartão"), "categoria_texto": col(row, "Categoria")}
        # Pagamento da fatura: negativo e com cara de pagamento -> fora dos itens.
        if centavos < 0 and "pagamento" in _sem_acento(descricao):
            pagamentos.append(linha)
        else:
            linhas.append(linha)
    if not linhas and not pagamentos:
        raise FaturaInvalida("O arquivo parece uma fatura do C6, mas nenhuma linha "
                             "tinha data e valor válidos.")
    return {"banco": "C6", "linhas": linhas, "pagamentos": pagamentos,
            "total_compras": sum(l["valor_centavos"] for l in linhas),
            "total_pagamentos": sum(p["valor_centavos"] for p in pagamentos)}


# --- Leitura de PDF (Banco do Brasil e Mercado Pago) -------------------------
#
# O texto sai do próprio PDF (pypdf), sem API paga. Cada linha de lançamento tem
# a forma  "DD/MM  descrição ...  R$ valor". A data da compra NÃO traz o ano (a
# parcela 8/12 pode ser de meses atrás), então o ano é inferido da competência:
# se o mês da compra vier depois do mês do vencimento, foi no ano anterior.

# data no começo da linha (DD/MM, mas não DD/MM/AAAA) e valor "R$ ..." no fim.
_LINHA_PDF = re.compile(r"^\s*(\d{2})/(\d{2})(?!/)\s+(.*?)\s+R\$\s*(-?[\d.,]+)\s*$")
# "PARC 08/12" (BB) e "Parcela 2 de 2" (Mercado Pago), num padrão só.
_PARCELA_PDF = re.compile(r"\bPARC(?:ELA)?\s*(\d{1,2})\s*(?:/|de)\s*(\d{1,2})\b", re.I)
# Linha de pagamento da fatura (não é compra).
_PAGAMENTO_PDF = re.compile(r"\b(pgto|pagto|pagamento)\b", re.I)


def _texto_pdf(conteudo: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:                                   # pragma: no cover
        raise FaturaInvalida("Para ler faturas em PDF é preciso a biblioteca pypdf.") from e
    try:
        leitor = PdfReader(io.BytesIO(conteudo))
        return "\n".join(p.extract_text() or "" for p in leitor.pages)
    except Exception as e:
        raise FaturaInvalida("Não consegui abrir este PDF de fatura.") from e


def _ano_da_compra(mes: int, competencia: str | None) -> int:
    """Ano da compra a partir da competência AAAA-MM do vencimento."""
    hoje = datetime.now()
    venc_ano, venc_mes = hoje.year, hoje.month
    if competencia:
        try:
            venc_ano, venc_mes = int(competencia[:4]), int(competencia[5:7])
        except (ValueError, IndexError):
            pass
    return venc_ano - 1 if mes > venc_mes else venc_ano


def _linhas_de_texto(texto: str, competencia: str | None) -> tuple[list[dict], list[dict]]:
    """Extrai (linhas de compra, pagamentos) de um texto de fatura em PDF."""
    linhas: list[dict] = []
    pagamentos: list[dict] = []
    for bruta in texto.splitlines():
        m = _LINHA_PDF.match(bruta)
        if not m:
            continue
        dd, mm, desc, vstr = m.groups()
        centavos = _centavos(vstr)
        if centavos is None:
            continue
        try:
            dia, mes = int(dd), int(mm)
            data = datetime(_ano_da_compra(mes, competencia), mes, dia).date().isoformat()
        except ValueError:
            continue
        pnum = ptot = None
        pm = _PARCELA_PDF.search(desc)
        if pm:
            pnum, ptot = int(pm.group(1)), int(pm.group(2))
            desc = _PARCELA_PDF.sub("", desc)
        desc = re.sub(r"\s+BR\b", "", desc)          # país no fim da linha (BB)
        desc = re.sub(r"\s{2,}", " ", desc).strip() or "(sem descrição)"
        eh_pagamento = bool(_PAGAMENTO_PDF.search(desc))
        if eh_pagamento:
            centavos = -abs(centavos)                # pagamento sempre abate a fatura
        linha = {"data": data, "descricao": desc, "valor_centavos": centavos,
                 "parcela": pnum, "total_parcelas": ptot, "final": "", "categoria_texto": ""}
        (pagamentos if eh_pagamento else linhas).append(linha)
    return linhas, pagamentos


def _banco_do_pdf(texto: str) -> str | None:
    t = _sem_acento(texto)
    if "mercado pago" in t or "mercadopago" in t:
        return "Mercado Pago"
    if "ourocard" in t or "banco do brasil" in t or "bb.com.br" in t:
        return "Banco do Brasil"
    return None


def ler(nome_arquivo: str, conteudo: bytes, competencia: str | None = None) -> dict:
    """Escolhe o leitor pelo arquivo: CSV do C6 ou PDF (BB / Mercado Pago)."""
    nome = (nome_arquivo or "").lower()
    if nome.endswith(".pdf"):
        texto = _texto_pdf(conteudo)
        banco = _banco_do_pdf(texto)
        if banco is None:
            raise FaturaInvalida(
                "Não reconheci de qual banco é esta fatura em PDF. Hoje leio "
                "PDF do Banco do Brasil e do Mercado Pago; para o C6, use o CSV.")
        linhas, pagamentos = _linhas_de_texto(texto, competencia)
        if not linhas and not pagamentos:
            raise FaturaInvalida(
                f"Reconheci a fatura como {banco}, mas não encontrei lançamentos "
                "(data + valor). O PDF pode ser uma imagem escaneada.")
        return {"banco": banco, "linhas": linhas, "pagamentos": pagamentos,
                "total_compras": sum(l["valor_centavos"] for l in linhas),
                "total_pagamentos": sum(p["valor_centavos"] for p in pagamentos)}
    if nome.endswith(".csv"):
        return ler_c6_csv(conteudo)
    # Tenta CSV mesmo sem extensão conhecida.
    return ler_c6_csv(conteudo)
