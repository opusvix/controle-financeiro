@echo off
rem Traz as faturas de cartao do Mobills (RELATORIO_CARTOES_*.xlsx).
rem Primeiro SIMULA e mostra o relatorio; so grava se voce confirmar.
rem Uso: scripts\importar_cartoes_mobills.bat "D:\caminho\RELATORIO_CARTOES.xlsx"
setlocal
if "%~1"=="" (
    echo Informe o arquivo .xlsx de cartoes exportado do Mobills.
    exit /b 1
)
set RAIZ=%~dp0..
cd /d "%RAIZ%\backend"
.venv\Scripts\python -m app.importacao.mobills_cartoes "%~1" --simular --saida "%RAIZ%\cartoes_simulacao.txt" || goto erro
echo.
set /p OK=Os saldos ficaram iguais e as faturas conferem? Digite S para gravar: 
if /i not "%OK%"=="S" (
    echo Nada foi gravado.
    exit /b 0
)
.venv\Scripts\python -m app.importacao.mobills_cartoes "%~1" --saida "%RAIZ%\cartoes_resultado.txt" || goto erro
echo Pronto. Abra o app em Cartoes de credito.
exit /b 0
:erro
echo Algo deu errado na importacao.
exit /b 1
