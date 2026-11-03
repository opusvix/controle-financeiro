@echo off
rem Le os PDFs das contas da casa (luz por enquanto) e grava a ficha de cada fatura
rem no lancamento ja pago: consumo, creditos da Solar, bandeira, iluminacao publica, multa.
rem Primeiro SIMULA; so grava se voce confirmar. Pode rodar de novo sem duplicar.
rem Uso: dois cliques (le ..\Contas\2026) ou arraste uma pasta de PDFs sobre este arquivo.
setlocal
set RAIZ=%~dp0..
set PASTA=%~1
if "%PASTA%"=="" set PASTA=%RAIZ%\..\Contas\2026
cd /d "%RAIZ%\backend"
.venv\Scripts\python -m pip install -q -r requirements.txt
.venv\Scripts\python -m app.importacao.contas_pdf "%PASTA%" --simular || goto erro
echo.
set /p OK=Digite S para gravar as fichas: 
if /i not "%OK%"=="S" (
    echo Nada foi gravado.
    pause
    exit /b 0
)
.venv\Scripts\python -m app.importacao.contas_pdf "%PASTA%" --saida "%RAIZ%\contas_resultado.txt" || goto erro
echo Pronto. Abra o app: as contas de luz ganharam a ficha.
pause
exit /b 0
:erro
echo Algo deu errado na leitura dos PDFs.
pause
exit /b 1
