#ifndef StageDir
  #error StageDir must point to a prepared application directory
#endif
#ifndef AppVersion
  #define AppVersion "1.1.1"
#endif
#ifndef CompressionProfile
  #define CompressionProfile "ultra64-solid"
#endif
#if CompressionProfile == "fast"
  #define CompressionMethod "lzma2/fast"
  #define SolidMode "no"
#elif CompressionProfile == "max"
  #define CompressionMethod "lzma2/max"
  #define SolidMode "no"
#elif CompressionProfile == "max-solid"
  #define CompressionMethod "lzma2/max"
  #define SolidMode "yes"
#elif CompressionProfile == "ultra64-solid"
  #define CompressionMethod "lzma2/ultra64"
  #define SolidMode "yes"
#else
  #error Unknown CompressionProfile
#endif
[Setup]
; Preserve installation identity so earlier local versions upgrade in place.
AppId=VocalPitchLab.LocalPreview
AppName=VocalPitchLab
AppVersion={#AppVersion}
AppPublisher=VocalPitchLab
VersionInfoDescription=VocalPitchLab 安装程序
DefaultDirName={localappdata}\Programs\VocalPitchLab
DefaultGroupName=VocalPitchLab
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#ifdef PackageOutputDir
OutputDir={#PackageOutputDir}
#else
#ifdef GithubAssets
OutputDir=..\dist\VocalPitchLab-{#AppVersion}-windows-x64
#else
OutputDir=..\dist
#endif
#endif
OutputBaseFilename=VocalPitchLab-{#AppVersion}-windows-x64-setup
Compression={#CompressionMethod}
SolidCompression={#SolidMode}
#ifdef GithubAssets
DiskSpanning=yes
DiskSliceSize=1500000000
#endif
SetupIconFile=..\assets\vocalpitch.ico
UninstallDisplayIcon={app}\assets\vocalpitch.ico
LicenseFile=..\LICENSE
WizardStyle=modern
ShowLanguageDialog=no
LanguageDetectionMethod=none
UsePreviousLanguage=no
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
CreateUninstallRegKey=not IsPackageValidation
Uninstallable=not IsPackageValidation
[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked
[Files]
#ifdef PackageFilesInclude
#include PackageFilesInclude
#else
Source: "{#StageDir}\*"; DestDir: "{app}"; Excludes: "__pycache__\*,*.pyc,*.pyo,*.pdb,BRAND.md,PERFORMANCE_PREVIEW.md,audio-separator.exe,audio-separator-remote.exe,\models\*,\runtime\*,\vendor\separation-runtime\*"; Flags: ignoreversion recursesubdirs createallsubdirs solidbreak
Source: "{#StageDir}\models\*"; DestDir: "{app}\models"; Excludes: "__pycache__\*,*.pyc,*.pyo,*.pdb,BRAND.md,PERFORMANCE_PREVIEW.md,audio-separator.exe,audio-separator-remote.exe"; Flags: ignoreversion recursesubdirs createallsubdirs solidbreak
Source: "{#StageDir}\runtime\*"; DestDir: "{app}\runtime"; Excludes: "__pycache__\*,*.pyc,*.pyo,*.pdb,BRAND.md,PERFORMANCE_PREVIEW.md,audio-separator.exe,audio-separator-remote.exe,\Lib\site-packages\torch\*,\Lib\site-packages\PySide6\*"; Flags: ignoreversion recursesubdirs createallsubdirs solidbreak
Source: "{#StageDir}\vendor\separation-runtime\*"; DestDir: "{app}\vendor\separation-runtime"; Excludes: "__pycache__\*,*.pyc,*.pyo,*.pdb,BRAND.md,PERFORMANCE_PREVIEW.md,audio-separator.exe,audio-separator-remote.exe"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#StageDir}\runtime\Lib\site-packages\torch\*"; DestDir: "{app}\runtime\Lib\site-packages\torch"; Excludes: "__pycache__\*,*.pyc,*.pyo,*.pdb,BRAND.md,PERFORMANCE_PREVIEW.md,audio-separator.exe,audio-separator-remote.exe"; Flags: ignoreversion recursesubdirs createallsubdirs solidbreak
Source: "{#StageDir}\runtime\Lib\site-packages\PySide6\*"; DestDir: "{app}\runtime\Lib\site-packages\PySide6"; Excludes: "__pycache__\*,*.pyc,*.pyo,*.pdb,BRAND.md,PERFORMANCE_PREVIEW.md,audio-separator.exe,audio-separator-remote.exe"; Flags: ignoreversion recursesubdirs createallsubdirs solidbreak
#endif
[InstallDelete]
#ifdef ObsoleteFilesInclude
#include ObsoleteFilesInclude
#endif
Type: files; Name: "{app}\assets\BRAND.md"
Type: files; Name: "{app}\PERFORMANCE_PREVIEW.md"
Type: files; Name: "{app}\vendor\separation-runtime\bin\audio-separator.exe"
Type: files; Name: "{app}\vendor\separation-runtime\bin\audio-separator-remote.exe"

[Icons]
Name: "{group}\VocalPitchLab"; Filename: "{app}\VocalPitchLab.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\vocalpitch.ico"; AppUserModelID: "VocalPitchLab.Desktop"; Check: not IsPackageValidation
Name: "{autodesktop}\VocalPitchLab"; Filename: "{app}\VocalPitchLab.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\vocalpitch.ico"; AppUserModelID: "VocalPitchLab.Desktop"; Tasks: desktopicon; Check: not IsPackageValidation
; User library/cache lives outside {app}; uninstall never deletes songs.

#include "vc_redist.iss"

[Code]
function ObsoleteFileMatches(const RelativeName, ExpectedHash: String): Boolean;
var
  FileName: String;
begin
  FileName := AddBackslash(ExpandConstant('{app}')) + RelativeName;
  Result := False;
  if FileExists(FileName) then begin
    try
      Result := CompareText(GetSHA256OfFile(FileName), ExpectedHash) = 0;
    except
      Result := False;
    end;
  end;
end;

function IsPackageValidation: Boolean;
begin
  Result := ExpandConstant('{param:PACKAGEVALIDATION|0}') = '1';
end;

procedure CleanBytecode(const Folder: String);
var
  Entry: TFindRec;
  Child: String;
begin
  if FindFirst(AddBackslash(Folder) + '*', Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') and
           ((Entry.Attributes and $400) = 0) then begin
          Child := AddBackslash(Folder) + Entry.Name;
          if (Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then begin
            CleanBytecode(Child);
            if Entry.Name = '__pycache__' then RemoveDir(Child);
          end else if (CompareText(ExtractFileExt(Child), '.pyc') = 0) or
                      (CompareText(ExtractFileExt(Child), '.pyo') = 0) then
            DeleteFile(Child);
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then begin
    CleanBytecode(ExpandConstant('{app}\runtime\Lib'));
    CleanBytecode(ExpandConstant('{app}\vendor'));
    CleanBytecode(ExpandConstant('{app}\vocalpitchlab'));
    CleanBytecode(ExpandConstant('{app}\__pycache__'));
    RemoveDir(ExpandConstant('{app}\__pycache__'));
  end;
end;
