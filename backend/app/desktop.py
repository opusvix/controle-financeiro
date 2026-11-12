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
from pathlib import Path

import uvicorn

from . import config as config_mod
from . import pasta_dados
from .main import criar_app

TITULO = "Controle Financeiro"

# Página mostrada na janela enquanto o usuário escolhe a pasta e o servidor sobe.
_HTML_ESPERE = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<style>html{background:#F4F2EF;color:#1c1813;font-family:Segoe UI,system-ui,sans-serif}
@media(prefers-color-scheme:dark){html{background:#16130e;color:#f3eee6}}
body{height:100vh;margin:0;display:grid;place-items:center;text-align:center}
h1{font-size:22px;margin:0 0 8px}p{color:#6c6358;margin:0}</style></head>
<body><div><h1>Controle Financeiro</h1><p id="m">Preparando…</p></div></body></html>"""


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

    demo = config_mod.carregar().modo_demo
    # Escolha de pasta feita numa execução anterior? aplica e abre direto (nunca no demo).
    if not demo and not os.environ.get("CF_PASTA_DADOS"):
        salva = pasta_dados.pasta_salva()
        if salva:
            pasta_dados.aplicar(salva)

    # No modo demonstração a janela avisa no título, para não confundir com os dados reais.
    titulo = TITULO + (" — Demonstração" if demo else "")
    import webview  # importado aqui: o módulo carrega mesmo sem a janela instalada

    if not pasta_dados.precisa_perguntar(empacotado=config_mod._empacotado(), modo_demo=demo):
        # Fluxo normal: sobe o servidor e abre a janela já no app.
        servidor = iniciar_servidor(host, port)
        if not _esperar_servidor(base + "api/saude"):
            raise SystemExit("O servidor não respondeu a tempo.")
        webview.create_window(titulo, base, width=1280, height=860, min_size=(900, 600))
        webview.start()                 # bloqueia até a janela fechar
        servidor.should_exit = True     # fecha o servidor junto com a janela
        return

    # PRIMEIRA VEZ (app normal): pergunta onde guardar os dados, depois sobe o servidor.
    janela = webview.create_window(titulo, html=_HTML_ESPERE,
                                   width=1280, height=860, min_size=(900, 600))
    estado: dict = {}

    def preparar() -> None:
        sugerida = pasta_dados.pasta_sugerida()
        try:
            sugerida.mkdir(parents=True, exist_ok=True)   # já deixa a sugestão pronta p/ "OK"
        except OSError:
            sugerida = Path.home()
        escolha = janela.create_file_dialog(webview.FOLDER_DIALOG, directory=str(sugerida))
        pasta = Path(escolha[0]) if escolha else sugerida   # cancelou -> usa a sugestão
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError:
            pasta = sugerida
        pasta_dados.salvar_escolha(pasta)
        pasta_dados.aplicar(pasta)
        estado["servidor"] = iniciar_servidor(host, port)   # criar_app() lê a pasta agora
        if _esperar_servidor(base + "api/saude"):
            janela.load_url(base)

    webview.start(preparar)             # bloqueia até a janela fechar
    if estado.get("servidor"):
        estado["servidor"].should_exit = True


if __name__ == "__main__":
    main()
