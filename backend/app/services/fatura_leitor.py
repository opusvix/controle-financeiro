"""Leitura do arquivo da fatura do cartão (o extrato que o banco/app exporta).

Hoje lê o CSV do C6. Cada banco tem seu formato, então a leitura é por banco:
`ler(nome_arquivo, conteudo)` escolhe o leitor certo e devolve sempre o mesmo
formato normalizado, para a conciliação não precisar saber de onde veio.

Valores em centavos, COM SINAL do ponto de vista da fatura:
  compra = positivo; crédito/estorno = negativo.
A linha de pagamento da fatura (ex.: "Inclusao de Pagamento") NÃO é compra:
sai numa lista à parte, porque ela vira "Pagamento de fatura" na conta, não um
item da fatura.
"""
from __future__ import annotations

import csv
import io
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


def ler(nome_arquivo: str, conteudo: bytes) -> dict:
    """Escolhe o leitor pelo arquivo. Por enquanto: C6 em CSV."""
    nome = (nome_arquivo or "").lower()
    if nome.endswith(".csv"):
        return ler_c6_csv(conteudo)
    if nome.endswith(".pdf"):
        raise FaturaInvalida("Fatura em PDF ainda não é lida automaticamente "
                             "(em breve, por banco). Por ora, use o CSV do C6.")
    # Tenta CSV mesmo sem extensão conhecida.
    return ler_c6_csv(conteudo)
