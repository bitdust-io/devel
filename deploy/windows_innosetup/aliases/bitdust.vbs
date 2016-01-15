Sub SplashScreen(pth)
    Dim shell : Set shell = CreateObject("WScript.Shell")
    Dim fso : Set fso = CreateObject("Scripting.FileSystemObject")
    Dim tempFolder : Set tempFolder = fso.GetSpecialFolder(2)
    Dim SplashName : SplashName = "bitdust-splash.hta"
    Dim tempFile : Set tempFile = tempFolder.CreateTextFile(SplashName)
    tempFile.Writeline "<HTML><HEAD><Title>BitDust</Title>"
    tempFile.Writeline "<HTA:APPLICATION ID=""BitDust"" BORDER=""THIN"" BORDERSTYLE=""NORMAL"" CAPTION=""NO"""
    tempFile.Writeline "INNERBORDER=""NO"" MAXIMIZEBUTTON=""NO"" MINIMIZEBUTTON=""NO"" SHOWINTASKBAR=""NO"""
    tempFile.Writeline "SCROLL=""NO"" SYSMENU=""NO"" SELECTION=""NO"" SINGLEINSTANCE=""YES""></HEAD>"
    tempFile.Writeline "<BODY style=""border: 1px solid black; margin: 0px; padding: 0px;""><CENTER>"
    tempFile.Writeline "<img src=""" & pth & "icons\bitdust128.png"">"
    tempFile.Writeline "<span style=""color: #888; font-size: 12px; font-family: Arial;"">&copy; BitDust, 2015</span>"
    tempFile.Writeline "</CENTER></BODY></HTML>"
    tempFile.Writeline "<SCRIPT LANGUAGE=""VBScript"">"
    tempFile.Writeline "Sub window_onload()"
    tempFile.Writeline "    window.resizeTo 5, 5"
    tempFile.Writeline "    window.moveTo 1, 1"
    tempFile.Writeline "    CenterWindow 130,160"
    tempFile.Writeline "    Self.document.bgColor = ""white"""
    tempFile.Writeline "    idTimer = window.setTimeout(""CloseWindow"", 5000, ""VBScript"")"
    tempFile.Writeline "End Sub"
    tempFile.Writeline "Sub CenterWindow(x,y)"
    tempFile.Writeline "    Dim ileft,itop"
    tempFile.Writeline "    window.resizeTo x,y"
    tempFile.Writeline "    ileft = window.screen.availWidth/2 - x/2"
    tempFile.Writeline "    itop = window.screen.availHeight/2 - y/2"
    tempFile.Writeline "    window.moveTo ileft,itop"
    tempFile.Writeline "End Sub"
    tempFile.Writeline "Sub CloseWindow"
    tempFile.Writeline "    window.clearTimeout(idTimer)"
    tempFile.Writeline "    window.close()"
    tempFile.Writeline "End Sub"
    tempFile.Writeline "</script>"
    tempFile.Close
    shell.Run tempFolder & "\" & SplashName,1,True
    Set shell = Nothing
    Set fso = Nothing
    Set tempFolder = Nothing
    Set SplashName = Nothing
    Set tempFile = Nothing
End Sub

Dim objShell
Set objShell = Wscript.CreateObject("WScript.Shell")

path = WScript.ScriptFullName
path = Left(path,InStrRev(path,"\")-1)
path = Left(path,InStrRev(path,"\"))

Set objArgs = Wscript.Arguments
args = ""
For I = 0 to objArgs.Count-1
    args = args & " " & objArgs(I)
Next

If objArgs.Count > 0 Then
    If objArgs(0) = "show" Then
        SplashScreen(path)
    End If
End If

cmd = """" & path & "python\python.exe"" """ & path & "src\bitdust.py""" & args
objShell.Run cmd, 0, False

Set objShell = Nothing