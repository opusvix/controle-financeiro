"""Contas da casa: vencimento separado do pagamento, ficha da fatura e despesas fixas x variáveis."""


def _conta(cliente):
    return cliente.post("/api/contas", json={"nome": "Itaú", "tipo": "corrente",
        "saldo_inicial_centavos": 100000, "data_saldo_inicial": "2026-10-01"}).json()["id"]


def _cat(cliente, nome):
    return next(c for c in cliente.get("/api/categorias").json() if c["nome"] == nome)


def _luz(cliente, conta, meses=2, descricao="EDP ESCELSA"):
    cat = _cat(cliente, "Energia, água e gás")["id"]
    return cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": descricao,
        "valor_centavos": 9610, "data": "2026-11-16", "conta_id": conta, "pago": False,
        "categoria_id": cat, "repetir_meses": meses}).json()


def test_pagar_guarda_o_vencimento_e_desfazer_devolve_a_data(cliente):
    luz = _luz(cliente, _conta(cliente))[0]
    r = cliente.patch(f"/api/transacoes/{luz['id']}", json={"pago": True, "data": "2026-11-28"}).json()
    assert (r["data"], r["vencimento"]) == ("2026-11-28", "2026-11-16")   # 12 dias de atraso
    r = cliente.patch(f"/api/transacoes/{luz['id']}", json={"pago": False}).json()
    assert (r["data"], r["vencimento"], r["pago"]) == ("2026-11-16", None, 0)


def test_lancamento_ja_pago_nao_ganha_vencimento(cliente):
    conta = _conta(cliente)
    r = cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "Padaria",
        "valor_centavos": 1000, "data": "2026-11-02", "conta_id": conta}).json()[0]
    r = cliente.patch(f"/api/transacoes/{r['id']}", json={"pago": True, "data": "2026-11-03"}).json()
    assert r["vencimento"] is None


def test_ficha_grava_so_os_campos_do_tipo(cliente):
    luz = _luz(cliente, _conta(cliente))[0]
    r = cliente.put(f"/api/transacoes/{luz['id']}/ficha", json={"tipo": "energia", "referencia": "2026-10",
        "consumo": 312, "kwh_compensado": 250, "bandeira": "amarela", "bandeira_centavos": 589,
        "multa_juros_centavos": 480, "vidas": 3}).json()
    assert r["gravada"] and r["consumo"] == 312 and r["bandeira"] == "amarela"
    assert r["multa_juros_centavos"] == 480
    assert r["vidas"] is None                      # vidas não vale para energia
    lista = cliente.get("/api/transacoes?competencia=2026-11").json()
    assert next(t for t in lista if t["id"] == luz["id"])["tem_ficha"] == 1


def test_ficha_sugere_o_tipo_pelo_mes_anterior_da_mesma_conta(cliente):
    jan, fev = _luz(cliente, _conta(cliente))
    cliente.put(f"/api/transacoes/{jan['id']}/ficha", json={"tipo": "energia", "consumo": 300})
    r = cliente.get(f"/api/transacoes/{fev['id']}/ficha").json()
    assert (r["gravada"], r["tipo"], r["consumo"], r["referencia"]) == (False, "energia", None, "2026-11")


def test_ficha_so_para_despesa(cliente):
    conta = _conta(cliente)
    rec = cliente.post("/api/transacoes", json={"tipo": "receita", "descricao": "Salário",
        "valor_centavos": 500000, "data": "2026-11-05", "conta_id": conta}).json()[0]
    assert cliente.put(f"/api/transacoes/{rec['id']}/ficha", json={"tipo": "outra"}).status_code == 422


def test_dashboard_separa_fixas_e_variaveis(cliente):
    conta = _conta(cliente)
    _luz(cliente, conta, meses=1)                                        # Energia: fixa
    farm = _cat(cliente, "Farmácia")["id"]
    cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "Drogaria",
        "valor_centavos": 4500, "data": "2026-11-10", "conta_id": conta, "categoria_id": farm})
    fv = cliente.get("/api/dashboard?competencia=2026-11").json()["fixas_variaveis"]
    assert fv == {"fixas": 9610, "variaveis": 4500}
    # marcar a categoria-mãe Saúde como fixa leva a Farmácia junto (herança)
    saude = _cat(cliente, "Saúde")["id"]
    assert cliente.patch(f"/api/categorias/{saude}", json={"fixa": True}).json()["fixa"] == 1
    fv = cliente.get("/api/dashboard?competencia=2026-11").json()["fixas_variaveis"]
    assert fv == {"fixas": 14110, "variaveis": 0}
