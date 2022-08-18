[Setup]
AppName=Tornado Bismuth Wallet
AppVersion=0.1x
DefaultDirName={pf}\TornadoWallet
DefaultGroupName=Tornado Bismuth Wallet
UninstallDisplayIcon={app}\TornadoBismuthWallet.exe
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=TornadoWallet_setup
SetupIconFile=favicon.ico
DisableDirPage=no

;WizardImageFile=graphics\left.bmp
;WizardSmallImageFile=graphics\mini.bmp

[Files]
Source: "dist\*" ; DestDir: "{app}"; Flags: recursesubdirs;

[Icons]
Name: "{group}\Tornado Bismuth Wallet"; Filename: "{app}\TornadoBismuthWallet.exe"
Name: "{group}\Uninstall Tornado Bismuth Wallet"; Filename: "{uninstallexe}"

Name: "{commondesktop}\Tornado Bismuth Wallet"; Filename: "{app}\TornadoBismuthWallet.exe"

[Registry]
; keys for 64-bit systems
Root: HKCU32; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; ValueType: String; ValueName: "{app}\TornadoBismuthWallet.exe"; ValueData: "RUNASADMIN"; Flags: uninsdeletekeyifempty uninsdeletevalue; Check: not IsWin64
Root: HKLM32; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; ValueType: String; ValueName: "{app}\TornadoBismuthWallet.exe"; ValueData: "RUNASADMIN"; Flags: uninsdeletekeyifempty uninsdeletevalue; Check: not IsWin64

; keys for 64-bit systems
Root: HKCU64; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; ValueType: String; ValueName: "{app}\TornadoBismuthWallet.exe"; ValueData: "RUNASADMIN"; Flags: uninsdeletekeyifempty uninsdeletevalue; Check: IsWin64
Root: HKLM64; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; ValueType: String; ValueName: "{app}\TornadoBismuthWallet.exe"; ValueData: "RUNASADMIN"; Flags: uninsdeletekeyifempty uninsdeletevalue; Check: IsWin64

[Run]
Filename: "{app}\TornadoBismuthWallet.exe"; Description: "Tornado Bismuth Wallet"; Flags: shellexec postinstall skipifsilent unchecked