def test_fluxo_basico_pela_api(cliente):
    assert cliente.get("/api/saude").json()["ok"]
    conta = cliente.post("/api/contas", json={
        "nome": "C6 Bank", "tipo": "corrente", "saldo_inicial_centavos": 42029,
        "data_saldo_inicial": "2026-10-01"}).json()
    cartao = cliente.post("/api/cartoes", json={
        "nome": "BB JU", "bandeira": "Visa", "final": "3756", "limite_centavos": 2227900,
        "dia_fechamento": 3, "dia_vencimento": 10})
    assert cartao.status_code == 201
    r = cliente.post("/api/transacoes", json={
        "tipo": "despesa", "descricao": "AUTO POSTO TORRES", "valor_centavos": 10000,
        "data": "2026-10-28", "conta_id": conta["id"]})
    assert r.status_code == 201
    painel = cliente.get("/api/dashboard", params={"competencia": "2026-10"}).json()
    assert painel["despesas"] == 10000
    assert painel["saldo_disponivel"] == 42029 - 10000
    lista = cliente.get("/api/transacoes", params={"competencia": "2026-10"}).json()
    assert [t["descricao"] for t in lista] == ["AUTO POSTO TORRES"]


def test_cartao_com_final_errado_e_recusado(cliente):
    r = cliente.post("/api/cartoes", json={"nome": "X", "bandeira": "Visa", "final": "37",
                                           "dia_fechamento": 3, "dia_vencimento": 10})
    assert r.status_code == 422


def test_regra_de_negocio_vira_422(cliente):
    r = cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "x",
                                              "valor_centavos": 100, "data": "2026-10-01"})
    assert r.status_code == 422 and "conta" in r.json()["detail"]


def test_categorias_iniciais_tem_hierarquia(cliente):
    cats = cliente.get("/api/categorias", params={"tipo": "despesa"}).json()
    nomes = {c["nome"] for c in cats}
    assert {"Alimentação", "Mercado", "Combustível", "DETRAN"} <= nomes
    assert "CERCO FELINO" not in nomes  # projeto vira tag, não categoria


def test_chave_pela_api(cliente):
    r = cliente.post("/api/nfce/chave", params={"chave": "3226 1006 9555 7600 0512 6512 1000 3769 8916 1325 7499"})
    assert r.json()["numero"] == 376989 and r.json()["valida"]
