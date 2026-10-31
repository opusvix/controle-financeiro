"""Backup do banco com rotação avô-pai-filho e cópia para o Google Drive.

Guarda o backup mais recente de cada um dos últimos 7 dias, 4 semanas e
12 meses. O banco em uso NUNCA fica dentro do Drive: só as cópias vão para lá.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

PADRAO = re.compile(r"^financeiro_(\d{8}_\d{6})\.db$")
RETER_DIAS, RETER_SEMANAS, RETER_MESES = 7, 4, 12


def _momento(arquivo: Path) -> datetime | None:
    m = PADRAO.match(arquivo.name)
    return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S") if m else None


def fazer(con: sqlite3.Connection, pasta: Path, agora: datetime | None = None) -> Path:
    """Cópia consistente do banco (API de backup do SQLite, segura com o app aberto)."""
    agora = agora or datetime.now()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"financeiro_{agora:%Y%m%d_%H%M%S}.db"
    with sqlite3.connect(destino) as copia:
        con.backup(copia)
    copia.close()
    return destino


def escolher_mantidos(momentos: list[datetime]) -> set[datetime]:
    """Quais backups ficam: o mais recente de cada dia/semana/mês dentro da janela."""
    ordenados = sorted(momentos, reverse=True)
    mantidos: set[datetime] = set()
    for chave, limite in (
        (lambda d: d.date(), RETER_DIAS),
        (lambda d: d.isocalendar()[:2], RETER_SEMANAS),
        (lambda d: (d.year, d.month), RETER_MESES),
    ):
        vistos = []
        for d in ordenados:
            k = chave(d)
            if k not in vistos:
                vistos.append(k)
                if len(vistos) > limite:
                    break
                mantidos.add(d)
    return mantidos


def rotacionar(pasta: Path) -> list[Path]:
    """Apaga os backups fora da política. Devolve os apagados."""
    arquivos = {m: a for a in pasta.glob("financeiro_*.db") if (m := _momento(a))}
    manter = escolher_mantidos(list(arquivos))
    apagados = []
    for momento, arquivo in arquivos.items():
        if momento not in manter:
            arquivo.unlink()
            apagados.append(arquivo)
    return apagados


def executar(con: sqlite3.Connection, pasta: Path, pasta_drive: Path | None,
             agora: datetime | None = None) -> dict:
    arquivo = fazer(con, pasta, agora)
    rotacionar(pasta)
    copiado = False
    if pasta_drive is not None:
        try:
            pasta_drive.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arquivo, pasta_drive / arquivo.name)
            rotacionar(pasta_drive)
            copiado = True
        except OSError:
            copiado = False  # Drive desconectado: o backup local continua valendo
    tamanho = arquivo.stat().st_size
    con.execute("INSERT INTO backup_log (arquivo, bytes, copiado_drive) VALUES (?, ?, ?)",
                (arquivo.name, tamanho, int(copiado)))
    con.commit()
    return {"arquivo": str(arquivo), "bytes": tamanho, "copiado_drive": copiado}


def ultimo(con: sqlite3.Connection) -> dict | None:
    r = con.execute("SELECT * FROM backup_log ORDER BY id DESC LIMIT 1").fetchone()
    return dict(r) if r else None
