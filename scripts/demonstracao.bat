@echo off
rem Abre a VERSAO DE DEMONSTRACAO: dados ficticios, banco separado (data\demo),
rem na porta 8001 para rodar ao lado do app normal sem conflito.
rem Nao toca nos seus dados reais.
set RAIZ=%~dp0..
cd /d "%RAIZ%\backend"
if not exist .venv (
    echo Rode primeiro o scripts\iniciar.bat uma vez ^(prepara o Python e as telas^).
    pause
    goto :eof
)
if not exist "%RAIZ%\frontend\dist\index.html" (
    echo Rode primeiro o scripts\iniciar.bat uma vez ^(compila as telas^).
    pause
    goto :eof
)
set CF_MODO_DEMO=1
set CF_PORT=8001
set CF_PASTA_DADOS=%RAIZ%\data\demo
start "" http://127.0.0.1:8001/
.venv\Scripts\python -m app
