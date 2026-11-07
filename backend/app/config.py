"""Configuração lida do ambiente (arquivo .env na raiz do projeto)."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _empacotado() -> bool:
    """True quando rodando dentro do .exe gerado pelo PyInstaller."""
    return getattr(sys, "frozen", False)


if _empacotado():
    # No .exe: as telas e migrações vêm do bundle temporário (_MEIPASS);
    # já os dados (banco, backup, .env) ficam AO LADO do executável, para persistir.
    RAIZ = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    _PASTA_PADRAO = Path(sys.executable).resolve().parent
else:
    RAIZ = Path(__file__).resolve().parents[2]
    _PASTA_PADRAO = RAIZ


def _carregar_env(arquivo: Path) -> None:
    """Lê KEY=valor de um .env simples, sem sobrescrever o ambiente."""
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"'))


def _verdadeiro(valor: str | None) -> bool:
    return (valor or "").strip().lower() in ("1", "true", "sim", "yes", "on")


@dataclass(frozen=True)
class Config:
    pasta_dados: Path
    pasta_backup: Path
    pasta_backup_drive: Path | None
    anthropic_api_key: str | None
    modo_demo: bool = False

    @property
    def arquivo_banco(self) -> Path:
        # No modo demonstração o banco é SEPARADO: nunca toca nos dados reais.
        nome = "financeiro_demo.db" if self.modo_demo else "financeiro.db"
        return self.pasta_dados / nome


def carregar() -> Config:
    _carregar_env(_PASTA_PADRAO / ".env")
    drive = os.environ.get("CF_PASTA_BACKUP_DRIVE", "").strip()
    return Config(
        pasta_dados=Path(os.environ.get("CF_PASTA_DADOS", _PASTA_PADRAO / "data")),
        pasta_backup=Path(os.environ.get("CF_PASTA_BACKUP", _PASTA_PADRAO / "BackUp")),
        pasta_backup_drive=Path(drive) if drive else None,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        modo_demo=_verdadeiro(os.environ.get("CF_MODO_DEMO") or os.environ.get("MODO_DEMO")),
    )
