@echo off
rem Cria (ou atualiza) o atalho "Controle Financeiro (Demonstracao)" na Area de Trabalho.
rem Abre a demo sem a janela preta do terminal.
set RAIZ=%~dp0..
powershell -NoProfile -Command "$raiz = (Resolve-Path '%RAIZ%').Path; $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Controle Financeiro (Demonstracao).lnk'; $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk); $s.TargetPath = \"$env:WINDIR\System32\wscript.exe\"; $s.Arguments = '\"' + $raiz + '\scripts\demonstracao.vbs\"'; $s.WorkingDirectory = $raiz; $s.IconLocation = $raiz + '\scripts\icone.ico,0'; $s.Description = 'Controle Financeiro - Demonstracao'; $s.Save(); 'Atalho criado em ' + $lnk"
pause
