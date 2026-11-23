; Instalador de PPF Tester (Inno Setup 6)
; Compilar:  ISCC.exe /DMyAppVersion=3.2.0 installer.iss   (después de python build.py)
; Desarrollado por Angel Cm - https://angelcm.com

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "PPF Tester"
#define MyAppExe "PPF-Tester.exe"

[Setup]
AppId={{6F3B2A71-9C4E-4F1D-8B2A-5E7C0D9A1F24}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Angel Cm
AppPublisherURL=https://angelcm.com
AppSupportURL=https://github.com/angel-cm-dev/ppf-tester/issues
AppUpdatesURL=https://github.com/angel-cm-dev/ppf-tester/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; instalación por usuario (sin permisos de administrador); así la app puede actualizarse sola
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=PPF-Tester-Setup-v{#MyAppVersion}
SetupIconFile=ppf_tester\ppf_tester.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
LicenseFile=LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
spanish.AssocPpf=Añadir PPF Tester a «Abrir con» para archivos .ppf
english.AssocPpf=Add PPF Tester to "Open with" for .ppf files
brazilianportuguese.AssocPpf=Adicionar o PPF Tester ao «Abrir com» para arquivos .ppf
spanish.AssocGroup=Archivos:
english.AssocGroup=Files:
brazilianportuguese.AssocGroup=Arquivos:

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "{cm:AssocPpf}"; GroupDescription: "{cm:AssocGroup}"

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; DestName: "LEEME.md"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Se añade a «Abrir con» sin quitarle .ppf a Yamaha Expansion Manager
Root: HKA; Subkey: "Software\Classes\.ppf\OpenWithProgids"; ValueType: string; ValueName: "PPFTester.ppf"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\PPFTester.ppf"; ValueType: string; ValueName: ""; ValueData: "Kit de Yamaha Expansion Manager"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\PPFTester.ppf\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExe},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\PPFTester.ppf\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\SupportedTypes"; ValueType: string; ValueName: ".ppf"; ValueData: ""; Flags: uninsdeletekey; Tasks: assoc

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
