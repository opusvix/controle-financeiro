@echo off
rem Traz as faturas de cartao do Mobills (RELATORIO_CARTOES_*.xlsx).
rem Pode dar dois cliques: sem arquivo informado, usa o RELATORIO_CARTOES_*.xlsx
rem mais recente da pasta ControleFinanceiro. Primeiro SIMULA; so grava com S.
setlocal
set RAIZ=%~dp0..
set ARQ=%~1
if "%ARQ%"=="" (
    for /f "delims=" %%F in ('dir /b /o:d "%RAIZ%\..\RELATORIO_CARTOES_*.xlsx" 2^>nul') do set ARQ=%RAIZ%\..\%%F
)
if "%ARQ%"=="" (
    echo Nao achei nenhum RELATORIO_CARTOES_*.xlsx na pasta ControleFinanceiro.
    goto fim
)
echo Arquivo: %ARQ%
echo.
cd /d "%RAIZ%\backend"
.venv\Scripts\python -m app.importacao.mobills_cartoes "%ARQ%" --simular --saida "%RAIZ%\cartoes_simulacao.txt" || goto erro
echo.
set /p OK=Os saldos ficaram iguais e as faturas conferem? Digite S para gravar: 
if /i not "%OK%"=="S" (
    echo Nada foi gravado.
    goto fim
)
.venv\Scripts\python -m app.importacao.mobills_cartoes "%ARQ%" --saida "%RAIZ%\cartoes_resultado.txt" || goto erro
echo.
echo Pronto. Abra o app em Cartoes de credito.
goto fim
:erro
echo Algo deu errado na importacao.
:fim
echo.
pause
