#requires -version 5
<#
.SYNOPSIS
    Regenerates the canonical WPF OpenAPI snapshot from FastAPI source.
.DESCRIPTION
    Uses backend.main.app.openapi() directly, writes UTF-8 without BOM through
    same-directory atomic replacement, and verifies the persisted JSON bytes.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
. (Join-Path $repoRoot "scripts\runtime_contract.ps1")
$runtime = Get-PBStudioRuntimeContract `
    -ProjectRoot $repoRoot `
    -RequirePython `
    -ApplyEnvironment

$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = (
        (Join-Path $repoRoot "src") +
        [System.IO.Path]::PathSeparator +
        $repoRoot
    )
    Push-Location $repoRoot
    try {
        & $runtime.PythonExe `
            (Join-Path $repoRoot "scripts\dev\export_openapi_snapshot.py") `
            --output (Join-Path $repoRoot "PBStudio.UI\openapi.snapshot.json")
        if ($LASTEXITCODE -ne 0) {
            throw "OpenAPI snapshot export failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

Write-Host "Next: review snapshot diff, then run the locked WPF Release gate."
