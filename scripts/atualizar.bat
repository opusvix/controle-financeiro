@echo off
rem Baixa a versao mais nova do GitHub e recompila as telas.
set RAIZ=%~dp0..
cd /d "%RAIZ%"
git pull || goto erro
cd backend
if exist .venv .venv\Scripts\python -m pip install -q -r requirements.txt
cd ..\frontend
call npm ci || goto erro
call npm run build || goto erro
echo Pronto. Abra de novo com iniciar.bat
pause
goto :eof
:erro
echo Algo deu errado na atualizacao.
pause
