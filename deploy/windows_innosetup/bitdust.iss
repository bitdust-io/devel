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
AppMutex=BitDust
DefaultDirName={#DestDir}\.{#ProcName}
OutputDir=.\dist
OutputBaseFileName={#ProcName}-setup
Compression=lzma
SolidCompression=yes
DisableDirPage=yes
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
ReadyLabel2b=Python Interpretator and Git binaries will be installed on your local drive.%n%nBitDust sources will be downloaded from official public repository at http://gitlab.bitdust.io/stable/bitdust.latest%n%nBitDust program is written in Python using Twisted Framework and is distributed in open source code - we are still deciding about the license type.%n%nClick Install to continue with the installation.

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpReady then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall)
  else if CurPageID = wpFinished then
    WizardForm.NextButton.Caption := '&Finish'
  else
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
end;

[Icons]
Name: "{commondesktop}\{#Name}"; Filename: "{app}\bin\bitdust.vbs"; WorkingDir: "{app}\src"; Parameters: "show"; Comment: "Start BitDust"; IconFilename: "{app}\icons\desktop.ico"

[Registry]
Root: "HKCU"; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#Name}"; ValueData: "{app}\bin\bitdust.vbs"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\git\bin\git.exe"; Parameters: "clone --depth=1 http://gitlab.bitdust.io/stable/bitdust.latest.git ."; WorkingDir: "{app}\src"; Description: "Downloading BitDust sources"; StatusMsg: "Downloading BitDust sources with Git: http://gitlab.bitdust.io/stable/bitdust.latest"; Flags: runhidden;
Filename: "{app}\bin\bitdust.vbs"; Parameters: "show"; WorkingDir: "{app}\src"; Description: "Start BitDust"; StatusMsg: "Start BitDust"; Flags: postinstall runhidden nowait shellexec;