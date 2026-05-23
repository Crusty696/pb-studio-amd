#Requires -Version 5.1
<#
.SYNOPSIS
    PB Studio AMD - Build Script
.DESCRIPTION
    Kompiliert das C# WPF Frontend und prueft Python-Abhaengigkeiten.
#>

param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [switch]$Clean,
    [switch]$PythonOnly
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot

function Write-Status($msg, $color = "Cyan") {
    Write-Host "[Build] " -NoNewline -ForegroundColor $color
    Write-Host $msg
}

Write-Status "=== PB Studio AMD Build ===" "Yellow"

# === Python- & Dotnet-Pfade dynamisch aufloesen ===
function Resolve-PythonExe {
    $candidates = @(
        (Join-Path $ProjectRoot '.venv\Scripts\python.exe'),
        (Join-Path $env:USERPROFILE 'AppData\Local\Programs\Python\Python311\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        'C:\Python311\python.exe',
        'python'
    )

    foreach ($candidate in $candidates) {
        if ($candidate -eq 'python') {
            try {
                $version = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($version -eq "3.11") {
                    return $candidate
                }
            } catch {}
        } elseif (Test-Path $candidate) {
            return $candidate
        }
    }

    throw 'Python 3.11 executable not found (.venv preferred, local AppData/global fallbacks missing).'
}

function Resolve-DotnetExe {
    $candidates = @(
        (Join-Path $ProjectRoot 'tools\dotnet\dotnet.exe'),
        'dotnet'
    )

    foreach ($candidate in $candidates) {
        if ($candidate -eq 'dotnet') {
            try {
                $version = & $candidate --version 2>$null
                if ($version) {
                    return $candidate
                }
            } catch {}
        } elseif (Test-Path $candidate) {
            return $candidate
        }
    }

    throw '.NET SDK executable not found (portable tools\dotnet or global installation missing).'
}

try {
    $PythonExe = Resolve-PythonExe
    $DotnetExe = Resolve-DotnetExe
} catch {
    Write-Status "FEHLER bei der Pfadaufloesung: $_" "Red"
    exit 1
}

# === Python-Abhaengigkeiten pruefen ===
Write-Status "Pruefe Python-Abhaengigkeiten mit $PythonExe..."

$requiredPackages = @("fastapi", "uvicorn", "pydantic", "pydantic-settings")
foreach ($pkg in $requiredPackages) {
    $installed = & $PythonExe -c "import $($pkg.Replace('-','_')); print('OK')" 2>&1
    if ($installed -ne "OK") {
        Write-Status "  FEHLT: $pkg - Installiere..." "Yellow"
        & $PythonExe -m pip install $pkg --quiet
    } else {
        Write-Status "  OK: $pkg" "Green"
    }
}

if ($PythonOnly) {
    Write-Status "Python-Check abgeschlossen" "Green"
    exit 0
}

# === C# WPF Frontend kompilieren ===
$csprojPath = Join-Path $ProjectRoot "PBStudio.UI\PBStudio.UI.csproj"
if (-not (Test-Path $csprojPath)) {
    Write-Status "C# Projekt nicht gefunden: $csprojPath" "Red"
    exit 1
}

# .NET SDK info
$dotnetVersion = & $DotnetExe --version 2>&1
Write-Status "Nutze .NET SDK ($DotnetExe): $dotnetVersion"

# Dotnet-Root temporaer setzen falls wir das portable dotnet nutzen
if ($DotnetExe -like "*tools\dotnet*") {
    $dotnetDir = Split-Path $DotnetExe -Parent
    $env:DOTNET_ROOT = $dotnetDir
    $env:Path = "$dotnetDir;$env:Path"
}

if ($Clean) {
    Write-Status "Clean Build..."
    & $DotnetExe clean $csprojPath -c $Configuration --nologo -v q
}

Write-Status "Kompiliere: $Configuration..."
& $DotnetExe build $csprojPath -c $Configuration --nologo
$buildExit = $LASTEXITCODE

if ($buildExit -eq 0) {
    Write-Status "Build erfolgreich!" "Green"
    $outputDir = Join-Path $ProjectRoot "PBStudio.UI\bin\$Configuration\net9.0-windows"
    Write-Status "Output: $outputDir"
} else {
    Write-Status "Build fehlgeschlagen! Exit-Code: $buildExit" "Red"
    exit 1
}

Write-Status "=== Build abgeschlossen ===" "Yellow"
