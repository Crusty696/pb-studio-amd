#Requires -Version 5.1
<#!
.SYNOPSIS
    PB Studio AMD – Publish Script
.DESCRIPTION
    Erstellt reproduzierbare WPF-Publish-Artefakte für verschiedene Deployment-Modi.
#>

param(
    [ValidateSet('framework', 'selfcontained', 'singlefile')]
    [string]$Mode = 'framework',
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',
    [string]$Runtime = 'win-x64',
    [string]$OutputRoot = '.\artifacts\publish'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$ProjectFile = Join-Path $ProjectRoot 'PBStudio.UI\PBStudio.UI.csproj'
$OutputDir = Join-Path $ProjectRoot (Join-Path $OutputRoot $Mode)

function Write-Status($msg, $color = 'Cyan') {
    Write-Host '[PB Publish] ' -NoNewline -ForegroundColor $color
    Write-Host $msg
}

if (-not (Test-Path $ProjectFile)) {
    throw "Project file not found: $ProjectFile"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$publishArgs = @(
    'publish',
    $ProjectFile,
    '-c', $Configuration,
    '-r', $Runtime,
    '-o', $OutputDir,
    '-p:PublishReadyToRun=false'
)

switch ($Mode) {
    'framework' {
        $publishArgs += @('--self-contained', 'false')
    }
    'selfcontained' {
        $publishArgs += @('--self-contained', 'true')
    }
    'singlefile' {
        $publishArgs += @(
            '--self-contained', 'true',
            '-p:PublishSingleFile=true',
            '-p:IncludeNativeLibrariesForSelfExtract=true'
        )
    }
}

Write-Status "Mode: $Mode"
Write-Status "Configuration: $Configuration"
Write-Status "Runtime: $Runtime"
Write-Status "Output: $OutputDir"

& dotnet @publishArgs
if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $OutputDir 'PBStudio.UI.exe'
if (Test-Path $exe) {
    Write-Status "Publish successful: $exe" 'Green'
} else {
    Write-Status 'Publish completed, but PBStudio.UI.exe was not found in output directory.' 'Yellow'
}
