import pytest
from fastapi.testclient import TestClient

from app import db, seed
from app.config import Config
from app.main import criar_app


@pytest.fixture
def con():
    c = db.conectar(":memory:")
    db.migrar(c)
    seed.popular(c)
    yield c
    c.close()


@pytest.fixture
def cliente(tmp_path):
    cfg = Config(pasta_dados=tmp_path, pasta_backup=tmp_path / "BackUp",
                 pasta_backup_drive=tmp_path / "Drive", anthropic_api_key=None)
    with TestClient(criar_app(cfg, banco=":memory:")) as c:
        yield c
