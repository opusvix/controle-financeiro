"""Ponto de entrada do app standalone (usado pelo PyInstaller para gerar o .exe).

Abre o Controle Financeiro numa janela nativa, sem navegador.

O MESMO arquivo gera dois executáveis (ver controle-financeiro.spec):
- ControleFinanceiro.exe             -> app normal (dados reais)
- ControleFinanceiro-Demonstracao.exe -> abre em modo DEMONSTRAÇÃO

O modo é decidido pelo NOME do executável: se o nome tiver "demonstra",
liga o modo demo antes de o servidor carregar a configuração.
"""
import os
import sys

if "demonstra" in os.path.basename(sys.executable).lower():
    os.environ.setdefault("CF_MODO_DEMO", "1")

from app.desktop import main

if __name__ == "__main__":
    main()
