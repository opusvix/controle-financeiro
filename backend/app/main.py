"""Servidor local. Rodar com: python -m app (dentro de backend/)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config as config_mod
from . import db, seed
from .routers import cadastros, conciliacao, cupons, movimento, sistema
from .services import backup

INTERVALO_BACKUP = timedelta(hours=20)


def _backup_se_preciso(con, cfg) -> None:
    ultimo = backup.ultimo(con)
    agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # SQLite grava em UTC
    if ultimo and agora_utc - datetime.fromisoformat(ultimo["criado_em"]) < INTERVALO_BACKUP:
        return
    backup.executar(con, cfg.pasta_backup, cfg.pasta_backup_drive)


def criar_app(cfg: config_mod.Config | None = None, banco: str | None = None) -> FastAPI:
    cfg = cfg or config_mod.carregar()

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        con = db.conectar(banco or cfg.arquivo_banco)
        db.migrar(con)
        seed.popular(con)
        if banco is None:
            _backup_se_preciso(con, cfg)
        app.state.con, app.state.cfg = con, cfg
        yield
        con.close()

    app = FastAPI(title="Controle Financeiro", lifespan=ciclo)
    for r in (cadastros.router, conciliacao.router, cupons.router, movimento.router, sistema.router):
        app.include_router(r)
    _servir_telas(app)
    return app


DESATUALIZADO = ("Esta função ainda não existe no servidor que está ligado. "
                 "Ele pode estar desatualizado: rode scripts\\parar.bat e abra o app de novo.")


def _servir_telas(app: FastAPI) -> None:
    """Entrega as telas já compiladas (frontend/dist), se existirem."""
    dist = config_mod.RAIZ / "frontend" / "dist"
    if not (dist / "index.html").exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def telas(caminho: str):
        # Qualquer rota que não seja /api abre o app (o React cuida da navegação).
        if caminho == "api" or caminho.startswith("api/"):
            return JSONResponse({"detail": DESATUALIZADO}, status_code=404)
        arquivo = (dist / caminho).resolve()
        if caminho and arquivo.is_file() and dist.resolve() in arquivo.parents:
            return FileResponse(arquivo)
        # Sem cache: depois de atualizar o app, o navegador sempre pega a tela nova.
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
