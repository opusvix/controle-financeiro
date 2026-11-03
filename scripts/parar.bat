@echo off
rem Desliga o Controle Financeiro que esta rodando escondido (porta 8000).
powershell -NoProfile -Command "$p = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($p) { $p | ForEach-Object { Stop-Process -Id $_ -Force }; 'Controle Financeiro desligado.' } else { 'O Controle Financeiro nao estava ligado.' }"
if /i not "%1"=="/q" pause
