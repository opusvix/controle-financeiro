@echo off
rem Liga o Controle Financeiro e abre no navegador.
rem Na primeira vez, cria o ambiente Python e instala as dependências.
cd /d "%~dp0..\backend"
if not exist .venv (
    echo Preparando o ambiente pela primeira vez...
    python -m venv .venv || goto erro
    .venv\Scripts\python -m pip install -q -r requirements.txt || goto erro
)
start "" http://127.0.0.1:8000/docs
.venv\Scripts\python -m app
goto :eof
:erro
echo Algo deu errado. Confira se o Python 3.11+ esta instalado.
pause
