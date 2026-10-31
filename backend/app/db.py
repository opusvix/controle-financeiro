"""Conexão SQLite e migrações numeradas (migrations/NNN_nome.sql)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

PASTA_MIGRACOES = Path(__file__).parent / "migrations"


def conectar(arquivo: Path | str) -> sqlite3.Connection:
    if str(arquivo) != ":memory:":
        Path(arquivo).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(arquivo, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL") if str(arquivo) != ":memory:" else None
    return con


def migrar(con: sqlite3.Connection) -> list[str]:
    """Aplica, em ordem, as migrações ainda não aplicadas. Devolve as aplicadas."""
    con.execute(
        "CREATE TABLE IF NOT EXISTS _migracao (nome TEXT PRIMARY KEY, "
        "aplicada_em TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    feitas = {r[0] for r in con.execute("SELECT nome FROM _migracao")}
    aplicadas = []
    for arquivo in sorted(PASTA_MIGRACOES.glob("*.sql")):
        if arquivo.name in feitas:
            continue
        con.executescript(arquivo.read_text(encoding="utf-8"))
        con.execute("INSERT INTO _migracao (nome) VALUES (?)", (arquivo.name,))
        aplicadas.append(arquivo.name)
    con.commit()
    return aplicadas
