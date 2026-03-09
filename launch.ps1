#Requires -Version 5.1
<#
.SYNOPSIS
    PB Studio AMD – Launcher Script
.DESCRIPTION
    Startet das Python FastAPI Backend und das C# WPF Frontend.
    Backend: localhost:8765 (Python 3.11 + FastAPI + Uvicorn)
    Frontend: PBStudio.UI.exe (.NET 9.0 WPF)
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Debug
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# === Konfiguration ===
$PythonExe = "C:\Users\david\AppData\Local\Programs\Python\Python311\python.exe"
$BackendPort = 8765
$BackendHost = "127.0.0.1"
$HealthCheckUrl = "http://${BackendHost}:${BackendPort}/health"
$MaxStartupWaitSeconds = 30

# === Hilfsfunktionen ===
function Write-Status($msg, $color = "Cyan") {
    Write-Host "[PB Studio] " -NoNewline -ForegroundColor $color
    Write-Host $msg
}

function Test-BackendHealth {
    try {
        $response = Invoke-RestMethod -Uri $HealthCheckUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.status -eq "ok"
    } catch {
        return $false
    }
}

function Wait-ForBackend {
    Write-Status "Warte auf Backend ($HealthCheckUrl)..."
    $deadline = (Get-Date).AddSeconds($MaxStartupWaitSeconds)
    
    while ((Get-Date) -lt $deadline) {
        if (Test-BackendHealth) {
            Write-Status "Backend ist bereit!" "Green"
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    
    Write-Status "Backend-Timeout nach ${MaxStartupWaitSeconds}s!" "Red"
    return $false
}

# === Prüfungen ===
Write-Status "=== PB Studio AMD Launcher ===" "Yellow"

# Python prüfen
if (-not (Test-Path $PythonExe)) {
    Write-Status "Python nicht gefunden: $PythonExe" "Red"
    exit 1
}

$pyVersion = & $PythonExe --version 2>&1
Write-Status "Python: $pyVersion"

# FFmpeg prüfen
$ffmpegPath = Join-Path $ProjectRoot "tools\ffmpeg\bin\ffmpeg.exe"
if (Test-Path $ffmpegPath) {
    Write-Status "FFmpeg: $ffmpegPath"
} else {
    Write-Status "FFmpeg nicht gefunden (optional)" "Yellow"
}

# === Backend starten ===
if (-not $FrontendOnly) {
    Write-Status "Starte Python Backend..."
    
    $backendArgs = "-m", "uvicorn", "backend.main:app", "--host", $BackendHost, "--port", $BackendPort
    if ($Debug) { $backendArgs += "--reload" }
    
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    
    $backendProcess = Start-Process -FilePath $PythonExe `
        -ArgumentList $backendArgs `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Minimized `
        -PassThru
    
    Write-Status "Backend-PID: $($backendProcess.Id)"
    
    if (-not (Wait-ForBackend)) {
        Write-Status "Backend konnte nicht gestartet werden!" "Red"
        if (-not $backendProcess.HasExited) { $backendProcess.Kill() }
        exit 1
    }
}

# === Frontend starten ===
if (-not $BackendOnly) {
    $frontendExe = Join-Path $ProjectRoot "PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe"
    $frontendDebugExe = Join-Path $ProjectRoot "PBStudio.UI\bin\Debug\net9.0-windows\PBStudio.UI.exe"
    
    if (Test-Path $frontendExe) {
        Write-Status "Starte Frontend: $frontendExe"
        $frontendProcess = Start-Process -FilePath $frontendExe -PassThru
    } elseif (Test-Path $frontendDebugExe) {
        Write-Status "Starte Frontend (Debug): $frontendDebugExe"
        $frontendProcess = Start-Process -FilePath $frontendDebugExe -PassThru
    } else {
        Write-Status "Frontend nicht gefunden. Bitte zuerst kompilieren:" "Yellow"
        Write-Status "  cd PBStudio.UI && dotnet build" "Yellow"
        
        if (-not $BackendOnly -and $backendProcess) {
            Write-Status "Backend läuft auf http://${BackendHost}:${BackendPort}"
            Write-Status "Drücke Ctrl+C zum Beenden"
            $backendProcess.WaitForExit()
        }
        exit 0
    }
    
    Write-Status "Frontend-PID: $($frontendProcess.Id)"
    
    # Warte auf Frontend-Ende
    Write-Status "App läuft. Warte auf Beenden..." "Green"
    $frontendProcess.WaitForExit()
}

# === Cleanup ===
if (-not $FrontendOnly -and $backendProcess -and -not $backendProcess.HasExited) {
    Write-Status "Stoppe Backend..."
    try {
        Invoke-RestMethod -Uri "http://${BackendHost}:${BackendPort}/shutdown" -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    } catch {}
    
    if (-not $backendProcess.HasExited) {
        $backendProcess.Kill()
    }
    Write-Status "Backend gestoppt"
}

Write-Status "=== PB Studio beendet ===" "Yellow"
