"""Versão de demonstração: seed fictício, idempotência e 'Reiniciar demonstração'."""
from datetime import date

from fastapi.testclient import TestClient

from app import db, seed_demo
from app.config import Config
from app.main import criar_app

HOJE = date(2026, 11, 7)


def _banco():
    c = db.conectar(":memory:")
    db.migrar(c)
    return c


def _conta_count(c):
    return c.execute("SELECT COUNT(*) FROM conta").fetchone()[0]


def test_construir_popula_todas_as_telas():
    c = _banco()
    seed_demo.construir(c, HOJE)
    assert _conta_count(c) >= 3                                   # C6, BB, Carteira
    assert c.execute("SELECT COUNT(*) FROM cartao").fetchone()[0] == 2
    assert c.execute("SELECT COUNT(*) FROM transacao").fetchone()[0] > 15
    assert c.execute("SELECT COUNT(*) FROM fatura").fetchone()[0] >= 2
    assert c.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 6   # 2 cupons × 3 itens
    # Há contas a pagar no mês corrente (as fixas não pagas).
    assert c.execute("SELECT COUNT(*) FROM transacao WHERE pago = 0 AND tipo = 'despesa'"
                     ).fetchone()[0] >= 3
    # Há uma compra parcelada em 3× (uma por mês).
    assert c.execute("SELECT COUNT(*) FROM transacao WHERE total_parcelas = 3").fetchone()[0] == 3
    c.close()


def test_garantir_so_semeia_uma_vez():
    c = _banco()
    assert seed_demo.garantir(c, HOJE) is True
    n = c.execute("SELECT COUNT(*) FROM transacao").fetchone()[0]
    assert seed_demo.garantir(c, HOJE) is False                  # já tem dados: não semeia de novo
    assert c.execute("SELECT COUNT(*) FROM transacao").fetchone()[0] == n
    c.close()


def test_reiniciar_nao_duplica():
    c = _banco()
    seed_demo.construir(c, HOJE)
    antes = c.execute("SELECT COUNT(*) FROM transacao").fetchone()[0]
    seed_demo.reiniciar(c, HOJE)
    assert c.execute("SELECT COUNT(*) FROM transacao").fetchone()[0] == antes
    assert _conta_count(c) >= 3                                   # não acumulou contas repetidas
    c.close()


def _cliente_demo(tmp_path, demo=True):
    cfg = Config(pasta_dados=tmp_path, pasta_backup=tmp_path / "BackUp",
                 pasta_backup_drive=None, anthropic_api_key=None, modo_demo=demo)
    return TestClient(criar_app(cfg, banco=":memory:"))


def test_saude_informa_modo_demo(tmp_path):
    with _cliente_demo(tmp_path) as cli:
        assert cli.get("/api/saude").json()["modo_demo"] is True
        # E o modo demo já deixou as telas com dados.
        assert len(cli.get("/api/contas").json()) >= 3


def test_endpoint_reiniciar_demo(tmp_path):
    with _cliente_demo(tmp_path) as cli:
        assert cli.post("/api/demo/reiniciar").json() == {"ok": True}
        assert len(cli.get("/api/cartoes").json()) == 2


def test_reiniciar_bloqueado_fora_do_demo(tmp_path):
    with _cliente_demo(tmp_path, demo=False) as cli:
        assert cli.get("/api/saude").json()["modo_demo"] is False
        assert cli.post("/api/demo/reiniciar").status_code == 404
