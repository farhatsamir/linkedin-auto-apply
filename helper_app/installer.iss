[Setup]
AppId={{B4F1A2C3-7E5D-4A8B-9C2F-1D3E5F7A9B1C}}
AppName=LinkedIn Auto Apply Helper
AppVersion=1.0.0
AppPublisher=LinkedIn Auto Apply
DefaultDirName={autopf}\LinkedInAutoApplyHelper
DefaultGroupName=LinkedIn Auto Apply Helper
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=LinkedInAutoApplyHelper-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\LinkedInAutoApplyHelper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LinkedIn Auto Apply Helper"; Filename: "{app}\LinkedInAutoApplyHelper.exe"
Name: "{autodesktop}\LinkedIn Auto Apply Helper"; Filename: "{app}\LinkedInAutoApplyHelper.exe"

[Registry]
Root: HKCU; Subkey: "Software\Classes\linkedinautoapply"; ValueType: string; ValueName: ""; ValueData: "URL:LinkedIn Auto Apply Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\linkedinautoapply"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\linkedinautoapply\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\LinkedInAutoApplyHelper.exe"" ""%1"""