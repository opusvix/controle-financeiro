@echo off
rem Le os PDFs das contas da casa (luz: EDP Escelsa e EDP Solar) e grava a ficha de cada fatura
rem no lancamento ja pago: consumo, creditos da Solar, bandeira, iluminacao publica, multa.
rem Primeiro SIMULA; so grava se voce confirmar. Pode rodar de novo sem duplicar.
rem Uso: dois cliques (le ..\Contas\2026) ou arraste uma pasta de PDFs sobre este arquivo.
rem PDFs com senha (EDP Solar): a senha e pedida aqui, escondida, e nao fica gravada.
setlocal
set RAIZ=%~dp0..
set PASTA=%~1
if "%PASTA%"=="" set PASTA=%RAIZ%\..\Contas\2026
cd /d "%RAIZ%\backend"
echo Se houver PDFs com senha (ex.: EDP Solar), digite a senha. Enter para pular.
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$s = Read-Host 'Senha dos PDFs' -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"`) do set "CF_SENHA_PDF=%%p"
.venv\Scripts\python -m pip install -q -r requirements.txt
.venv\Scripts\python -m app.importacao.contas_pdf "%PASTA%" --simular --diagnostico || goto erro
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
