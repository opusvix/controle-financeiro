@echo off
rem Liga a leitura de cupom por FOTO (OCR local, gratis e offline).
rem Rode uma vez. Depois e so mandar a foto ou o PDF do pedido na tela Cupons.
set RAIZ=%~dp0..
cd /d "%RAIZ%\backend"
if not exist .venv (
    echo Primeiro abra o app uma vez pelo atalho, para preparar o Python. & pause & exit /b 1
)
echo Instalando o pacote de OCR (pode levar alguns minutos na primeira vez)...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements-ocr.txt || goto erro
echo.
echo Pronto! A leitura de cupom por foto esta ligada. Abra a tela Cupons e mande a foto.
pause
exit /b 0
:erro
echo.
echo Nao consegui instalar o pacote de OCR. Confira a conexao com a internet (so e preciso nesta instalacao).
pause
exit /b 1
