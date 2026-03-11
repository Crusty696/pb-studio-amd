#Requires -Version 5.1
<#!
.SYNOPSIS
    PB Studio AMD – Launcher Script
.DESCRIPTION
    Startet das Python FastAPI Backend und das C# WPF Frontend.
    Backend: localhost:8765 (Python + FastAPI + Uvicorn)
    Frontend: PBStudio.UI.exe (.NET 9.0 WPF)
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Debug,
    [string]$PublishedDir
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$BackendPort = 8765
$BackendHost = '127.0.0.1'
$HealthCheckUrl = "http://${BackendHost}:${BackendPort}/health"
$MaxStartupWaitSeconds = 30

function Write-Status($msg, $color = 'Cyan') {
    Write-Host '[PB Studio] ' -NoNewline -ForegroundColor $color
    Write-Host $msg
}

function Resolve-PythonExe {
    $candidates = @(
        (Join-Path $ProjectRoot '.venv\Scripts\python.exe'),
        'C:\Users\david\AppData\Local\Programs\Python\Python311\python.exe',
        'python'
    )

    foreach ($candidate in $candidates) {
        if ($candidate -eq 'python') {
            try {
                $null = & $candidate --version 2>$null
                return $candidate
            } catch {}
        } elseif (Test-Path $candidate) {
            return $candidate
        }
    }

    throw 'Python executable not found (.venv preferred, global fallback missing).'
}

function Test-BackendHealth {
    try {
        $response = Invoke-RestMethod -Uri $HealthCheckUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.status -eq 'ok'
    } catch {
        return $false
    }
}

function Wait-ForBackend {
    Write-Status "Warte auf Backend ($HealthCheckUrl)..."
    $deadline = (Get-Date).AddSeconds($MaxStartupWaitSeconds)

    while ((Get-Date) -lt $deadline) {
        if (Test-BackendHealth) {
            Write-Status 'Backend ist bereit!' 'Green'
            return $true
        }
        Start-Sleep -Milliseconds 500
    }

    Write-Status "Backend-Timeout nach ${MaxStartupWaitSeconds}s!" 'Red'
    return $false
}

function Resolve-FrontendExe {
    $candidates = @()

    if ($PublishedDir) {
        $candidates += (Join-Path $PublishedDir 'PBStudio.UI.exe')
    }

    $candidates += @(
        (Join-Path $ProjectRoot 'artifacts\publish\framework\PBStudio.UI.exe'),
        (Join-Path $ProjectRoot 'artifacts\publish\selfcontained\PBStudio.UI.exe'),
        (Join-Path $ProjectRoot 'artifacts\publish\singlefile\PBStudio.UI.exe'),
        (Join-Path $ProjectRoot 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe'),
        (Join-Path $ProjectRoot 'PBStudio.UI\bin\Debug\net9.0-windows\PBStudio.UI.exe')
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

Write-Status '=== PB Studio AMD Launcher ===' 'Yellow'
$PythonExe = Resolve-PythonExe
$pyVersion = & $PythonExe --version 2>&1
Write-Status "Python: $pyVersion"

$ffmpegPath = Join-Path $ProjectRoot 'tools\ffmpeg\bin\ffmpeg.exe'
if (Test-Path $ffmpegPath) {
    Write-Status "FFmpeg: $ffmpegPath"
} else {
    Write-Status 'FFmpeg nicht gefunden (optional)' 'Yellow'
}

if (-not $FrontendOnly) {
    Write-Status 'Starte Python Backend...'

    $backendArgs = @('-m', 'uvicorn', 'backend.main:app', '--host', $BackendHost, '--port', $BackendPort)
    if ($Debug) { $backendArgs += '--reload' }

    $env:PYTHONPATH = Join-Path $ProjectRoot 'src'

    $backendProcess = Start-Process -FilePath $PythonExe `
        -ArgumentList $backendArgs `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Minimized `
        -PassThru

    Write-Status "Backend-PID: $($backendProcess.Id)"

    if (-not (Wait-ForBackend)) {
        Write-Status 'Backend konnte nicht gestartet werden!' 'Red'
        if ($backendProcess -and -not $backendProcess.HasExited) { $backendProcess.Kill() }
        exit 1
    }
}

if (-not $BackendOnly) {
    $frontendExe = Resolve-FrontendExe
    if ($frontendExe) {
        Write-Status "Starte Frontend: $frontendExe"
        $frontendProcess = Start-Process -FilePath $frontendExe -PassThru
    } else {
        Write-Status 'Frontend nicht gefunden. Nutze zuerst publish.ps1 oder dotnet build.' 'Yellow'
        if ($backendProcess) {
            Write-Status "Backend läuft auf http://${BackendHost}:${BackendPort}" 'Yellow'
            Write-Status 'Drücke Ctrl+C zum Beenden' 'Yellow'
            $backendProcess.WaitForExit()
        }
        exit 0
    }

    Write-Status "Frontend-PID: $($frontendProcess.Id)"
    Write-Status 'App läuft. Warte auf Beenden...' 'Green'
    $frontendProcess.WaitForExit()
}

if (-not $FrontendOnly -and $backendProcess -and -not $backendProcess.HasExited) {
    Write-Status 'Stoppe Backend...'
    try {
        Invoke-RestMethod -Uri "http://${BackendHost}:${BackendPort}/shutdown" -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Seconds 3
    } catch {}

    if (-not $backendProcess.HasExited) {
        $backendProcess.Kill()
    }
    Write-Status 'Backend gestoppt'
}

Write-Status '=== PB Studio beendet ===' 'Yellow'
