def _base(cliente):
    conta = cliente.post("/api/contas", json={"nome": "C6 Bank", "tipo": "corrente",
        "saldo_inicial_centavos": 100000, "data_saldo_inicial": "2026-10-01"}).json()
    cartao = cliente.post("/api/cartoes", json={"nome": "BB JU", "bandeira": "Visa", "final": "3756",
        "limite_centavos": 500000, "dia_fechamento": 3, "dia_vencimento": 10}).json()
    return conta["id"], cartao["id"]


def _compra(cliente, cartao, desc, valor, data, parcelas=1):
    return cliente.post("/api/transacoes", json={"tipo": "despesa_cartao", "descricao": desc,
        "valor_centavos": valor, "data": data, "cartao_id": cartao, "parcelas": parcelas}).json()


def test_fatura_lista_lancamentos_e_pagamento(cliente):
    conta, cartao = _base(cliente)
    _compra(cliente, cartao, "Padaria Ideal", 2917, "2026-10-21")      # fecha 03/11 -> vence 10/11
    _compra(cliente, cartao, "Geladeira", 30000, "2026-10-25", parcelas=3)
    f = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert [t["descricao"] for t in f["lancamentos"]] == ["Padaria Ideal", "Geladeira (1/3)"]
    assert f["total"] == 12917 and f["data_fechamento"] == "2026-11-03"
    assert f["data_vencimento"] == "2026-11-10"
    cliente.post("/api/transacoes", json={"tipo": "pagamento_fatura", "descricao": "Fatura BB",
        "valor_centavos": 12917, "data": "2026-11-10", "conta_id": conta, "cartao_id": cartao,
        "fatura_competencia": "2026-11"})
    f = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert f["situacao"] == "paga" and f["a_pagar"] == 0 and len(f["pagamentos"]) == 1


def test_fatura_vazia_tem_datas(cliente):
    _, cartao = _base(cliente)
    f = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2027-01"}).json()
    assert f["fatura_id"] is None and f["total"] == 0
    assert (f["data_fechamento"], f["data_vencimento"]) == ("2027-01-03", "2027-01-10")


def test_editar_conferir_e_mover_de_fatura(cliente):
    _, cartao = _base(cliente)
    t = _compra(cliente, cartao, "Padaria", 2917, "2026-10-21")[0]
    r = cliente.patch(f"/api/transacoes/{t['id']}", json={"descricao": "Padaria Ideal",
                                                          "valor_centavos": 3000, "conferido": True})
    assert r.status_code == 200 and r.json()["conferido"] == 1 and r.json()["valor_centavos"] == 3000
    # Mudar a data para depois do fechamento leva para a fatura seguinte.
    cliente.patch(f"/api/transacoes/{t['id']}", json={"data": "2026-11-05"})
    dez = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-12"}).json()
    assert [x["id"] for x in dez["lancamentos"]] == [t["id"]]
    # Mover à mão (o banco lançou em outro mês).
    cliente.patch(f"/api/transacoes/{t['id']}", json={"fatura_competencia": "2026-11"})
    nov = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert nov["total"] == 3000 and nov["conferido"] == 3000


def test_valor_do_banco_mostra_diferenca(cliente):
    _, cartao = _base(cliente)
    _compra(cliente, cartao, "Padaria", 2917, "2026-10-21")
    f = cliente.put(f"/api/cartoes/{cartao}/fatura/2026-11/valor-banco",
                    json={"valor_centavos": 3917}).json()
    assert f["valor_banco"] == 3917 and f["diferenca_banco"] == -1000


