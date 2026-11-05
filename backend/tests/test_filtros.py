"""Filtros da tela Transações: filtragem do /api/transacoes e filtros salvos."""
from datetime import date

from app.services import transacoes
from app.services.transacoes import NovaTransacao


def _semear(con):
    conta = con.execute("SELECT id FROM conta WHERE nome = 'Carteira'").fetchone()[0]
    outra = con.execute("INSERT INTO conta (nome, tipo, saldo_inicial_centavos, data_saldo_inicial) "
                        "VALUES ('Banco X', 'corrente', 0, '2026-01-01')").lastrowid
    merc = con.execute("SELECT id FROM categoria WHERE nome = 'Mercado'").fetchone()[0]
    farm = con.execute("SELECT id FROM categoria WHERE nome = 'Farmácia'").fetchone()[0]
    tag = con.execute("INSERT INTO tag (nome) VALUES ('VIAGEM')").lastrowid
    transacoes.criar(con, NovaTransacao(tipo="despesa", descricao="Mercado", valor_centavos=10000,
                                        data=date(2026, 11, 3), conta_id=conta, categoria_id=merc))
    transacoes.criar(con, NovaTransacao(tipo="despesa", descricao="Remédio", valor_centavos=5000,
                                        data=date(2026, 11, 10), conta_id=outra, categoria_id=farm,
                                        pago=False, tags=[tag]))
    transacoes.criar(con, NovaTransacao(tipo="receita", descricao="Salário", valor_centavos=80000,
                                        data=date(2026, 10, 5), conta_id=conta,
                                        categoria_id=con.execute("SELECT id FROM categoria WHERE nome='Salário'").fetchone()[0]))
    return conta, outra, merc, farm, tag


def test_filtro_por_intervalo_e_tipo(cliente):
    _semear(cliente.app.state.con)
    # intervalo que pega só novembro
    r = cliente.get("/api/transacoes?ini=2026-11-01&fim=2026-11-30").json()
    assert {t["descricao"] for t in r} == {"Mercado", "Remédio"}
    # intervalo amplo + só receitas
    r = cliente.get("/api/transacoes?ini=2026-01-01&fim=2026-12-31&tipos=receita").json()
    assert [t["descricao"] for t in r] == ["Salário"]


def test_filtro_por_categoria_mae_conta_tag_situacao(cliente):
    con = cliente.app.state.con
    _conta, outra, _merc, _farm, _tag = _semear(con)
    # categoria-mãe Saúde inclui a subcategoria Farmácia
    saude = con.execute("SELECT id FROM categoria WHERE nome = 'Saúde'").fetchone()[0]
    r = cliente.get(f"/api/transacoes?ini=2026-11-01&fim=2026-11-30&categorias={saude}").json()
    assert [t["descricao"] for t in r] == ["Remédio"]
    # por conta
    r = cliente.get(f"/api/transacoes?ini=2026-11-01&fim=2026-11-30&contas={outra}").json()
    assert [t["descricao"] for t in r] == ["Remédio"]
    # só pendentes
    r = cliente.get("/api/transacoes?ini=2026-11-01&fim=2026-11-30&situacoes=pendente").json()
    assert [t["descricao"] for t in r] == ["Remédio"]
    # por tag
    tag = con.execute("SELECT id FROM tag WHERE nome = 'VIAGEM'").fetchone()[0]
    r = cliente.get(f"/api/transacoes?ini=2026-11-01&fim=2026-11-30&tags={tag}").json()
    assert [t["descricao"] for t in r] == ["Remédio"]


def test_filtros_salvos_crud(cliente):
    crit = {"ini": "2026-11-01", "fim": "2026-11-30", "contas": [1]}
    r = cliente.post("/api/filtros", json={"nome": "Casa em novembro", "criterios": crit})
    assert r.status_code == 201 and r.json()["criterios"] == crit
    fid = r.json()["id"]
    # salvar de novo com o mesmo nome atualiza (não duplica)
    crit2 = {**crit, "tipos": ["despesa"]}
    cliente.post("/api/filtros", json={"nome": "Casa em novembro", "criterios": crit2})
    lista = cliente.get("/api/filtros").json()
    assert len(lista) == 1 and lista[0]["criterios"] == crit2
    assert cliente.delete(f"/api/filtros/{fid}").status_code == 204
    assert cliente.get("/api/filtros").json() == []
