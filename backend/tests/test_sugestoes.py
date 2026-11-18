"""Autocompletar da Descrição: sugere descrições do histórico e a categoria usual.

Usa descrições com um prefixo único (ZZQ) para não colidir com os dados semeados."""


def _cat(cliente, nome, tipo="despesa"):
    return cliente.post("/api/categorias", json={"nome": nome, "tipo": tipo}).json()["id"]


def _conta(cliente):
    return cliente.post("/api/contas", json={"nome": "Conta Sugestao ZZQ", "tipo": "corrente",
                                             "saldo_inicial_centavos": 0}).json()["id"]


def _desp(cliente, conta, descricao, data, categoria_id=None):
    return cliente.post("/api/transacoes", json={
        "tipo": "despesa", "descricao": descricao, "valor_centavos": 1000,
        "data": data, "conta_id": conta, "categoria_id": categoria_id})


def _sug(cliente, termo, tipo="despesa"):
    return cliente.get("/api/transacoes/sugestoes-descricao",
                       params={"termo": termo, "tipo": tipo}).json()


def test_sugere_por_prefixo_e_ignora_acento_e_caixa(cliente):
    conta = _conta(cliente)
    _desp(cliente, conta, "ZZQ Supermercado Perim", "2026-11-01")
    _desp(cliente, conta, "ZZQ Farmácia São João", "2026-11-02")
    r = _sug(cliente, "zzq super")
    assert any(s["descricao"] == "ZZQ Supermercado Perim" for s in r)
    assert all("farm" not in s["descricao"].lower() for s in r)
    # acento no termo não atrapalha
    assert any("Farmácia" in s["descricao"] for s in _sug(cliente, "zzq farmacia"))


def test_mais_frequente_vem_antes(cliente):
    conta = _conta(cliente)
    for d in ("2026-11-01", "2026-11-03", "2026-11-05"):
        _desp(cliente, conta, "ZZQ Mercado Bom Preço", d)
    _desp(cliente, conta, "ZZQ Mercado Livre", "2026-11-02")
    r = _sug(cliente, "zzq mercado")
    assert r[0]["descricao"] == "ZZQ Mercado Bom Preço"


def test_traz_categoria_mais_usada_daquela_descricao(cliente):
    conta = _conta(cliente)
    mercado = _cat(cliente, "ZZQ Mercado")
    lazer = _cat(cliente, "ZZQ Lazer")
    _desp(cliente, conta, "ZZQ Padaria Central", "2026-11-01", categoria_id=mercado)
    _desp(cliente, conta, "ZZQ Padaria Central", "2026-11-02", categoria_id=mercado)
    _desp(cliente, conta, "ZZQ Padaria Central", "2026-11-03", categoria_id=lazer)
    r = _sug(cliente, "zzq padaria")
    assert r[0]["descricao"] == "ZZQ Padaria Central"
    assert r[0]["categoria_id"] == mercado


def test_termo_curto_nao_sugere(cliente):
    conta = _conta(cliente)
    _desp(cliente, conta, "ZZQ Uber", "2026-11-01")
    assert _sug(cliente, "z") == []


def test_tipo_receita_nao_mistura_categoria_de_despesa(cliente):
    conta = _conta(cliente)
    salario = _cat(cliente, "ZZQ Salário", tipo="receita")
    _cat(cliente, "ZZQ Serviços")  # despesa (não deve ser escolhida para uma receita)
    cliente.post("/api/transacoes", json={"tipo": "receita", "descricao": "ZZQ Salário Raízen",
                 "valor_centavos": 5000, "data": "2026-11-05", "conta_id": conta,
                 "categoria_id": salario})
    r = _sug(cliente, "zzq salario", tipo="receita")
    assert r and r[0]["categoria_id"] == salario
