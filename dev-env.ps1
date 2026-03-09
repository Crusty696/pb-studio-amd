#Requires -Version 5.1
<#
.SYNOPSIS
    PB Studio AMD – Development Environment Setup
.DESCRIPTION
    Richtet die Entwicklungsumgebung ein: Python venv, .NET, Dependencies.
#>

param(
    [switch]$Force,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$PythonExe = "C:\Users\david\AppData\Local\Programs\Python\Python311\python.exe"
$VenvPath = Join-Path $ProjectRoot ".venv"

function Write-Status($msg, $color = "Cyan") {
    Write-Host "[Setup] " -NoNewline -ForegroundColor $color
    Write-Host $msg
}

function Test-Python {
    if (-not (Test-Path $PythonExe)) {
        Write-Status "Python 3.11 nicht gefunden: $PythonExe" "Red"
        Write-Status "Bitte Python 3.11 installieren: https://www.python.org/downloads/" "Yellow"
        exit 1
    }
    
    $version = & $PythonExe --version 2>&1
    Write-Status "Python: $version"
    
    if ($version -notmatch "3.11") {
        Write-Status "Warnung: Python 3.11 empfohlen!" "Yellow"
    }
}

function Test-DotNet {
    $dotnet = & dotnet --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Status ".NET SDK nicht gefunden" "Red"
        Write-Status "Installieren: https://dotnet.microsoft.com/download" "Yellow"
        exit 1
    }
    
    Write-Status ".NET SDK: $dotnet"
}

function Setup-Venv {
    if (Test-Path $VenvPath) {
        if ($Clean) {
            Write-Status "Lösche alte venv..."
            Remove-Item $VenvPath -Recurse -Force
        } elseif (-not $Force) {
            Write-Status "venv existiert bereits. Verwende -Force zum Neuerstellen." "Yellow"
            return
        }
    }
    
    Write-Status "Erstelle Python venv..."
    & $PythonExe -m venv $VenvPath
    
    Write-Status "Aktiviere venv und installiere Dependencies..."
    $activateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
    & $activateScript
    
    Write-Status "pip upgrade..."
    & pip install --upgrade pip --quiet
    
    Write-Status "Installiere Backend-Dependencies..."
    $requirementsPath = Join-Path $ProjectRoot "requirements.txt"
    if (Test-Path $requirementsPath) {
        & pip install -r $requirementsPath --quiet
    } else {
        Write-Status "requirements.txt nicht gefunden — installiere Basis-Packages" "Yellow"
        & pip install fastapi uvicorn pydantic pydantic-settings --quiet
    }
    
    Write-Status "venv fertig!" "Green"
}

function Setup-DotNet {
    $csprojPath = Join-Path $ProjectRoot "PBStudio.UI\PBStudio.UI.csproj"
    if (-not (Test-Path $csprojPath)) {
        Write-Status "C# Projekt nicht gefunden: $csprojPath" "Yellow"
        return
    }
    
    Write-Status "Restore .NET Dependencies..."
    & dotnet restore $csprojPath --nologo -v q
    
    Write-Status ".NET Setup fertig!" "Green"
}

# === Hauptlogik ===
Write-Status "=== PB Studio AMD Environment Setup ===" "Yellow"

Test-Python
Test-DotNet

Setup-Venv
Setup-DotNet

Write-Status "=== Setup abgeschlossen ===" "Green"
Write-Status "Nächste Schritte:" "Cyan"
Write-Status "  1. . .\.venv\Scripts\Activate.ps1  (venv aktivieren)"
Write-Status "  2. .\build.ps1                     (Frontend kompilieren)"
Write-Status "  3. .\launch.ps1                    (App starten)"
