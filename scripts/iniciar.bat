@echo off
rem Liga o Controle Financeiro e abre no navegador.
rem Na primeira vez prepara o Python e compila as telas (alguns minutos).
set RAIZ=%~dp0..
cd /d "%RAIZ%\backend"
if not exist .venv (
    echo Preparando o Python pela primeira vez...
    python -m venv .venv || goto erro
    call "%RAIZ%\scripts\dependencias.bat" || goto erro
)
if not exist "%RAIZ%\frontend\dist\index.html" (
    echo Compilando as telas pela primeira vez...
    pushd "%RAIZ%\frontend"
    call npm ci || goto erro
    copy /y package-lock.json node_modules\.lock-instalado.json >nul
    call npm run build || goto erro
    popd
)
start "" http://127.0.0.1:8000/
.venv\Scripts\python -m app
goto :eof
:erro
echo Algo deu errado. Confira se o Python 3.11+ e o Node.js estao instalados.
pause
