param([string]$OutputPath = "dist/MDCx-HyMT2-launcher.zip")
$ErrorActionPreference = "Stop"
$target = [IO.Path]::GetFullPath($OutputPath)
[IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
$staging = Join-Path ([IO.Path]::GetTempPath()) ("MDCx-launcher-" + [guid]::NewGuid().ToString("N"))
try {
    [IO.Directory]::CreateDirectory($staging) | Out-Null
    foreach ($name in @("Start-HyMT2.cmd", "start-local-hymt2.ps1", "local-hymt2-README.txt")) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $staging
    }
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $target -Force
    Write-Host "Launcher package: $target"
    Get-FileHash -LiteralPath $target -Algorithm SHA256
} finally { Remove-Item -LiteralPath $staging -Recurse -Force }
