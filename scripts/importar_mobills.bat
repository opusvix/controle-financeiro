@echo off
rem Importa o Excel exportado do Mobills. Primeiro SIMULA e mostra o relatorio;
rem so grava se voce confirmar. Pode rodar de novo: o que ja existe nao duplica.
rem Uso: scripts\importar_mobills.bat "D:\caminho\RELATORIO_TRANSACOES.xlsx"
rem    ou arraste o .xlsx (transacoes ou transacoes futuras) em cima deste arquivo.
setlocal
if "%~1"=="" (
    echo Informe o arquivo .xlsx exportado do Mobills ^(ou arraste o arquivo sobre este .bat^).
    pause
    exit /b 1
)
set RAIZ=%~dp0..
cd /d "%RAIZ%\backend"
call "%RAIZ%\scripts\dependencias.bat" || goto erro
.venv\Scripts\python -m app.importacao.mobills "%~1" --simular --saida "%RAIZ%\importacao_simulacao.txt" || goto erro
echo.
set /p OK=Confere com o Mobills? Digite S para gravar de verdade: 
if /i not "%OK%"=="S" (
    echo Nada foi gravado.
    pause
    exit /b 0
)
.venv\Scripts\python -m app.importacao.mobills "%~1" --saida "%RAIZ%\importacao_resultado.txt" || goto erro
echo Pronto. Veja o resultado em importacao_resultado.txt e abra o app.
pause
exit /b 0
:erro
echo Algo deu errado na importacao.
pause
exit /b 1
