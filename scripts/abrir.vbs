' Abre o Controle Financeiro SEM a janela preta do terminal.
' - Se o app ja esta ligado, so abre o navegador.
' - Na primeira vez (falta preparar Python ou compilar as telas), usa o iniciar.bat visivel,
'   para voce acompanhar a instalacao.
' - Senao, liga o servidor escondido, espera ele responder e abre o navegador.
' Para desligar: scripts\parar.bat
Option Explicit
Dim sh, fs, raiz, url, i
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
raiz = fs.GetParentFolderName(fs.GetParentFolderName(WScript.ScriptFullName))
url = "http://127.0.0.1:8000/"

Function Ligado()
  On Error Resume Next
  Dim http : Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
  http.setTimeouts 1000, 1000, 1000, 1000
  http.Open "GET", url & "api/saude", False
  http.Send
  Ligado = (Err.Number = 0 And http.Status = 200)
End Function

If Ligado() Then
  sh.Run url
  WScript.Quit
End If

If Not fs.FileExists(raiz & "\backend\.venv\Scripts\python.exe") Or _
   Not fs.FileExists(raiz & "\frontend\dist\index.html") Then
  sh.Run """" & raiz & "\scripts\iniciar.bat""", 1, False
  WScript.Quit
End If

' Atualizacao automatica: verifica (rapidinho e sem janela) se ha versao nova no GitHub.
' So quando houver, roda a atualizacao mostrando o progresso; senao, abre direto.
Dim rc
rc = sh.Run("cmd /c """ & raiz & "\scripts\atualizar_silencioso.bat"" check", 0, True)
If rc = 10 Then
  sh.Run "cmd /c """ & raiz & "\scripts\atualizar_silencioso.bat""", 1, True
End If

' 0 = janela escondida. O registro do servidor vai para %TEMP%\controle-financeiro.log
sh.CurrentDirectory = raiz & "\backend"
sh.Run "cmd /c "".venv\Scripts\python.exe -m app > ""%TEMP%\controle-financeiro.log"" 2>&1""", 0, False

For i = 1 To 30
  WScript.Sleep 500
  If Ligado() Then
    sh.Run url
    WScript.Quit
  End If
Next
MsgBox "O Controle Financeiro nao respondeu em 15 segundos." & vbCrLf & _
  "Tente abrir pelo scripts\iniciar.bat para ver a mensagem de erro.", vbExclamation, "Controle Financeiro"
