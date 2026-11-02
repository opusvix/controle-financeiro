"""Contas que se repetem todo mês (luz, água, plano de saúde) e a baixa no pagamento."""
from datetime import date, timedelta


def _conta(cliente):
    return cliente.post("/api/contas", json={"nome": "C6 Bank", "tipo": "corrente",
        "saldo_inicial_centavos": 100000, "data_saldo_inicial": "2026-10-01"}).json()["id"]


def _luz(cliente, conta, meses=12, pago=False, data="2026-11-15"):
    return cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "Conta de luz EDP",
        "valor_centavos": 25000, "data": data, "conta_id": conta, "pago": pago,
        "repetir_meses": meses}).json()


def test_repetir_cria_um_lancamento_por_mes_todos_a_pagar(cliente):
    conta = _conta(cliente)
    luz = _luz(cliente, conta, meses=3, pago=True, data="2026-01-31")
    assert [t["data"] for t in luz] == ["2026-01-31", "2026-02-28", "2026-03-31"]
    assert [t["pago"] for t in luz] == [1, 0, 0]          # só o primeiro já foi pago
    assert len({t["recorrencia_id"] for t in luz}) == 1
    assert all(t["descricao"] == "Conta de luz EDP" for t in luz)


def test_so_receita_e_despesa_se_repetem(cliente):
    r = cliente.post("/api/transacoes", json={"tipo": "despesa_cartao", "descricao": "x",
        "valor_centavos": 100, "data": "2026-11-01", "cartao_id": 1, "repetir_meses": 3})
    assert r.status_code == 422


def test_pagar_da_baixa_com_valor_real_e_mexe_no_saldo(cliente):
    conta = _conta(cliente)
    luz = _luz(cliente, conta)
    saldo = lambda: next(c for c in cliente.get("/api/dashboard").json()["contas"] if c["id"] == conta)["saldo_atual"]
    antes = saldo()
    hoje = date.today().isoformat()
    r = cliente.patch(f"/api/transacoes/{luz[0]['id']}", json={"pago": True, "valor_centavos": 26318,
        "data": hoje, "conta_id": conta}).json()
    assert (r["pago"], r["valor_centavos"], r["data"]) == (1, 26318, hoje)
    assert saldo() == antes - 26318
    # O mês seguinte continua com a estimativa.
    seg = cliente.get("/api/transacoes", params={"competencia": luz[1]["data"][:7]}).json()
    assert [t["valor_centavos"] for t in seg if t["id"] == luz[1]["id"]] == [25000]


def test_reajuste_vale_para_os_meses_nao_pagos(cliente):
    conta = _conta(cliente)
    plano = _luz(cliente, conta, meses=4)
    cliente.patch(f"/api/transacoes/{plano[0]['id']}", json={"pago": True})
    cliente.patch(f"/api/transacoes/{plano[1]['id']}", json={"valor_centavos": 31000,
        "descricao": "Plano de saúde", "aplicar_nas_proximas": True})
    todos = {}
    for t in plano:
        for x in cliente.get("/api/transacoes", params={"competencia": t["data"][:7]}).json():
            todos[x["id"]] = (x["valor_centavos"], x["descricao"])
    assert [todos[t["id"]] for t in plano] == [(25000, "Conta de luz EDP"), (31000, "Plano de saúde"),
                                               (31000, "Plano de saúde"), (31000, "Plano de saúde")]


def test_cancelar_apaga_os_proximos_nao_pagos(cliente):
    conta = _conta(cliente)
    net = _luz(cliente, conta, meses=4)
    assert cliente.delete(f"/api/transacoes/{net[1]['id']}", params={"proximas": True}).status_code == 204
    restantes = [t["id"] for t in net
                 if any(x["id"] == t["id"] for x in
                        cliente.get("/api/transacoes", params={"competencia": t["data"][:7]}).json())]
    assert restantes == [net[0]["id"]]


def test_lista_a_pagar_inclui_atrasadas_e_ignora_pagas(cliente):
    conta = _conta(cliente)
    atrasada = (date.today() - timedelta(days=5)).isoformat()
    contas = _luz(cliente, conta, meses=3, data=atrasada)
    cliente.patch(f"/api/transacoes/{contas[1]['id']}", json={"pago": True})
    ids = [t["id"] for t in cliente.get("/api/a-pagar", params={"dias": 366}).json()]
    assert ids == [contas[0]["id"], contas[2]["id"]]
    ids30 = [t["id"] for t in cliente.get("/api/a-pagar", params={"dias": 0}).json()]
    assert ids30 == [contas[0]["id"]]
