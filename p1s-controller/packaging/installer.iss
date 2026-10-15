; Inno Setup script. Compile after build_windows.bat has produced dist\P1S Controller.
[Setup]
AppName=P1S Controller
AppVersion=0.1.0
DefaultDirName={autopf}\P1S Controller
DefaultGroupName=P1S Controller
OutputDir=..\dist
OutputBaseFilename=P1S-Controller-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "..\dist\P1S Controller\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\P1S Controller"; Filename: "{app}\P1S Controller.exe"
Name: "{autodesktop}\P1S Controller"; Filename: "{app}\P1S Controller.exe"

[Run]
Filename: "{app}\P1S Controller.exe"; Description: "Launch P1S Controller"; Flags: postinstall nowait skipifsilent
