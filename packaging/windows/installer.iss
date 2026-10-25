; =====================================================================
; Sengoku Basara 4 Sumeragi — Inno Setup 6 Script
; Non-Administrative (Per-User) Portable Game & Launcher Installer
; =====================================================================

#ifndef AppVersion
#define AppVersion "1.0-update3"
#endif

[Setup]
AppId={{6B52A74F-4C82-4C9D-998E-D9F5796E2E10}
AppName=Basara 4 PC
AppVersion={#AppVersion}
AppPublisher=Sengoku Basara 4 Sumeragi PC Preservation Team
AppPublisherURL=https://github.com/krixsan/Basara-4-Sumeragi-Native-PC
AppSupportURL=https://github.com/krixsan/Basara-4-Sumeragi-Native-PC/issues
DefaultDirName={localappdata}\Programs\Basara4Sumeragi
DefaultGroupName=Basara 4 Sumeragi PC
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE.txt
OutputDir=..\..\dist
OutputBaseFilename=Basara4_Sumeragi_PC_Setup_v{#AppVersion}
SetupIconFile=icons\basara4.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\packaging\windows\icons\basara4.ico
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Primary Executables & Launchers
Source: "..\..\basara_pc.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\Basara4_Launcher.exe"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\..\..\Basara4_Launcher.exe'))
Source: "..\..\launcher.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\Play_Basara4.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\basara4-pad-mapper.exe"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\..\..\basara4-pad-mapper.exe'))

; Runtime Open-Source DLLs
Source: "..\..\*.dll"; DestDir: "{app}"; Flags: ignoreversion

; Configuration & Documentation
Source: "..\..\basara.ini"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.id.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\THIRD_PARTY_LICENSES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\PRIVACY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

; Assets & Icons
Source: "icons\basara4.ico"; DestDir: "{app}\packaging\windows\icons"; Flags: ignoreversion
Source: "basara.manifest"; DestDir: "{app}\packaging\windows"; Flags: ignoreversion
Source: "launcher.manifest"; DestDir: "{app}\packaging\windows"; Flags: ignoreversion

[Dirs]
; Ensure user directory exists for configurations, screenshots, logs, and dumps
Name: "{app}\user"; Permissions: everyone-modify

[Icons]
Name: "{group}\Basara 4 Sumeragi"; Filename: "{app}\Basara4_Launcher.exe"; IconFilename: "{app}\packaging\windows\icons\basara4.ico"
Name: "{group}\Sengoku Basara 4 (Engine Direct)"; Filename: "{app}\basara_pc.exe"; IconFilename: "{app}\packaging\windows\icons\basara4.ico"
Name: "{group}\Uninstall Basara 4 PC"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Basara 4 Sumeragi"; Filename: "{app}\Basara4_Launcher.exe"; IconFilename: "{app}\packaging\windows\icons\basara4.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Basara4_Launcher.exe"; Description: "{cm:LaunchProgram,Basara 4 Sumeragi}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up application files but strictly PRESERVE user save data, logs, screenshots, and crashes
Type: files; Name: "{app}\basara_pc.exe"
Type: files; Name: "{app}\Basara4_Launcher.exe"
Type: files; Name: "{app}\basara4-pad-mapper.exe"
Type: files; Name: "{app}\launcher.py"
Type: files; Name: "{app}\Play_Basara4.bat"
Type: files; Name: "{app}\*.dll"
Type: files; Name: "{app}\*.md"
Type: files; Name: "{app}\*.txt"
Type: filesandordirs; Name: "{app}\packaging"
Type: filesandordirs; Name: "{app}\dist"
Type: filesandordirs; Name: "{app}\scripts"
