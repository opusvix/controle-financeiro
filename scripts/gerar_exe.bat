@echo off
rem ============================================================================
rem  GERAR O APLICATIVO (.exe) - rode UMA vez, no Windows, para criar o programa.
rem  Faz tudo sozinho: prepara o Python, as bibliotecas, compila as telas e
rem  empacota o ControleFinanceiro.exe (janela propria, sem navegador).
rem  O usuario final NAO roda isto: ele so recebe o .exe pronto e da dois cliques.
rem ============================================================================
setlocal
set RAIZ=%~dp0..
cd /d "%RAIZ%\backend"

echo [1/4] Preparando o Python...
if not exist .venv (
    python -m venv .venv || goto erro
)
echo [2/4] Instalando as bibliotecas (pode demorar na primeira vez)...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements-desktop.txt || goto erro

echo [3/4] Compilando as telas...
pushd "%RAIZ%\frontend"
call npm ci || goto erro
call npm run build || goto erro
popd

echo [4/4] Empacotando o ControleFinanceiro.exe...
cd /d "%RAIZ%"
backend\.venv\Scripts\pyinstaller --noconfirm --clean controle-financeiro.spec || goto erro

echo.
echo Pronto! Foram gerados DOIS programas na pasta "%RAIZ%\dist":
echo   - ControleFinanceiro.exe             (app normal, dados reais)
echo   - ControleFinanceiro-Demonstracao.exe (abre em modo DEMONSTRACAO, dados ficticios)
echo Entregue o arquivo desejado ao usuario: ele da dois cliques e o app abre numa janela propria.
echo.
pause
goto :eof
:erro
echo.
echo Algo deu errado. Confira se o Python 3.11+ e o Node.js estao instalados.
pause