def test_editar_transferencia_muda_as_duas_pernas(cliente):
    conta, _ = _base(cliente)
    outra = cliente.post("/api/contas", json={"nome": "Itaú", "tipo": "corrente",
        "saldo_inicial_centavos": 0, "data_saldo_inicial": "2026-10-01"}).json()["id"]
    ids = cliente.post("/api/transacoes", json={"tipo": "transferencia", "descricao": "Pix",
        "valor_centavos": 1000, "data": "2026-10-05", "conta_id": conta,
        "conta_destino_id": outra}).json()
    cliente.patch(f"/api/transacoes/{ids[0]['id']}", json={"valor_centavos": 2500})
    lista = cliente.get("/api/transacoes", params={"competencia": "2026-10"}).json()
    assert sorted(t["valor_centavos"] for t in lista) == [2500, 2500]


def test_editar_inexistente_e_valor_invalido(cliente):
    assert cliente.patch("/api/transacoes/999", json={"descricao": "x"}).status_code == 422
    _, cartao = _base(cliente)
    t = _compra(cliente, cartao, "Padaria", 2917, "2026-10-21")[0]
    assert cliente.patch(f"/api/transacoes/{t['id']}", json={"descricao": "  "}).status_code == 422


def test_trocar_conta_por_cartao_e_volta(cliente):
    conta, cartao = _base(cliente)
    t = cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "Padaria Ideal",
        "valor_centavos": 2917, "data": "2026-10-21", "conta_id": conta}).json()[0]
    r = cliente.patch(f"/api/transacoes/{t['id']}", json={"cartao_id": cartao}).json()
    assert r["tipo"] == "despesa_cartao" and r["conta_id"] is None and r["fatura_id"]
    nov = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert nov["total"] == 2917
    r = cliente.patch(f"/api/transacoes/{t['id']}", json={"conta_id": conta}).json()
    assert r["tipo"] == "despesa" and r["cartao_id"] is None and r["fatura_id"] is None


def test_lancar_direto_na_fatura(cliente):
    _, cartao = _base(cliente)
    # Anuidade cobrada em 05/11 (depois do fechamento), mas o banco pôs na fatura de novembro.
    cliente.post("/api/transacoes", json={"tipo": "despesa_cartao", "descricao": "Anuidade",
        "valor_centavos": 2000, "data": "2026-11-05", "cartao_id": cartao,
        "fatura_competencia": "2026-11"})
    nov = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert [t["descricao"] for t in nov["lancamentos"]] == ["Anuidade"]


def test_credito_na_fatura_abate_total_e_despesa(cliente):
    _, cartao = _base(cliente)
    cat = next(x["id"] for x in cliente.get("/api/categorias").json() if x["nome"] == "Mercado")
    cliente.post("/api/transacoes", json={"tipo": "despesa_cartao", "descricao": "Mercado",
        "valor_centavos": 10000, "data": "2026-10-21", "cartao_id": cartao, "categoria_id": cat})
    r = cliente.post("/api/transacoes", json={"tipo": "credito_cartao", "descricao": "Estorno Mercado",
        "valor_centavos": 2500, "data": "2026-10-25", "cartao_id": cartao, "categoria_id": cat})
    assert r.status_code == 201
    f = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert f["total"] == 7500 and len(f["lancamentos"]) == 2
    painel = cliente.get("/api/dashboard", params={"competencia": "2026-10"}).json()
    assert painel["despesas"] == 7500
    assert painel["despesas_por_categoria"][0]["total"] == 7500
    assert painel["cartoes"][0]["limite_disponivel"] == 500000 - 7500
    # Pode ser movido de fatura como uma compra.
    cliente.patch(f"/api/transacoes/{r.json()[0]['id']}", json={"fatura_competencia": "2026-12"})
    f = cliente.get(f"/api/cartoes/{cartao}/fatura", params={"competencia": "2026-11"}).json()
    assert f["total"] == 10000


def test_credito_exige_cartao(cliente):
    conta, _ = _base(cliente)
    r = cliente.post("/api/transacoes", json={"tipo": "credito_cartao", "descricao": "x",
        "valor_centavos": 100, "data": "2026-10-25", "conta_id": conta})
    assert r.status_code == 422
