<#
.SYNOPSIS
    Runs the complete Python suite with coverage, skip and temp-hygiene gates.
#>

[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$ArtifactDirectory = "",
    [string]$MarkerExpression = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if ([string]::IsNullOrWhiteSpace($ArtifactDirectory)) {
    $ArtifactDirectory = Join-Path $repoRoot "artifacts\python-quality"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python executable not found: $PythonExe"
}

$quality = Get-Content -LiteralPath (Join-Path $repoRoot "config\test-quality.json") -Raw |
    ConvertFrom-Json
$releaseBaselineCoverage = 53.0
if ($quality.schema_version -ne 1) {
    throw "Unsupported test-quality schema"
}
if ($null -eq $quality.coverage.minimum_percent) {
    throw "Coverage minimum is missing"
}
try {
    $minimumCoverage = [double]$quality.coverage.minimum_percent
    $unapprovedSkipLimit = [int]$quality.skips.unapproved_allowed
} catch {
    throw "Coverage minimum and skip limit must be numeric"
}
if (
    [double]::IsNaN($minimumCoverage) -or
    [double]::IsInfinity($minimumCoverage) -or
    $minimumCoverage -lt $releaseBaselineCoverage -or
    $minimumCoverage -gt 100.0
) {
    throw "Coverage minimum must be between $releaseBaselineCoverage and 100"
}
if ($unapprovedSkipLimit -ne 0) {
    throw "Release quality gate requires zero unapproved skips"
}
$ownedRootSetting = [string]$quality.temporary_files.owned_root
if ([string]::IsNullOrWhiteSpace($ownedRootSetting)) {
    throw "Configured pytest temp root is empty"
}
$ownedParent = [Environment]::ExpandEnvironmentVariables(
    $ownedRootSetting
)
$ownedParent = [System.IO.Path]::GetFullPath($ownedParent)
$systemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
if (-not $ownedParent.StartsWith(
    $systemTemp,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Configured pytest temp root is outside the system temp directory"
}
$ownedTemp = Join-Path $ownedParent ([guid]::NewGuid().ToString("N"))
$coverageFile = Join-Path $ArtifactDirectory ".coverage"
$coverageJson = Join-Path $ArtifactDirectory "coverage.json"
$skipReport = Join-Path $ArtifactDirectory "skips.json"
$junitReport = Join-Path $ArtifactDirectory "pytest.xml"

function Get-MatchingDirectories {
    param([Parameter(Mandatory)] [object[]]$Globs)
    return @(
        foreach ($glob in $Globs) {
            Get-ChildItem -LiteralPath $repoRoot -Directory -Force -Filter ([string]$glob) |
                ForEach-Object { $_.FullName }
        }
    ) | Sort-Object -Unique
}

function Get-TreeDigest {
    param([Parameter(Mandatory)] [string]$Directory)
    $root = [System.IO.Path]::GetFullPath($Directory)
    $records = @(
        Get-ChildItem -LiteralPath $root -File -Force -Recurse |
            Sort-Object FullName |
            ForEach-Object {
                $relative = $_.FullName.Substring($root.Length).TrimStart("\", "/")
                $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                "$relative|$($_.Length)|$hash"
            }
    )
    $payload = [System.Text.Encoding]::UTF8.GetBytes(($records -join "`n"))
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString(
            $algorithm.ComputeHash($payload)
        )).Replace("-", "").ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
    }
}

$forbiddenGlobs = @($quality.temporary_files.forbidden_new_repository_globs)
$preserveGlobs = @($quality.temporary_files.historical_preserve_globs)
if ($forbiddenGlobs.Count -eq 0 -or $preserveGlobs.Count -eq 0) {
    throw "Temp hygiene globs must not be empty"
}
foreach ($glob in @($forbiddenGlobs + $preserveGlobs)) {
    if (
        $glob -isnot [string] -or
        [string]::IsNullOrWhiteSpace($glob) -or
        $glob.Contains("..") -or
        $glob.Contains("\") -or
        $glob.Contains("/")
    ) {
        throw "Temp hygiene glob must be a non-empty root-name pattern"
    }
}
$beforeScratch = @(Get-MatchingDirectories -Globs $forbiddenGlobs)
$beforePreserved = @{}
foreach ($path in (Get-MatchingDirectories -Globs $preserveGlobs)) {
    $beforePreserved[$path] = Get-TreeDigest -Directory $path
}

New-Item -ItemType Directory -Path $ArtifactDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $ownedTemp -Force | Out-Null

$previousPythonPath = $env:PYTHONPATH
$previousCoverageFile = $env:COVERAGE_FILE
$previousSkipAllowlist = $env:PBSTUDIO_SKIP_ALLOWLIST
$previousSkipReport = $env:PBSTUDIO_SKIP_REPORT
$previousSkipLimit = $env:PBSTUDIO_UNAPPROVED_SKIP_LIMIT
$primaryError = $null
$hygieneErrors = New-Object System.Collections.Generic.List[string]

try {
    $env:PYTHONPATH = "src;."
    $env:COVERAGE_FILE = $coverageFile
    $env:PBSTUDIO_SKIP_ALLOWLIST = Join-Path $repoRoot "config\pytest-skip-allowlist.json"
    $env:PBSTUDIO_SKIP_REPORT = $skipReport
    $env:PBSTUDIO_UNAPPROVED_SKIP_LIMIT = [string]$unapprovedSkipLimit

    Push-Location $repoRoot
    try {
        & $PythonExe -m coverage erase
        if ($LASTEXITCODE -ne 0) { throw "coverage erase failed" }

        $pytestArguments = @(
            "-m", "coverage", "run", "--rcfile=.coveragerc",
            "-m", "pytest", "Tests",
            "-p", "scripts.pytest_release_guard",
            "-p", "no:cacheprovider",
            "--basetemp=$ownedTemp",
            "--junitxml=$junitReport"
        )
        if (-not [string]::IsNullOrWhiteSpace($MarkerExpression)) {
            $pytestArguments += @("-m", $MarkerExpression)
        }
        & $PythonExe @pytestArguments
        if ($LASTEXITCODE -ne 0) { throw "pytest quality run failed" }

        & $PythonExe -m coverage json --rcfile=.coveragerc -o $coverageJson
        if ($LASTEXITCODE -ne 0) { throw "coverage JSON generation failed" }

        & $PythonExe -m coverage report --rcfile=.coveragerc "--fail-under=$minimumCoverage"
        if ($LASTEXITCODE -ne 0) {
            throw "Coverage fell below $minimumCoverage percent"
        }
    } finally {
        Pop-Location
    }
} catch {
    $primaryError = $_
} finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:COVERAGE_FILE = $previousCoverageFile
    $env:PBSTUDIO_SKIP_ALLOWLIST = $previousSkipAllowlist
    $env:PBSTUDIO_SKIP_REPORT = $previousSkipReport
    $env:PBSTUDIO_UNAPPROVED_SKIP_LIMIT = $previousSkipLimit
    try {
        if (Test-Path -LiteralPath $ownedTemp) {
            $resolvedOwned = [System.IO.Path]::GetFullPath($ownedTemp)
            $resolvedParent = [System.IO.Path]::GetFullPath($ownedParent) +
                [System.IO.Path]::DirectorySeparatorChar
            if (-not $resolvedOwned.StartsWith(
                $resolvedParent,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                throw "Refusing to clean non-owned temp directory: $resolvedOwned"
            }
            Remove-Item -LiteralPath $resolvedOwned -Recurse -Force
        }
    } catch {
        [void]$hygieneErrors.Add("Owned temp cleanup failed: $($_.Exception.Message)")
    }
    try {
        $afterScratch = @(Get-MatchingDirectories -Globs $forbiddenGlobs)
        $newScratch = @($afterScratch | Where-Object { $_ -notin $beforeScratch })
        if ($newScratch.Count -gt 0) {
            [void]$hygieneErrors.Add(
                "Python quality run left repository scratch directories: " +
                ($newScratch -join ", ")
            )
        }
        $afterPreserved = @{}
        foreach ($path in (Get-MatchingDirectories -Globs $preserveGlobs)) {
            $afterPreserved[$path] = Get-TreeDigest -Directory $path
        }
        if ($beforePreserved.Count -ne $afterPreserved.Count) {
            [void]$hygieneErrors.Add(
                "Historical pytest evidence directory set changed"
            )
        } else {
            foreach ($path in $beforePreserved.Keys) {
                if (
                    -not $afterPreserved.ContainsKey($path) -or
                    $afterPreserved[$path] -ne $beforePreserved[$path]
                ) {
                    [void]$hygieneErrors.Add(
                        "Historical pytest evidence changed: $path"
                    )
                }
            }
        }
    } catch {
        [void]$hygieneErrors.Add(
            "Temp hygiene verification failed: $($_.Exception.Message)"
        )
    }
}

if ($hygieneErrors.Count -gt 0) {
    $primaryText = if ($null -ne $primaryError) {
        "Primary gate failure: $($primaryError.Exception.Message). "
    } else {
        ""
    }
    throw (
        $primaryText +
        "Temp hygiene failure: $($hygieneErrors -join '; ')"
    )
}
if ($null -ne $primaryError) {
    throw $primaryError
}

Write-Host "PYTHON_QUALITY_GATE_PASS coverage>=$minimumCoverage unapproved_skips=0"
