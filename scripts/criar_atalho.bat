@echo off
rem Cria (ou atualiza) o atalho "Controle Financeiro" na Area de Trabalho, com o icone do app.
rem O atalho abre o app sem a janela preta do terminal.
set RAIZ=%~dp0..
powershell -NoProfile -Command "$raiz = (Resolve-Path '%RAIZ%').Path; $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Controle Financeiro.lnk'; $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk); $s.TargetPath = \"$env:WINDIR\System32\wscript.exe\"; $s.Arguments = '\"' + $raiz + '\scripts\abrir.vbs\"'; $s.WorkingDirectory = $raiz; $s.IconLocation = $raiz + '\scripts\icone.ico,0'; $s.Description = 'Controle Financeiro'; $s.Save(); 'Atalho criado em ' + $lnk"
pause
