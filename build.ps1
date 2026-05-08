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
$PythonExe = "C:\Users\david\AppData\Local\Programs\Python\Python311\python.exe"

function Write-Status($msg, $color = "Cyan") {
    Write-Host "[Build] " -NoNewline -ForegroundColor $color
    Write-Host $msg
}

Write-Status "=== PB Studio AMD Build ===" "Yellow"

# === Python-Abhaengigkeiten pruefen ===
Write-Status "Pruefe Python-Abhaengigkeiten..."

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

# .NET SDK pruefen
$dotnetVersion = & dotnet --version 2>&1
Write-Status ".NET SDK: $dotnetVersion"

if ($Clean) {
    Write-Status "Clean Build..."
    & dotnet clean $csprojPath -c $Configuration --nologo -v q
}

Write-Status "Kompiliere: $Configuration..."
& dotnet build $csprojPath -c $Configuration --nologo
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
