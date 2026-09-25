param([string]$SourceFile)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$manifest = Get-Content (Join-Path $root 'resources\vc-redist.json') -Raw | ConvertFrom-Json
$directory = Join-Path $root 'work\installer-tools\prerequisites'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$target = Join-Path $directory $manifest.file
$candidate = Join-Path $directory (([guid]::NewGuid().ToString()) + '.exe')
if ($SourceFile) {
    Copy-Item -LiteralPath (Resolve-Path -LiteralPath $SourceFile).Path -Destination $candidate
} elseif (Test-Path -LiteralPath $target) {
    Copy-Item -LiteralPath $target -Destination $candidate
} else {
    Invoke-WebRequest $manifest.download_url -OutFile $candidate
}
# The official latest URL can move. Never silently accept a different artifact.
if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash -ne $manifest.sha256) {
    throw "Runtime hash mismatch. Preserve the pinned artifact or explicitly review a version update. Download retained at $candidate"
}
$signature = Get-AuthenticodeSignature -LiteralPath $candidate
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') {
    throw "Microsoft signature could not be verified: $($signature.Status). File retained at $candidate"
}
Move-Item -LiteralPath $candidate -Destination $target -Force
Write-Output "Offline prerequisite ready: $target"
