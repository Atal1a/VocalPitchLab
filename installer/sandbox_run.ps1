$ErrorActionPreference = 'Stop'
$out = 'C:\VPLQAOutput'
try {
    @{ started=(Get-Date).ToString('o'); computer=$env:COMPUTERNAME; user=$env:USERNAME; os=(Get-CimInstance Win32_OperatingSystem).Caption; pythonBeforeInstall=@(Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source) } | ConvertTo-Json | Set-Content "$out\system.json"
    $setup = Get-ChildItem 'C:\VPLSetup\*-setup.exe'
    if (@($setup).Count -ne 1) { throw 'Expected exactly one setup executable' }
    $setup | Get-FileHash -Algorithm SHA256 | ConvertTo-Json | Set-Content "$out\installer-hash.json"
    $p = Start-Process $setup.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/DIR=C:\VPLInstalled',"/LOG=$out\install.log" -WindowStyle Hidden -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Install failed: $($p.ExitCode)" }
    $env:VPL_QA_DATA_DIR = "$env:LOCALAPPDATA\VocalPitchLab-SandboxQA"
    $p = Start-Process 'C:\VPLInstalled\runtime\python.exe' -ArgumentList 'C:\VPLQAInput\sandbox_check.py',$out,'C:\VPLQAInput\sample.wav' -RedirectStandardOutput "$out\analysis.log" -RedirectStandardError "$out\analysis-stderr.log" -WindowStyle Hidden -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Application verification failed' }
    $sentinel = Join-Path $env:VPL_QA_DATA_DIR 'uninstall-retention.txt'
    'retain user data' | Set-Content $sentinel
    $p = Start-Process 'C:\VPLInstalled\unins000.exe' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -WindowStyle Hidden -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Uninstall failed: $($p.ExitCode)" }
    if (Test-Path 'C:\VPLInstalled\runtime\python.exe') { throw 'Runtime remains after uninstall' }
    if (-not (Test-Path $sentinel)) { throw 'User data removed during uninstall' }
    @{status='passed';uninstalled=$true;userDataRetained=$true;finished=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content "$out\acceptance.json"
} catch {
    if ($env:VPL_QA_DATA_DIR) {
        Get-ChildItem "$env:VPL_QA_DATA_DIR\library" -Filter '*.log' -ErrorAction SilentlyContinue | Copy-Item -Destination $out -ErrorAction SilentlyContinue
    }
    $_ | Out-String | Set-Content "$out\error.txt"
    @{status='failed';finished=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content "$out\acceptance.json"
}
