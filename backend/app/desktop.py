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


def _html_pergunta(caminho: str) -> str:
    """Tela da 1ª abertura: mostra a pasta sugerida EM TEXTO e um botão que a usa
    num clique. Não abrimos o seletor nativo de cara porque, no Windows, ele
    ignora a pasta sugerida e reabre no último lugar visto no Explorer — a
    sugestão nunca aparecia. O seletor só abre se o usuário pedir 'outra pasta'."""
    caminho_html = (caminho.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;"))
    return """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<style>
:root{--bg:#F4F2EF;--cartao:#fff;--texto:#1c1813;--suave:#6c6358;
--laranja:#F38433;--borda:#e4ddd3}
@media(prefers-color-scheme:dark){:root{--bg:#16130e;--cartao:#211c15;
--texto:#f3eee6;--suave:#b9ac9b;--borda:#3a3025}}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--texto);
font-family:Segoe UI,system-ui,sans-serif;display:grid;place-items:center;padding:24px}
main{max-width:520px;width:100%;background:var(--cartao);border:1px solid var(--borda);
border-radius:16px;padding:32px;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,.08)}
h1{font-size:22px;margin:0 0 14px}
p{margin:0 0 14px;line-height:1.5;color:var(--suave)}
.caminho{margin:18px 0}
.caminho code{display:inline-block;background:var(--bg);border:1px solid var(--borda);
border-radius:10px;padding:10px 14px;font-size:15px;color:var(--texto);word-break:break-all}
.dica{font-size:14px}
.botoes{display:flex;flex-direction:column;gap:10px;margin-top:22px}
button{font-size:16px;padding:13px 18px;border-radius:10px;cursor:pointer;
border:1px solid var(--borda);background:var(--cartao);color:var(--texto)}
button.primario{background:var(--laranja);border-color:var(--laranja);color:#111;font-weight:600}
button:disabled{opacity:.6;cursor:default}
.status{min-height:20px;margin:16px 0 0;font-size:14px}
</style></head>
<body><main>
<h1>Onde guardar seus dados?</h1>
<p>O Controle Financeiro vai guardar suas informações nesta pasta do seu computador:</p>
<p class="caminho"><code>__CAMINHO__</code></p>
<p class="dica">Pode confirmar — é o lugar recomendado. Se preferir outro local
(um pen drive, por exemplo), escolha a segunda opção.</p>
<div class="botoes">
  <button id="ok" class="primario">Usar esta pasta</button>
  <button id="outra">Escolher outra pasta…</button>
</div>
<p id="status" class="status"></p>
</main>
<script>
const ok=document.getElementById('ok'),outra=document.getElementById('outra'),
st=document.getElementById('status');
function trava(m){ok.disabled=true;outra.disabled=true;st.textContent=m;}
function solta(){ok.disabled=false;outra.disabled=false;st.textContent='';}
ok.addEventListener('click',()=>{trava('Preparando…');window.pywebview.api.usar_sugerida();});
outra.addEventListener('click',async()=>{trava('Abrindo o seletor…');
  const escolheu=await window.pywebview.api.escolher_outra();
  if(escolheu){st.textContent='Preparando…';}else{solta();}});
</script></body></html>""".replace("__CAMINHO__", caminho_html)


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


class _PrimeiraVez:
    """Ponte entre a tela da 1ª abertura (HTML) e o Python. Os botões da tela
    chamam estes métodos via `window.pywebview.api.*`. Quando a pasta é definida,
    grava a escolha, sobe o servidor e troca a tela pelo app."""

    def __init__(self, host: str, port: int, base: str) -> None:
        self.host, self.port, self.base = host, port, base
        self.sugerida = pasta_dados.pasta_sugerida()
        self.janela = None          # preenchido em main() logo após criar a janela
        self.servidor: uvicorn.Server | None = None

    def _abrir(self, pasta: Path) -> None:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError:
            pasta = self.sugerida
            pasta.mkdir(parents=True, exist_ok=True)
        pasta_dados.salvar_escolha(pasta)
        pasta_dados.aplicar(pasta)
        self.servidor = iniciar_servidor(self.host, self.port)  # criar_app() lê a pasta agora
        if _esperar_servidor(self.base + "api/saude"):
            self.janela.load_url(self.base)

    def usar_sugerida(self) -> None:
        """Botão 'Usar esta pasta': aceita a sugestão em um clique."""
        self._abrir(self.sugerida)

    def escolher_outra(self) -> bool:
        """Botão 'Escolher outra pasta…': abre o seletor nativo (começando na
        sugestão). Devolve False se o usuário cancelar, para a tela reabilitar."""
        import webview
        escolha = self.janela.create_file_dialog(webview.FOLDER_DIALOG,
                                                 directory=str(self.sugerida))
        if not escolha:
            return False
        self._abrir(Path(escolha[0]))
        return True


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

    # PRIMEIRA VEZ (app normal): a tela mostra a pasta sugerida e o usuário confirma.
    fluxo = _PrimeiraVez(host, port, base)
    fluxo.janela = webview.create_window(
        titulo, html=_html_pergunta(str(fluxo.sugerida)),
        width=1280, height=860, min_size=(900, 600), js_api=fluxo)
    webview.start()                     # bloqueia até a janela fechar
    if fluxo.servidor:
        fluxo.servidor.should_exit = True


if __name__ == "__main__":
    main()
