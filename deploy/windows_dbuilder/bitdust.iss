#define   Name       "BitDust"
#define   ProcName   "bitdust"
#define   Publisher  "BitDust"
#define   URL        "http://www.bitdust.io"
#define   ExeName    "{#ProcName}.bat"
#define   DestDir    "{%HOMEDRIVE}{%HOMEPATH}"

#define VerFile FileOpen("../version")
#define Version FileRead(VerFile)
#expr FileClose(VerFile)
#undef VerFile

[Setup]
AppId={{94F29201-B980-4051-BC56-CDB759228B40}}
AppName={#Name}
AppVersion={#Version}
AppPublisher={#Publisher}
AppPublisherURL={#URL}
AppSupportURL={#URL}
AppUpdatesURL={#URL}
DefaultDirName={#DestDir}\.{#ProcName}
OutputDir=.\dist
OutputBaseFileName={#ProcName}-setup
Compression=lzma
SolidCompression=yes
DisableDirPage=yes
;DisableReadyPage=yes
DisableProgramGroupPage=yes
SetupIconFile=.\build\src\icons\desktop.ico
UsePreviousAppDir=no

[Files]
Source: ".\build\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".\build\bin\{#ProcName}.bat"; DestDir: "{app}\bin"; Flags: ignoreversion

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpReady then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall)
  else
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
end;

[Icons]
Name: "{commondesktop}\Start {#Name}"; Filename: "{app}\python\pythonw.exe"; WorkingDir: "{app}\src"; Parameters: "bitdust.py show"; Comment: "Launch BitDust software"; IconFilename: "{app}\src\icons\desktop.ico"
;Name: "{commondesktop}\Start {#Name}"; Filename: "{app}\bin\{#ProcName}.bat"; WorkingDir: "{app}\src"; Parameters: "show"; Comment: "Launch BitDust software"; IconFilename: "{app}\src\icons\desktop.ico"
Name: "{commondesktop}\Start {#Name} in debug mode"; Filename: "{app}\bin\{#ProcName}d.bat"; WorkingDir: "{app}\src"; Parameters: "-d20 show"; Comment: "Launch BitDust software in debug mode"; IconFilename: "{app}\src\icons\desktop-debug.ico"
;Name: "{commondesktop}\Stop {#Name}"; Filename: "{app}\bin\{#ProcName}.bat"; WorkingDir: "{app}\src"; Parameters: "stop"; Comment: "Completely stop BitDust software"; IconFilename: "{app}\src\icons\desktop-stop.ico"
Name: "{commondesktop}\Stop {#Name}"; Filename: "{app}\python\pythonw.exe"; WorkingDir: "{app}\src"; Parameters: "bitdust.py stop"; Comment: "Completely stop BitDust software"; IconFilename: "{app}\src\icons\desktop-stop.ico"

