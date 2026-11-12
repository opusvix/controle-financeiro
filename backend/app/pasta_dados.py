"""Primeira vez no .exe: onde guardar os dados.

O app standalone guardava os dados na pasta AO LADO do .exe. Agora, na primeira
abertura do app normal, ele PERGUNTA onde o usuário quer guardar (sugerindo
`Documentos\\ControleFinanceiro`) e anota a escolha num bilhete
(`local-dos-dados.txt`), ao lado do .exe, para as próximas vezes abrirem direto
na pasta certa. A janela/pergunta ficam no desktop.py; aqui mora só a lógica
(pura, testável).

Não mexe no modo desenvolvimento (roda do código, usa a pasta `data` do repo)
nem no modo demonstração (dados fictícios ao lado do .exe, descartáveis).
"""
from __future__ import annotations

import os
from pathlib import Path

from . import config as config_mod

BILHETE = "local-dos-dados.txt"   # guarda o caminho escolhido, ao lado do .exe


def _bilhete() -> Path:
    return config_mod._PASTA_PADRAO / BILHETE


def pasta_salva() -> Path | None:
    """O caminho anotado numa execução anterior, se houver."""
    bi = _bilhete()
    if not bi.exists():
        return None
    texto = bi.read_text(encoding="utf-8").strip()
    return Path(texto) if texto else None


def salvar_escolha(pasta: Path) -> None:
    _bilhete().write_text(str(pasta), encoding="utf-8")


def pasta_sugerida() -> Path:
    """Sugestão prática: `Documentos\\ControleFinanceiro` (achando a pasta de
    Documentos mesmo quando o OneDrive a redireciona); senão, a pasta do usuário."""
    lar = Path.home()
    for rel in ("Documents", "OneDrive/Documents", "OneDrive/Documentos", "Documentos"):
        if (lar / rel).is_dir():
            return lar / rel / "ControleFinanceiro"
    return lar / "ControleFinanceiro"


def aplicar(pasta: Path) -> None:
    """Faz o app usar essa pasta para dados e backup, sem sobrescrever o que o
    usuário já tenha definido no ambiente/.env."""
    os.environ.setdefault("CF_PASTA_DADOS", str(pasta))
    os.environ.setdefault("CF_PASTA_BACKUP", str(pasta / "BackUp"))


def precisa_perguntar(*, empacotado: bool, modo_demo: bool) -> bool:
    """Pergunta só no .exe normal (não demo), quando ainda não há escolha salva
    nem caminho definido no ambiente."""
    if not empacotado or modo_demo:
        return False
    if os.environ.get("CF_PASTA_DADOS"):
        return False
    return pasta_salva() is None
