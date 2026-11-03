@echo off
rem Desliga o Controle Financeiro que esta rodando escondido.
rem Pega quem escuta na porta 8000 e tambem qualquer Python rodando "-m app" (o servidor do app),
rem para nao sobrar servidor antigo ligado depois de atualizar.
powershell -NoProfile -Command "$p = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess); $p += @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -match ' -m app' } | Select-Object -ExpandProperty ProcessId); $p = $p | Where-Object { $_ } | Sort-Object -Unique; if ($p) { $p | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; 'Controle Financeiro desligado.' } else { 'O Controle Financeiro nao estava ligado.' }"
if /i not "%1"=="/q" pause
