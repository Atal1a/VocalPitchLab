param(
    [Parameter(Mandatory=$true)][string]$SetupDirectory,
    [Parameter(Mandatory=$true)][string]$AudioFile,
    [string]$RunName = ('sandbox-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if ($RunName -notmatch '^[a-zA-Z0-9-]+$') { throw 'RunName must contain only letters, digits and hyphens' }
$setup = (Resolve-Path -LiteralPath $SetupDirectory).Path
$audio = (Resolve-Path -LiteralPath $AudioFile).Path
if (@(Get-ChildItem -LiteralPath $setup -Filter '*-setup.exe').Count -ne 1) { throw 'Expected one setup executable in SetupDirectory' }
$inputDir = Join-Path $root "work\$RunName-input"
$outputDir = Join-Path $root "outputs\$RunName"
if ((Test-Path $inputDir) -or (Test-Path $outputDir)) { throw 'Choose a new RunName to preserve previous evidence' }
New-Item -ItemType Directory -Path $inputDir,$outputDir | Out-Null
Copy-Item "$PSScriptRoot\sandbox_run.ps1" "$inputDir\run.ps1"
Copy-Item "$PSScriptRoot\sandbox_check.py" "$inputDir\sandbox_check.py"
Copy-Item -LiteralPath $audio -Destination "$inputDir\sample.wav"
$s = [Security.SecurityElement]::Escape($setup)
$i = [Security.SecurityElement]::Escape($inputDir)
$o = [Security.SecurityElement]::Escape($outputDir)
@"
<Configuration>
<Networking>Disable</Networking><vGPU>Disable</vGPU><MemoryInMB>8192</MemoryInMB>
<MappedFolders>
<MappedFolder><HostFolder>$s</HostFolder><SandboxFolder>C:\VPLSetup</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
<MappedFolder><HostFolder>$i</HostFolder><SandboxFolder>C:\VPLQAInput</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
<MappedFolder><HostFolder>$o</HostFolder><SandboxFolder>C:\VPLQAOutput</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
</MappedFolders>
<LogonCommand><Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\VPLQAInput\run.ps1</Command></LogonCommand>
</Configuration>
"@ | Set-Content "$inputDir\validate.wsb" -Encoding UTF8
Write-Output "Prepared: $inputDir\validate.wsb"
Write-Output "Results: $outputDir"
