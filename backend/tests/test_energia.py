"""Painel de energia: Escelsa + Solar por mês de consumo, preço real do kWh e consumo × ano anterior."""


def _conta(cliente):
    return cliente.post("/api/contas", json={"nome": "Itaú", "tipo": "corrente",
        "saldo_inicial_centavos": 100000, "data_saldo_inicial": "2026-08-01"}).json()["id"]


def _paga(cliente, conta, desc, valor, venc, pago_em, ficha):
    t = cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": desc,
        "valor_centavos": valor, "data": venc, "conta_id": conta, "pago": False}).json()[0]
    cliente.patch(f"/api/transacoes/{t['id']}", json={"pago": True, "data": pago_em})
    assert cliente.put(f"/api/transacoes/{t['id']}/ficha", json=ficha).status_code == 200


def test_junta_escelsa_e_solar_e_calcula_o_kwh(cliente):
    conta = _conta(cliente)
    _paga(cliente, conta, "EDP ESCELSA", 10216, "2026-10-13", "2026-10-16", {
        "tipo": "energia", "referencia": "2026-09", "consumo": 224, "kwh_compensado": 174,
        "bandeira": "amarela", "bandeira_centavos": 148})
    _paga(cliente, conta, "EDP SOLAR", 16486, "2026-10-26", "2026-10-16", {
        "tipo": "energia_solar", "referencia": "2026-09", "kwh_compensado": 174})
    # Só a Solar de um mês sem Escelsa: fica de fora (consumo e parte fixa incompletos).
    _paga(cliente, conta, "EDP SOLAR", 15019, "2026-09-25", "2026-09-17", {
        "tipo": "energia_solar", "referencia": "2026-08", "kwh_compensado": 163})

    d = cliente.get("/api/painel/energia").json()
    assert [m["referencia"] for m in d["meses"]] == ["2026-09"]
    m = d["meses"][0]
    assert (m["escelsa_centavos"], m["solar_centavos"], m["total_centavos"]) == (10216, 16486, 26702)
    assert m["custo_kwh"] == round(26702 / 224)            # R$ 1,19 por kWh
    assert m["dias_atraso"] == 3                            # Escelsa paga 3 dias depois
    assert m["bandeira"] == "amarela" and m["completo"]
    assert d["resumo"]["meses_com_atraso"] == 1


def test_compara_com_o_mesmo_mes_do_ano_anterior(con):
    from app.services import energia
    con.execute("INSERT INTO conta(nome, tipo) VALUES ('X', 'corrente')")
    conta = con.execute("SELECT max(id) FROM conta").fetchone()[0]
    for ref, venc, valor, consumo in (("2026-08", "2026-09-10", 9100, 213), ("2026-09", "2026-10-13", 10216, 224)):
        con.execute("INSERT INTO transacao(tipo, descricao, valor_centavos, data, conta_id, pago) "
                    "VALUES ('despesa', 'EDP ESCELSA', ?, ?, ?, 1)", (valor, venc, conta))
        tid = con.execute("SELECT max(id) FROM transacao").fetchone()[0]
        con.execute("INSERT INTO conta_ficha(transacao_id, tipo, referencia, consumo, cip_centavos, "
                    "terceiros_centavos) VALUES (?, 'energia', ?, ?, 2791, 671)", (tid, ref, consumo))
    con.executemany("INSERT INTO conta_historico(tipo, referencia, consumo) VALUES ('energia', ?, ?)",
                    [("2025-08", 201), ("2025-09", 192)])
    r = energia.painel(con)["resumo"]
    assert r["variacao_consumo_pct"] == round((437 / 393 - 1) * 100, 1)   # +11,2%
    assert (r["fixos_centavos"], r["seguro_centavos"]) == (2 * 3462, 2 * 671)
    assert r["custo_kwh_energia"] == round((19316 - 2 * 3462) / 437)
