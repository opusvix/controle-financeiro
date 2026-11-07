"""Conciliação da FATURA do cartão: leitura do CSV do C6 e cruzamento por valor."""
from app.services import fatura_leitor

# Cabeçalho e formato reais do export do C6 (separador ';', decimal com ponto).
CABECALHO = ("Data de Compra;Nome no Cartão;Final do Cartão;Categoria;Descrição;"
             "Parcela;Valor (em US$);Cotação (em R$);Valor (em R$)")


def _csv(*linhas: str) -> bytes:
    return ("\r\n".join([CABECALHO, *linhas]) + "\r\n").encode("utf-8")


FATURA = _csv(
    "05/06/2026;MAURICIO S BARROS;1118;Automotivo;PNEUS MAURI;5/6;0;0;367.66",
    "16/05/2026;MAURICIO S BARROS;3289;Varejo;AMAZON MARKETPLACE;6/6;0;0;36.21",
    "27/10/2026;MAURICIO S BARROS;1118;Mercearia;MP *MARLENE;Única;0;0;20.50",
    "23/10/2026;MAURICIO S BARROS;1118;Associação;SUPERMERCADO PERIM;Única;0;0;129.75",
    "10/10/2026;MAURICIO S BARROS;1118;-;Inclusao de Pagamento;Única;0;0;-2010.66",
)


def test_ler_c6_separa_pagamento_e_normaliza():
    lido = fatura_leitor.ler("C6-Fatura_2026-11-10.csv", FATURA)
    assert lido["banco"] == "C6"
    assert len(lido["linhas"]) == 4                       # a linha de pagamento sai dos itens
    assert len(lido["pagamentos"]) == 1
    assert lido["pagamentos"][0]["valor_centavos"] == -201066
    p = {l["descricao"]: l for l in lido["linhas"]}
    assert p["PNEUS MAURI"]["valor_centavos"] == 36766
    assert p["PNEUS MAURI"]["data"] == "2026-06-05"        # data da COMPRA, não da fatura
    assert (p["PNEUS MAURI"]["parcela"], p["PNEUS MAURI"]["total_parcelas"]) == (5, 6)
    assert lido["total_compras"] == 36766 + 3621 + 2050 + 12975


def test_pdf_ainda_nao_lido():
    import pytest
    with pytest.raises(fatura_leitor.FaturaInvalida):
        fatura_leitor.ler("fatura.pdf", b"%PDF-1.4 ...")


def _cartao(cliente):
    return cliente.post("/api/cartoes", json={"nome": "C6 MAU", "bandeira": "Mastercard",
        "final": "1118", "limite_centavos": 900000, "dia_fechamento": 28,
        "dia_vencimento": 10}).json()["id"]


def _compra(cliente, cartao, desc, valor, data="2026-10-20"):
    return cliente.post("/api/transacoes", json={"tipo": "despesa_cartao", "descricao": desc,
        "valor_centavos": valor, "data": data, "cartao_id": cartao, "parcelas": 1,
        "fatura_competencia": "2026-11"}).json()[0]


def _analisar(cliente, cartao):
    return cliente.post("/api/conciliacao/fatura/analisar",
        files={"arquivo": ("C6-Fatura_2026-11-10.csv", FATURA, "text/csv")},
        data={"cartao_id": cartao, "competencia": "2026-11"})


def test_quatro_baldes_por_valor(cliente):
    cartao = _cartao(cliente)
    _compra(cliente, cartao, "Pneus Mauri 6x (5/6)", 36766)   # casa exato
    _compra(cliente, cartao, "Amazon (6/6)", 3621)            # casa exato
    _compra(cliente, cartao, "Barraca da Marlene", 2000)      # diverge (20,00 vs 20,50)
    _compra(cliente, cartao, "Só no app", 9999)               # não vem na fatura

    r = _analisar(cliente, cartao).json()
    assert r["resumo"] == {"linhas_fatura": 4, "casados": 2, "divergencias": 1,
                           "so_fatura": 1, "so_app": 1, "pagamentos": 1}
    assert r["so_fatura"][0]["descricao"] == "SUPERMERCADO PERIM"
    assert r["totais"]["app"] == 36766 + 3621 + 2000 + 9999
    assert r["totais"]["extrato"] == 36766 + 3621 + 2050 + 12975
    assert r["totais"]["diferenca"] == r["totais"]["app"] - r["totais"]["extrato"]


def test_aplicar_lanca_confere_e_grava_total(cliente):
    cartao = _cartao(cliente)
    _compra(cliente, cartao, "Pneus Mauri 6x (5/6)", 36766)
    _compra(cliente, cartao, "Amazon (6/6)", 3621)
    r = _analisar(cliente, cartao).json()
    casar = [c["app"]["id"] for c in r["casados"]]
    criar = [{"data": b["data"], "valor_centavos": b["valor_centavos"], "descricao": b["descricao"]}
             for b in r["so_fatura"]]
    saida = cliente.post("/api/conciliacao/fatura/aplicar", json={
        "cartao_id": cartao, "competencia": "2026-11", "conferir_ids": casar,
        "criar": criar, "valor_banco": r["totais"]["extrato"]}).json()
    assert saida["conferidos"] == 2 and saida["criados"] == 2 and saida["valor_banco_gravado"]

    # Recarrega: o que faltava virou casado e o total do banco ficou gravado.
    f = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert f["valor_banco"] == 36766 + 3621 + 2050 + 12975
    r2 = _analisar(cliente, cartao).json()
    assert r2["resumo"]["so_fatura"] == 0 and r2["resumo"]["casados"] == 4
