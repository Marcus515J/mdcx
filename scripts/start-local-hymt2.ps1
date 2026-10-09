param(
    [string]$LlamaServerPath = "",
    [string]$ModelPath = ""
)

$ErrorActionPreference = "Stop"

# Reuse the existing ChickenRice runtime and GGUF; do not download or install anything.
function Select-ExistingFile([string]$Title, [string]$Filter) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = $Title
    $dialog.Filter = $Filter
    $dialog.CheckFileExists = $true
    try {
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
            throw "File selection cancelled."
        }
        return $dialog.FileName
    }
    finally {
        $dialog.Dispose()
    }
}

if (-not $LlamaServerPath) {
    $LlamaServerPath = Select-ExistingFile "Select ChickenRice llama-server.exe" "llama-server.exe|llama-server.exe"
}
if (-not $ModelPath) {
    $ModelPath = Select-ExistingFile "Select existing Hy-MT2 GGUF model" "GGUF model|*.gguf"
}
$LlamaServerPath = (Resolve-Path -LiteralPath $LlamaServerPath).Path
$ModelPath = (Resolve-Path -LiteralPath $ModelPath).Path
Write-Host "Starting Hy-MT2 for MDCx: http://127.0.0.1:8080/v1"
Write-Host "Wait for llama-server to finish loading before scraping. Keep this window open."
Write-Host "Stop with Ctrl+C when finished to release GPU memory."
Push-Location (Split-Path -Parent $LlamaServerPath)
try {
    & $LlamaServerPath -m $ModelPath -ngl 999 -c 8192 --host 127.0.0.1 --port 8080 --alias HY-MT2-7B-Q8_0
    if ($LASTEXITCODE -ne 0) { throw "llama-server exited with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
