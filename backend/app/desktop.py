"""Abre o Controle Financeiro numa JANELA NATIVA, sem navegador (PyWebView).

Sobe o mesmo servidor FastAPI local num thread e mostra o app numa janela
própria do Windows. É o modo "aplicativo independente do navegador".

Rodar (de dentro de backend/): python -m app.desktop
Empacotar num .exe: ver scripts\\gerar_exe.bat (PyInstaller).
"""
from __future__ import annotations

import os
import sys
import threading
import time
import urllib.request

import uvicorn

from . import config as config_mod
from .main import criar_app

TITULO = "Controle Financeiro"


def _garantir_saida() -> None:
    """No .exe sem console (PyInstaller windowed), sys.stdout/stderr são None e o
    log do uvicorn quebra ao chamar None.isatty(). Manda a saída para o 'nada'."""
    for nome in ("stdout", "stderr"):
        if getattr(sys, nome, None) is None:
            setattr(sys, nome, open(os.devnull, "w", encoding="utf-8"))


def _esperar_servidor(url: str, tentativas: int = 80) -> bool:
    """Espera o servidor responder antes de abrir a janela (evita tela em branco)."""
    for _ in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def iniciar_servidor(host: str, port: int) -> uvicorn.Server:
    """Sobe o FastAPI num thread em segundo plano e devolve o servidor."""
    servidor = uvicorn.Server(uvicorn.Config(criar_app(), host=host, port=port,
                                             log_level="warning"))
    threading.Thread(target=servidor.run, daemon=True).start()
    return servidor


def main() -> None:
    _garantir_saida()
    host = os.environ.get("CF_HOST", "127.0.0.1")
    port = int(os.environ.get("CF_PORT", "8000"))
    base = f"http://{host}:{port}/"

    servidor = iniciar_servidor(host, port)
    if not _esperar_servidor(base + "api/saude"):
        raise SystemExit("O servidor não respondeu a tempo.")

    # No modo demonstração a janela avisa no título, para não confundir com os dados reais.
    titulo = TITULO + (" — Demonstração" if config_mod.carregar().modo_demo else "")

    import webview  # importado aqui: o módulo carrega mesmo sem a janela instalada
    webview.create_window(titulo, base, width=1280, height=860, min_size=(900, 600))
    webview.start()                 # bloqueia até a janela fechar
    servidor.should_exit = True     # fecha o servidor junto com a janela


if __name__ == "__main__":
    main()
