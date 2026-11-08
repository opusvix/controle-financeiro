@echo off
rem Atualizacao automatica usada pelo atalho (abrir.vbs) ao abrir o app.
rem   atualizar_silencioso.bat check  -> so verifica (codigo 10 = ha versao nova), sem baixar nada.
rem   atualizar_silencioso.bat        -> baixa a versao nova e recompila as telas, mostrando o progresso.
rem Nunca mexe nos seus dados: o banco e o .env ficam fora do repositorio.
rem Em qualquer imprevisto (sem internet, sem git, mudanca local), sai sem travar e abre a versao atual.
setlocal
set "RAIZ=%~dp0.."
cd /d "%RAIZ%" 2>nul || exit /b 0

rem So da para atualizar se for um clone do Git com o git instalado.
if not exist ".git" exit /b 0
where git >nul 2>&1 || exit /b 0

git fetch origin main --quiet 2>nul || exit /b 0
for /f "delims=" %%H in ('git rev-parse HEAD 2^>nul') do set "LOCAL=%%H"
for /f "delims=" %%H in ('git rev-parse origin/main 2^>nul') do set "REMOTE=%%H"
if "%LOCAL%"=="%REMOTE%" exit /b 0      rem ja esta na versao mais nova

rem Modo "check": apenas sinaliza que ha versao nova (codigo 10), sem baixar.
if /i "%~1"=="check" exit /b 10

title Atualizando o Controle Financeiro
echo.
echo   Baixando a versao nova do Controle Financeiro. Um momento...
git pull --ff-only --quiet || ( echo   Nao consegui atualizar agora; abrindo a versao atual. & exit /b 0 )

rem Dependencias do Python, se o requirements mudou (so quando ja existe o ambiente).
if exist "%RAIZ%\backend\.venv" (
    pushd "%RAIZ%\backend"
    call "%RAIZ%\scripts\dependencias.bat" >nul 2>&1
    popd
)

rem Dependencias das telas: so reinstala se o package-lock.json mudou.
cd /d "%RAIZ%\frontend" 2>nul || exit /b 0
where npm >nul 2>&1 || exit /b 0
echo   Atualizando as telas...
fc /b package-lock.json node_modules\.lock-instalado.json >nul 2>&1 || (
    call npm ci || exit /b 0
    copy /y package-lock.json node_modules\.lock-instalado.json >nul
)
call npm run build >nul 2>&1
echo   Pronto! Abrindo o Controle Financeiro...
exit /b 0
