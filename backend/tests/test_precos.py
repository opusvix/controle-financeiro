"""Comparação de preços (Fase 3): agrupamento por produto, variação, lojas e unidades."""
from app.services import precos


def _loja(con, nome):
    return con.execute("INSERT INTO estabelecimento (nome) VALUES (?)", (nome,)).lastrowid


def _doc(con, loja_id, data):
    return con.execute(
        "INSERT INTO documento (tipo, arquivo, estabelecimento_id, data_emissao, status) "
        "VALUES ('pedido', '(teste)', ?, ?, 'revisado')", (loja_id, data)).lastrowid


def _item(con, doc_id, descricao, unidade, qtd_milesimos, liquido_centavos, categoria=None):
    cat_id = con.execute("SELECT id FROM categoria WHERE nome = ?", (categoria,)).fetchone()[0] if categoria else None
    con.execute(
        "INSERT INTO item (documento_id, seq, descricao_lida, quantidade_milesimos, unidade, "
        "preco_unitario_centavos, valor_total_centavos, categoria_id) VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
        (doc_id, descricao, qtd_milesimos, unidade,
         round(liquido_centavos * 1000 / qtd_milesimos), liquido_centavos, cat_id))


def test_normaliza_nome_e_une_variacoes_de_texto():
    assert precos._chave_produto("LARANJA PERA KG") == "LARANJA PERA"
    assert precos._chave_produto("4 LARANJA PÊRA  kg") == "LARANJA PERA"      # acento + código + unidade
    assert precos._chave_produto("BATATA INGLESA UN") == "BATATA INGLESA"
    assert precos._chave_produto("12345") == ""                               # só código: ignora


def test_agrupa_por_produto_e_calcula_variacao(con):
    frescor = _loja(con, "Frescor")
    perim = _loja(con, "PERIM")
    # Laranja: subiu de 329 para 349 (R$/kg); comprada em duas lojas e dois meses.
    _item(con, _doc(con, perim, "2026-10-10"), "LARANJA PERA KG", "KG", 1000, 329, "Frutas")
    _item(con, _doc(con, frescor, "2026-11-03"), "LARANJA PERA KG", "KG", 1130, round(349 * 1130 / 1000), "Frutas")
    # Batata só uma compra.
    _item(con, _doc(con, frescor, "2026-11-03"), "BATATA INGLESA KG", "KG", 2000, 1198, "Legumes")

    p = precos.painel(con)
    assert p["resumo"]["produtos"] == 2
    assert p["resumo"]["com_historico"] == 1       # só a laranja tem 2+ compras
    frutas = next(g for g in p["grupos"] if g["categoria"] == "Frutas")
    laranja = frutas["produtos"][0]
    assert laranja["nome"] == "Laranja Pera" and laranja["unidade"] == "kg"
    assert laranja["compras"] == 2 and laranja["lojas"] == 2
    assert laranja["preco_atual_centavos"] == 349 and laranja["preco_anterior_centavos"] == 329
    assert laranja["variacao_pct"] == round((349 / 329 - 1) * 100, 1)
    assert laranja["menor_centavos"] == 329 and laranja["menor_loja"] == "PERIM"
    assert laranja["melhor_loja"] == "PERIM"        # mais barata entre as lojas
    assert [s["loja"] for s in laranja["serie"]] == ["PERIM", "Frescor"]


def test_sem_historico_nao_tem_variacao(con):
    loja = _loja(con, "Frescor")
    _item(con, _doc(con, loja, "2026-11-03"), "ALFACE CRESPA UN", "UN", 1000, 299, "Verduras")
    laranja = precos.painel(con)
    prod = laranja["grupos"][0]["produtos"][0]
    assert prod["variacao_pct"] is None and prod["preco_anterior_centavos"] is None
    assert prod["melhor_loja"] is None              # uma loja só


def test_unidades_diferentes_nao_se_misturam(con):
    loja = _loja(con, "Frescor")
    _item(con, _doc(con, loja, "2026-10-01"), "OVO BRANCO DZ", "DZ", 1000, 1200)      # unidade "dz" -> un? não: DZ não mapeia
    _item(con, _doc(con, loja, "2026-10-02"), "OVO BRANCO KG", "KG", 1000, 1800)
    p = precos.painel(con)
    nomes_unid = sorted((prod["nome"], prod["unidade"]) for g in p["grupos"] for prod in g["produtos"])
    # Mesmo texto "OVO BRANCO", unidades distintas -> dois produtos separados.
    assert nomes_unid == [("Ovo Branco", "dz"), ("Ovo Branco", "kg")]
