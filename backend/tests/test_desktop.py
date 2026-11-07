"""App standalone (janela nativa): o launcher sobe o servidor e ele responde.

A janela em si (PyWebView) precisa de ambiente gráfico e só é testada no PC;
aqui validamos a parte que dá para automatizar: subir o FastAPI num thread.
"""
import json
import sys
import urllib.request

from app import desktop

PORTA = 8766


def test_launcher_sobe_servidor_e_responde(tmp_path, monkeypatch):
    # Modo demo + banco temporário: não toca em dados reais nem faz backup.
    monkeypatch.setenv("CF_MODO_DEMO", "1")
    monkeypatch.setenv("CF_PASTA_DADOS", str(tmp_path))
    servidor = desktop.iniciar_servidor("127.0.0.1", PORTA)
    try:
        base = f"http://127.0.0.1:{PORTA}/"
        assert desktop._esperar_servidor(base + "api/saude")
        with urllib.request.urlopen(base + "api/saude", timeout=2) as r:
            dados = json.load(r)
        assert dados["ok"] is True and dados["modo_demo"] is True
    finally:
        servidor.should_exit = True


def test_garantir_saida_quando_sem_console(monkeypatch):
    """No .exe sem console sys.stdout é None; a correção evita o crash do uvicorn."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    desktop._garantir_saida()
    assert sys.stdout is not None and hasattr(sys.stdout, "write")
    assert sys.stderr is not None and hasattr(sys.stderr, "write")
