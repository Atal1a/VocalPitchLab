#ifndef StageDir
  #error StageDir must point to a prepared application directory
#endif
#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
[Setup]
; Preserve installation identity so earlier local versions upgrade in place.
AppId=VocalPitchLab.LocalPreview
AppName=VocalPitchLab
AppVersion={#AppVersion}
AppPublisher=VocalPitchLab
VersionInfoDescription=VocalPitchLab Setup
DefaultDirName={localappdata}\Programs\VocalPitchLab
DefaultGroupName=VocalPitchLab
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#ifdef GithubAssets
OutputDir=..\dist\VocalPitchLab-{#AppVersion}-windows-x64
#else
OutputDir=..\dist
#endif
OutputBaseFilename=VocalPitchLab-{#AppVersion}-windows-x64-setup
Compression=lzma2/fast
SolidCompression=no
#ifdef GithubAssets
DiskSpanning=yes
DiskSliceSize=1500000000
#endif
SetupIconFile=..\assets\vocalpitch.ico
UninstallDisplayIcon={app}\assets\vocalpitch.ico
LicenseFile=..\LICENSE
WizardStyle=modern
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; Flags: unchecked
[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\VocalPitchLab"; Filename: "{app}\VocalPitchLab.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\vocalpitch.ico"; AppUserModelID: "VocalPitchLab.Desktop"
Name: "{autodesktop}\VocalPitchLab"; Filename: "{app}\VocalPitchLab.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\vocalpitch.ico"; AppUserModelID: "VocalPitchLab.Desktop"; Tasks: desktopicon
; User library/cache lives outside {app}; uninstall never deletes songs.

#include "vc_redist.iss"
