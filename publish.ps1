#Requires -Version 5.1
<#
.SYNOPSIS
    PB Studio AMD - Publish Script
.DESCRIPTION
    Erstellt reproduzierbare WPF-Publish-Artefakte fuer verschiedene Deployment-Modi.
#>

param(
    [ValidateSet('framework', 'selfcontained', 'singlefile')]
    [string]$Mode = 'framework',
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',
    [string]$Runtime = 'win-x64',
    [string]$OutputRoot = '.\artifacts\publish',
    [switch]$FlatOutput,
    [string]$VersionTag,
    [switch]$NoPause
)

$ErrorActionPreference = 'Continue'
$ProjectRoot = $PSScriptRoot
$ProjectFile = Join-Path $ProjectRoot 'PBStudio.UI\PBStudio.UI.csproj'
$publishBaseDir = Join-Path $ProjectRoot (Join-Path $OutputRoot $Mode)

if ($VersionTag) {
    $safeVersionTag = ($VersionTag -replace '[^A-Za-z0-9._-]', '-')
} else {
    $safeVersionTag = Get-Date -Format 'yyyyMMdd-HHmmss'
}

$OutputDir = if ($FlatOutput) {
    $publishBaseDir
} else {
    Join-Path $publishBaseDir (Join-Path $Configuration (Join-Path $Runtime $safeVersionTag))
}

function Write-Status($msg, $color = 'Cyan') {
    Write-Host '[PB Publish] ' -NoNewline -ForegroundColor $color
    Write-Host $msg
}

function Get-RelativePathSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    try {
        return [System.IO.Path]::GetRelativePath($BasePath, $TargetPath)
    } catch {
        $baseResolved = (Resolve-Path $BasePath).Path.TrimEnd('\\')
        $targetResolved = (Resolve-Path $TargetPath).Path
        $baseUri = [System.Uri]($baseResolved + [System.IO.Path]::DirectorySeparatorChar)
        $targetUri = [System.Uri]$targetResolved
        $relativeUri = $baseUri.MakeRelativeUri($targetUri)
        return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    }
}

function Write-LatestPointer {
    param(
        [string]$BaseDir,
        [string]$ResolvedOutputDir
    )

    $latestFile = Join-Path $BaseDir 'latest.txt'
    $relativeOutput = Get-RelativePathSafe -BasePath $BaseDir -TargetPath $ResolvedOutputDir
    Set-Content -Path $latestFile -Value $relativeOutput -Encoding ascii
}

function Write-PublishMetadata {
    param(
        [string]$BaseDir,
        [string]$ResolvedOutputDir,
        [string]$ResolvedExe
    )

    $relativeOutput = Get-RelativePathSafe -BasePath $BaseDir -TargetPath $ResolvedOutputDir
    $relativeExe = Get-RelativePathSafe -BasePath $BaseDir -TargetPath $ResolvedExe
    $metadata = [ordered]@{
        mode = $Mode
        configuration = $Configuration
        runtime = $Runtime
        versionTag = $safeVersionTag
        flatOutput = [bool]$FlatOutput
        outputDir = $ResolvedOutputDir
        outputDirRelative = $relativeOutput
        exePath = $ResolvedExe
        exePathRelative = $relativeExe
        generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    }

    $latestJson = Join-Path $BaseDir 'latest.json'
    $metadata | ConvertTo-Json -Depth 5 | Set-Content -Path $latestJson -Encoding utf8
}

function Test-LegacyFlatArtifacts {
    param([string]$BaseDir)

    $flatExe = Join-Path $BaseDir 'PBStudio.UI.exe'
    if (-not (Test-Path $flatExe)) {
        return $false
    }

    $releaseDir = Join-Path $BaseDir 'Release'
    if (-not (Test-Path $releaseDir)) {
        return $true
    }

    $flatTimestamp = (Get-Item $flatExe).LastWriteTimeUtc
    $newerVersionedExe = Get-ChildItem -Path $releaseDir -Filter 'PBStudio.UI.exe' -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTimeUtc -ge $flatTimestamp } |
        Select-Object -First 1

    return $null -ne $newerVersionedExe
}

# --- Pre-flight checks ---
if (-not (Test-Path $ProjectFile)) {
    Write-Status "FATAL: Project file not found: $ProjectFile" 'Red'
    exit 1
}

$null = New-Item -ItemType Directory -Force -Path $OutputDir
if (-not (Test-Path $OutputDir)) {
    Write-Status "FATAL: Could not create output directory: $OutputDir" 'Red'
    exit 1
}

# --- Build publishArgs ---
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

Write-Status "Mode:          $Mode"
Write-Status "Configuration: $Configuration"
Write-Status "Runtime:       $Runtime"
Write-Status "Output:        $OutputDir"
if (-not $FlatOutput) {
    Write-Status "Version tag:   $safeVersionTag"
}

# --- dotnet publish ---
Write-Status "Running: dotnet $($publishArgs -join ' ')"
& dotnet @publishArgs
$publishExit = $LASTEXITCODE
if ($publishExit -ne 0) {
    Write-Status "FATAL: dotnet publish failed with exit code $publishExit" 'Red'
    exit $publishExit
}

# --- Post-publish ---
$resolvedOutputDir = (Resolve-Path $OutputDir).Path
Write-LatestPointer -BaseDir $publishBaseDir -ResolvedOutputDir $resolvedOutputDir

$exe = Join-Path $resolvedOutputDir 'PBStudio.UI.exe'
if (Test-Path $exe) {
    Write-PublishMetadata -BaseDir $publishBaseDir -ResolvedOutputDir $resolvedOutputDir -ResolvedExe $exe
    Write-Status "Publish successful: $exe" 'Green'
    if (-not $FlatOutput) {
        Write-Status "Latest pointer updated: $(Join-Path $publishBaseDir 'latest.txt') -> $(Get-RelativePathSafe -BasePath $publishBaseDir -TargetPath $resolvedOutputDir)" 'Green'
        if (Test-LegacyFlatArtifacts -BaseDir $publishBaseDir) {
            Write-Status "Legacy flat artifacts detected in $publishBaseDir. Launcher will prefer versioned releases; optional cleanup recommended." 'Yellow'
        }
    }
    Write-Status "Publish metadata written: $(Join-Path $publishBaseDir 'latest.json')" 'Green'
} else {
    Write-Status 'Publish completed, but PBStudio.UI.exe was not found in output directory.' 'Yellow'
}

if (-not $NoPause) { Read-Host 'Press Enter to close' }
