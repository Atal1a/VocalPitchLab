#ifndef UpdateDir
  #error UpdateDir required
#endif
#ifndef AppVersion
  #error AppVersion required
#endif
#ifndef FromVersion
  #error FromVersion required
#endif
#ifndef AppIdentity
  #define AppIdentity "VocalPitchLab.LocalPreview"
#endif
[Setup]
AppId={#AppIdentity}
AppName=VocalPitchLab
AppVersion={#AppVersion}
AppPublisher=VocalPitchLab
VersionInfoDescription=VocalPitchLab 更新程序
DefaultDirName={localappdata}\Programs\VocalPitchLab
DefaultGroupName=VocalPitchLab
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UsePreviousAppDir=yes
UsePreviousGroup=yes
OutputDir={#UpdateDir}
OutputBaseFilename=VocalPitchLab-{#AppVersion}-windows-x64-update-from-{#FromVersion}
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=..\assets\vocalpitch.ico
UninstallDisplayIcon={app}\assets\vocalpitch.ico
#ifdef InstalledSize
UninstallDisplaySize={#InstalledSize}
#endif
LicenseFile=..\LICENSE
WizardStyle=modern
ShowLanguageDialog=no
LanguageDetectionMethod=none
UsePreviousLanguage=no
DisableProgramGroupPage=yes
CloseApplications=no
RestartApplications=no
SetupMutex=VocalPitchLab.Update
CreateUninstallRegKey=not IsPackageValidation
Uninstallable=not IsPackageValidation
[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
[Files]
Source: "{#UpdateDir}\checks.tsv"; Flags: dontcopy
Source: "{#UpdateDir}\removed.tsv"; Flags: dontcopy
Source: "{#UpdateDir}\changed.txt"; Flags: dontcopy
#include UpdateDir + "\files.iss"
[Code]
#include "update_guard.iss"
