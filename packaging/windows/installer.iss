; Inno Setup script. CI invokes:  iscc /DAppVersion=x.y.z packaging\windows\installer.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7B7E3F86-1D51-4E1C-9C86-2A41F0D6B7E3}
AppName=WebTunes Importer
AppVersion={#AppVersion}
AppPublisher=Matteo Bombelli
AppPublisherURL=https://matteob.dev/projects/webtunes
DefaultDirName={autopf}\WebTunes Importer
DefaultGroupName=WebTunes Importer
DisableProgramGroupPage=yes
OutputBaseFilename=WebTunes-Importer-Setup-x64
OutputDir=..\..\dist
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\webtunes-importer.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\webtunes-importer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WebTunes Importer"; Filename: "{app}\webtunes-importer.exe"
Name: "{autodesktop}\WebTunes Importer"; Filename: "{app}\webtunes-importer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\webtunes-importer.exe"; Description: "{cm:LaunchProgram,WebTunes Importer}"; Flags: nowait postinstall skipifsilent
