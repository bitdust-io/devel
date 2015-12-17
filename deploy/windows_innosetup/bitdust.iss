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
SetupIconFile=.\build\icons\desktop.ico
UsePreviousAppDir=no
WizardImageStretch=no
WizardImageFile=bitdust128.bmp
WizardSmallImageFile=bitdust48.bmp
WizardImageBackColor=$ffffff


[Files]
Source: ".\build\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".\build\bin\{#ProcName}.bat"; DestDir: "{app}\bin"; Flags: ignoreversion

[Messages]
WelcomeLabel1=Welcome to the [name] Setup
WelcomeLabel2=BitDust - is decentralized, secure and anonymous on-line storage, where only the owner has access and absolute control over its data.%n%nOn your computer you store the data that other users uploaded to you via Internet, and you in turn can use the free space on lots remote machines to save your files.%n%nThis creates redundancy, but allows storing important data in a much safer and independent way.%n%nDuring first start of the main program you will be asked to provide an initial storage distribution: your needed and donated storage quotas.%n%nThis will install [name/ver] on your computer.
ReadyLabel2b=Python Interpretator and Git binaries will be installed on your local drive.%n%nBitDust sources will be downloaded from official public repository at http://gitlab.bitdust.io/devel/bitdust.%n%nBitDust program is written in Python using Twisted Framework and is distributed in open source code - we are still deciding about the license type.%n%nClick Install to continue with the installation.

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpReady then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall)
  else
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
end;

[Icons]
Name: "{commondesktop}\{#Name}"; Filename: "{app}\python\pythonw.exe"; WorkingDir: "{app}\src"; Parameters: "bitdust.py show"; Comment: "Launch BitDust software"; IconFilename: "{app}\icons\desktop.ico"
;Name: "{commondesktop}\Start {#Name} in debug mode"; Filename: "{app}\bin\{#ProcName}d.bat"; WorkingDir: "{app}\src"; Parameters: "-d20 show"; Comment: "Launch BitDust software in debug mode"; IconFilename: "{app}\icons\desktop-debug.ico"
;Name: "{commondesktop}\Stop {#Name}"; Filename: "{app}\python\pythonw.exe"; WorkingDir: "{app}\src"; Parameters: "bitdust.py stop"; Comment: "Completely stop BitDust software"; IconFilename: "{app}\icons\desktop-stop.ico"
;Name: "{commondesktop}\Synchronize {#Name} sources"; Filename: "{app}\bin\{#ProcName}sync.bat"; WorkingDir: "{app}\src"; Parameters: ""; Comment: "Synchronize BitDust sources from public repository at http://gitlab.bitdust.io/devel/bitdust/"; IconFilename: "{app}\icons\desktop-sync.ico"
;Name: "{userstartup}\{#Name}"; Filename: ""

[Run]
Filename: "{app}\git\bin\git.exe"; Parameters: "clone --depth=1 http://gitlab.bitdust.io/devel/bitdust.git ."; WorkingDir: "{app}\src"; Description: "Downloading BitDust sources"; StatusMsg: "Downloading BitDust sources with Git: http://gitlab.bitdust.io/devel/bitdust"; Flags: runhidden;
; Flags: runhidden postinstall unchecked;
; Filename: "{app}\git\bin\git.exe"; Parameters: "clone --depth=1 http://gitlab.bitdust.io/devel/bitdust.git ."; WorkingDir: "{app}\src"; Description: "Downloading BitDust sources"; StatusMsg: "Downloading BitDust sources from Git repository at http://gitlab.bitdust.io/devel/bitdust"; Flags: hidewizard postinstall;
Filename: "{app}\python\pythonw.exe"; Parameters: "bitdust.py stop"; WorkingDir: "{app}\src"; Description: "Prepare to start the program"; StatusMsg: "Prepare to start the program ..."; Flags: runhidden;
Filename: "{app}\python\pythonw.exe"; Parameters: "bitdust.py show"; WorkingDir: "{app}\src"; Description: "Starting the main BitDust process"; StatusMsg: "Starting the main BitDust process ..."; Flags: runhidden nowait;
