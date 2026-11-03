@echo off
rem Instala as bibliotecas do Python SO quando o requirements.txt mudou desde a ultima instalacao.
rem Guarda uma copia do requirements.txt instalado em .venv\requisitos-instalados.txt e compara.
rem Uso (de dentro da pasta backend): call "%RAIZ%\scripts\dependencias.bat"
if exist .venv\requisitos-instalados.txt (
    fc /b requirements.txt .venv\requisitos-instalados.txt >nul 2>&1 && exit /b 0
)
echo Instalando bibliotecas do Python (requirements.txt mudou)...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || exit /b 1
copy /y requirements.txt .venv\requisitos-instalados.txt >nul
exit /b 0
