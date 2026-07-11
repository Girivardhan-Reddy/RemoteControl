[Setup]
AppName=Remote Control Agent
AppVersion=1.0.0
DefaultDirName={pf}\Remote Control Agent
DefaultGroupName=Remote Control Agent
OutputBaseFilename=RemoteControlSetup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=resources\icons\app_icon.ico

[Files]
Source: "dist\RemoteControlAgent.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{commondesktop}\Remote Control Agent"; Filename: "{app}\RemoteControlAgent.exe"
Name: "{group}\Remote Control Agent"; Filename: "{app}\RemoteControlAgent.exe"

[Run]
Filename: "{app}\RemoteControlAgent.exe"; Description: "Launch Remote Control Agent"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Remote Control Agent"; ValueData: """{app}\RemoteControlAgent.exe"""; Flags: uninsdeletevalue
