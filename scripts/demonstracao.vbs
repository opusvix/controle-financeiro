' Abre a VERSAO DE DEMONSTRACAO sem a janela preta do terminal.
' Dados ficticios, banco separado (data\demo), na porta 8001 - roda ao lado
' do app normal e NUNCA toca nos seus dados reais.
' Para desligar a demo: scripts\parar.bat (fecha o python).
Option Explicit
Dim sh, fs, raiz, url, env, i
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
raiz = fs.GetParentFolderName(fs.GetParentFolderName(WScript.ScriptFullName))
url = "http://127.0.0.1:8001/"

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

' Sem o app preparado ainda: peca para rodar o iniciar.bat uma vez.
If Not fs.FileExists(raiz & "\backend\.venv\Scripts\python.exe") Or _
   Not fs.FileExists(raiz & "\frontend\dist\index.html") Then
  MsgBox "Rode o scripts\iniciar.bat uma vez (prepara o Python e as telas)." & vbCrLf & _
    "Depois a demonstracao abre normalmente.", vbInformation, "Controle Financeiro - Demonstracao"
  WScript.Quit
End If

' Liga o servidor em modo demo, escondido. Os processos filhos herdam estas variaveis.
Set env = sh.Environment("Process")
env("CF_MODO_DEMO") = "1"
env("CF_PORT") = "8001"
env("CF_PASTA_DADOS") = raiz & "\data\demo"
sh.CurrentDirectory = raiz & "\backend"
sh.Run "cmd /c "".venv\Scripts\python.exe -m app > ""%TEMP%\controle-financeiro-demo.log"" 2>&1""", 0, False

For i = 1 To 40
  WScript.Sleep 500
  If Ligado() Then
    sh.Run url
    WScript.Quit
  End If
Next
MsgBox "A demonstracao nao respondeu em 20 segundos." & vbCrLf & _
  "Veja o arquivo %TEMP%\controle-financeiro-demo.log para o motivo.", vbExclamation, _
  "Controle Financeiro - Demonstracao"
