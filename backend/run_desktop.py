"""Ponto de entrada do app standalone (usado pelo PyInstaller para gerar o .exe).

Abre o Controle Financeiro numa janela nativa, sem navegador.
"""
from app.desktop import main

if __name__ == "__main__":
    main()
