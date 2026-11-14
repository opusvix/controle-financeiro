@echo off
rem ============================================================================
rem  GERAR O APLICATIVO (.exe) - rode UMA vez, no Windows, para criar o programa.
rem  Faz tudo sozinho: atualiza o codigo (git pull no main), prepara o Python,
rem  as bibliotecas, compila as telas e empacota o ControleFinanceiro.exe
rem  (janela propria, sem navegador).
rem  O usuario final NAO roda isto: ele so recebe o .exe pronto e da dois cliques.
rem ============================================================================
setlocal
set RAIZ=%~dp0..

rem A 1a passada atualiza o codigo (git pull) e RELANCA o script ja atualizado
rem com /continuar; a 2a passada pula o pull e vai direto para o build. Assim o
rem build nunca roda com uma versao do proprio script que acabou de mudar.
if "%~1"=="/continuar" goto build

cd /d "%RAIZ%"
set BRANCH=
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%b
if /i "%BRANCH%"=="main" (
    echo [1/5] Atualizando o codigo ^(git pull no main^)...
    git pull --ff-only
    if errorlevel 1 echo     Aviso: nao deu pra atualizar agora - seguindo com o codigo que esta no PC.
) else (
    echo [1/5] Branch atual "%BRANCH%" nao e main - pulando o git pull.
)
call "%~f0" /continuar
exit /b %errorlevel%

:build
cd /d "%RAIZ%\backend"
echo [2/5] Preparando o Python...
if not exist .venv (
    python -m venv .venv || goto erro
)
echo [3/5] Instalando as bibliotecas (pode demorar na primeira vez)...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements-desktop.txt || goto erro

echo [4/5] Compilando as telas...
pushd "%RAIZ%\frontend"
call npm ci || goto erro
call npm run build || goto erro
popd

echo [5/5] Empacotando o ControleFinanceiro.exe...
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
