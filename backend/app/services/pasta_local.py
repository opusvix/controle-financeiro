"""Ler arquivos de uma pasta do próprio computador (o servidor roda em 127.0.0.1).

Base dos campos "pasta que lembra o último local": valida o caminho, lista os
arquivos de uma pasta por extensão e lê UM arquivo de dentro dela com segurança
(sem deixar o nome escapar para fora da pasta). Serve às telas de Conciliação,
Conciliação de Fatura e Cupom.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException


def _exts(extensoes: list[str]) -> set[str]:
    return {(e if e.startswith(".") else "." + e).lower() for e in extensoes}


def pasta_valida(caminho: str) -> Path:
    """Devolve a pasta se o caminho existir e for um diretório; senão, erro 422 claro."""
    caminho = (caminho or "").strip().strip('"').strip("'")
    if not caminho:
        raise HTTPException(422, "Informe o caminho da pasta.")
    pasta = Path(caminho)
    if not pasta.is_dir():
        raise HTTPException(422, f"Não encontrei a pasta: {caminho}")
    return pasta


def listar(caminho: str, extensoes: list[str]) -> tuple[Path, list[str]]:
    """Nomes dos arquivos da pasta cujas extensões batem (ordenados)."""
    pasta = pasta_valida(caminho)
    exts = _exts(extensoes)
    nomes = sorted(p.name for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in exts)
    return pasta, nomes


def ler_arquivo(caminho: str, nome: str, extensoes: list[str]) -> tuple[str, bytes]:
    """Lê os bytes de UM arquivo da pasta. `nome` é só o nome (nunca um caminho),
    para não escapar da pasta escolhida."""
    pasta = pasta_valida(caminho)
    if not nome or "/" in nome or "\\" in nome or nome in (".", ".."):
        raise HTTPException(422, "Nome de arquivo inválido.")
    alvo = pasta / nome
    if alvo.parent != pasta or not alvo.is_file():
        raise HTTPException(422, f"Não encontrei o arquivo: {nome}")
    if alvo.suffix.lower() not in _exts(extensoes):
        raise HTTPException(422, f"Tipo de arquivo não aceito: {nome}")
    return alvo.name, alvo.read_bytes()
