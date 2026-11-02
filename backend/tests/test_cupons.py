from pathlib import Path

import pytest

from app.services import cupons
from app.services.transacoes import RegraViolada

AMOSTRA = Path(__file__).parent / "dados" / "sefaz_es_padaria.html"


def test_le_pagina_salva_da_sefaz_es():
    c = cupons.ler_sefaz_html(AMOSTRA.read_bytes())
    assert c["emitente"] == {"nome": "PADARIA IDEAL LTDA", "cnpj": "05932696000108",
                             "cidade": "Vila Velha", "uf": "ES"}
    assert c["numero"] == "379430" and c["serie"] == "13"
    assert c["emissao"] == "2026-10-21T16:45:12"
    assert c["chave"] == "32261005932696000108650130003794301133794308"
    assert [i["descricao"] for i in c["itens"]] == [
        "MORT DF SEARA KG", "PAO DE HOT DOG KG", "PAO DE HOT DOG KG", "PAO FRANCES KG"]
    mort = c["itens"][0]
    assert (mort["codigo"], mort["quantidade_milesimos"], mort["unidade"],
            mort["preco_unitario_centavos"], mort["valor_total_centavos"]) == ("5595", 106, "KG", 3890, 412)
    assert c["valor_pagar_centavos"] == 2917
    assert cupons.conferir(c)["confere"]


def test_pagina_sem_itens_explica_o_que_fazer():
    with pytest.raises(cupons.CupomInvalido, match="captcha"):
        cupons.ler_sefaz_html("<html><div class='cf-turnstile'></div>captcha</html>")


def test_desconto_no_total_e_rateado():
    c = cupons.normalizar_json({"itens": [
        {"descricao": "A", "valor_total_centavos": 1000},
        {"descricao": "B", "valor_total_centavos": 333}], "desconto_centavos": 100})
    assert [i["desconto_centavos"] for i in c["itens"]] == [76, 24]
    assert c["valor_pagar_centavos"] == 1233 and cupons.conferir(c)["confere"]


def _ids(con):
    conta = con.execute("SELECT id FROM conta WHERE nome = 'Carteira'").fetchone()[0]
    cat = lambda n: con.execute("SELECT id FROM categoria WHERE nome = ?", (n,)).fetchone()[0]  # noqa: E731
    return conta, cat("Padaria"), cat("Carnes")


def test_lanca_com_itens_aprende_e_bloqueia_duplicado(con):
    conta, padaria, carnes = _ids(con)
    c = cupons.ler_sefaz_html(AMOSTRA.read_bytes())
    r = cupons.lancar(con, c, conta_id=conta, categorias={1: carnes, 2: padaria})
    assert r["valor_centavos"] == 2917 and r["itens"] == 4
    t = con.execute("SELECT * FROM transacao WHERE id = ?", (r["transacao_id"],)).fetchone()
    assert (t["tipo"], t["data"], t["categoria_id"], t["descricao"]) == (
        "despesa", "2026-10-21", None, "PADARIA IDEAL LTDA")
    # O 3º item (mesmo pão do 2º) herda Padaria; o 4º herda a mais frequente (Padaria).
    cats = [r[0] for r in con.execute("SELECT categoria_id FROM item ORDER BY seq")]
    assert cats == [carnes, padaria, padaria, padaria]
    # Painel divide a compra por categoria de item.
    from app.services.painel import despesas_por_categoria
    fatias = {f["categoria"]: f["total"] for f in despesas_por_categoria(con, "2026-10")}
    assert fatias == {"Alimentação": 2917}

    de_novo = cupons.preparar(con, cupons.ler_sefaz_html(AMOSTRA.read_bytes()))
    assert de_novo["ja_lancado"] is not None
    assert [i["categoria_sugerida"] for i in de_novo["cupom"]["itens"]] == [carnes, padaria, padaria, padaria]
    with pytest.raises(RegraViolada, match="já foi lançado"):
        cupons.lancar(con, de_novo["cupom"], conta_id=conta)


def test_api_ler_e_lancar(cliente):
    r = cliente.post("/api/cupons/ler", files={"arquivo": ("ideal.html", AMOSTRA.read_bytes(), "text/html")})
    assert r.status_code == 200 and r.json()["conferencia"]["confere"]
    contas = cliente.get("/api/contas").json()
    cats = cliente.get("/api/categorias").json()
    padaria = next(x["id"] for x in cats if x["nome"] == "Padaria")
    r2 = cliente.post("/api/cupons/lancar", json={"cupom": r.json()["cupom"], "conta_id": contas[0]["id"],
                                                   "categorias": {"1": padaria}, "arquivo": "ideal.html"})
    assert r2.status_code == 201, r2.text
    assert cliente.post("/api/cupons/lancar", json={"cupom": r.json()["cupom"],
                                                    "conta_id": contas[0]["id"]}).status_code == 422
    ruim = cliente.post("/api/cupons/ler", files={"arquivo": ("x.html", b"<html>nada</html>", "text/html")})
    assert ruim.status_code == 422


def test_perim_30_itens_com_desconto_no_total():
    c = cupons.ler_sefaz_html((AMOSTRA.parent / "sefaz_es_perim.html").read_bytes())
    assert c["emitente"]["cnpj"] == "06955576000512" and len(c["itens"]) == 30
    assert (c["valor_total_centavos"], c["desconto_centavos"], c["valor_pagar_centavos"]) == (38871, 1365, 37506)
    queijo = c["itens"][3]
    assert (queijo["quantidade_milesimos"], queijo["preco_unitario_centavos"], queijo["valor_total_centavos"]) == (458, 8950, 4099)
    assert sum(i["desconto_centavos"] for i in c["itens"]) == 1365
    assert cupons.conferir(c)["confere"]
