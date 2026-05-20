#requires -version 5
<#
.SYNOPSIS
  Refreshes PBStudio.UI/openapi.snapshot.json from a live backend.
.DESCRIPTION
  S-H1b (Audit V2): the snapshot is the source for NSwag DTO generation.
  Run this after any backend route/schema change, then rebuild WPF.

  The script starts a uvicorn backend if none is running on port 8765.
.EXAMPLE
  pwsh scripts/dev/refresh-openapi-snapshot.ps1
#>
param(
    [int]$Port = 8765,
    [int]$StartupWaitSec = 30
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$snapshotPath = Join-Path $repoRoot "PBStudio.UI/openapi.snapshot.json"
$uri = "http://localhost:$Port/openapi.json"

function Test-BackendAlive {
    try {
        $null = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

$ownedBackend = $false
if (-not (Test-BackendAlive)) {
    Write-Host "Backend not running on port $Port -- starting uvicorn"
    $env:PYTHONPATH = "src"
    $proc = Start-Process -PassThru -NoNewWindow `
        -RedirectStandardOutput "$env:TEMP\refresh-openapi.uvicorn.out" `
        -RedirectStandardError  "$env:TEMP\refresh-openapi.uvicorn.err" `
        -FilePath ".venv\Scripts\python.exe" `
        -ArgumentList "-m","uvicorn","backend.main:app","--port","$Port","--log-level","warning"
    $ownedBackend = $true
    # Poll-loop statt fixed sleep: Backend braucht 5-30s je nach Module-Imports.
    $deadline = (Get-Date).AddSeconds($StartupWaitSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-BackendAlive) { break }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-BackendAlive)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        throw "Backend didn't come up within $StartupWaitSec s. See $env:TEMP\refresh-openapi.uvicorn.err"
    }
} else {
    Write-Host "Backend already running on port $Port -- using existing"
}

try {
    Write-Host "Fetching $uri"
    $spec = Invoke-RestMethod -Uri $uri
    $json = $spec | ConvertTo-Json -Depth 100 -Compress:$false
    Set-Content -Path $snapshotPath -Value $json -Encoding utf8
    $size = (Get-Item $snapshotPath).Length
    Write-Host "Wrote $snapshotPath ($size bytes)"
} finally {
    if ($ownedBackend) {
        Write-Host "Stopping owned backend (PID $($proc.Id))"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. git diff PBStudio.UI/openapi.snapshot.json   # review changes"
Write-Host "  2. dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release"
Write-Host "  3. pytest Tests/test_openapi_snapshot_drift.py"
Write-Host "  4. git add + commit"
