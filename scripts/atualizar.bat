@echo off
rem Baixa a versao mais nova do GitHub e recompila as telas.
set RAIZ=%~dp0..
cd /d "%RAIZ%"
rem Desliga o app se estiver rodando escondido, para ele voltar com a versao nova.
call "%RAIZ%\scripts\parar.bat" /q
git pull || goto erro
cd backend
if exist .venv call "%RAIZ%\scripts\dependencias.bat" || goto erro
cd ..\frontend
rem So reinstala os pacotes das telas se o package-lock.json mudou.
fc /b package-lock.json node_modules\.lock-instalado.json >nul 2>&1 || (
    call npm ci || goto erro
    copy /y package-lock.json node_modules\.lock-instalado.json >nul
)
call npm run build || goto erro
echo Pronto. Abra de novo pelo atalho da Area de Trabalho (ou abrir.vbs).
pause
goto :eof
:erro
echo Algo deu errado na atualizacao.
pause
