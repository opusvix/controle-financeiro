"""App standalone (janela nativa): o launcher sobe o servidor e ele responde.

A janela em si (PyWebView) precisa de ambiente gráfico e só é testada no PC;
aqui validamos a parte que dá para automatizar: subir o FastAPI num thread.
"""
import json
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
