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
    [string]$PublishedDir,
    [ValidateSet('framework', 'selfcontained', 'singlefile')]
    [string]$PreferredPublishMode
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$BackendPort = 8765
$BackendHost = '127.0.0.1'
$HealthCheckUrl = "http://${BackendHost}:${BackendPort}/health"
$MaxStartupWaitSeconds = 30
$startedBackend = $false
$backendWasAlreadyRunning = $false
$previousExternalBackendFlag = $env:PBSTUDIO_BACKEND_MANAGED_EXTERNALLY
$previousBackendDir = $env:PBSTUDIO_BACKEND_DIR
$LogsDir = Join-Path $ProjectRoot 'logs'
$BackendStdOutLog = Join-Path $LogsDir 'backend_live.out.log'
$BackendStdErrLog = Join-Path $LogsDir 'backend_live.err.log'

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

function Get-BackendListenerPids {
    $connections = Get-NetTCPConnection -LocalAddress $BackendHost -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        return @()
    }

    return @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Test-ProcessDescendsFrom {
    param(
        [int]$ProcessId,
        [int]$AncestorId
    )

    if ($ProcessId -eq $AncestorId) {
        return $true
    }

    $currentPid = $ProcessId
    for ($i = 0; $i -lt 12 -and $currentPid -gt 0; $i++) {
        try {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $currentPid" -ErrorAction Stop
        } catch {
            return $false
        }

        $parentPid = [int]$proc.ParentProcessId
        if ($parentPid -eq $AncestorId) {
            return $true
        }

        if ($parentPid -le 0 -or $parentPid -eq $currentPid) {
            return $false
        }

        $currentPid = $parentPid
    }

    return $false
}

function Wait-ForBackend {
    param([System.Diagnostics.Process]$ExpectedProcess)

    Write-Status "Warte auf Backend ($HealthCheckUrl)..."
    $deadline = (Get-Date).AddSeconds($MaxStartupWaitSeconds)

    while ((Get-Date) -lt $deadline) {
        if ($ExpectedProcess) {
            $ExpectedProcess.Refresh()
            if ($ExpectedProcess.HasExited) {
                $listenerPids = Get-BackendListenerPids
                foreach ($listenerPid in $listenerPids) {
                    if (Test-ProcessDescendsFrom -ProcessId $listenerPid -AncestorId $ExpectedProcess.Id) {
                        Write-Status "Start-PID $($ExpectedProcess.Id) ist beendet, aber Listener-PID $listenerPid läuft weiter. Akzeptiere Windows-Launcher/Child-Prozess." 'Yellow'
                        return $true
                    }
                }

                if (Test-BackendHealth) {
                    Write-Status "Start-PID $($ExpectedProcess.Id) ist beendet, aber Healthcheck ist bereits OK. Akzeptiere separaten Listener-Prozess." 'Yellow'
                    return $true
                }

                Write-Status "Backend-Prozess $($ExpectedProcess.Id) ist vorzeitig beendet (ExitCode=$($ExpectedProcess.ExitCode))." 'Red'
                return $false
            }
        }

        if (Test-BackendHealth) {
            if (-not $ExpectedProcess) {
                Write-Status 'Backend ist bereit!' 'Green'
                return $true
            }

            $listenerPids = Get-BackendListenerPids
            if ($listenerPids -contains $ExpectedProcess.Id) {
                Write-Status 'Backend ist bereit!' 'Green'
                return $true
            }

            foreach ($listenerPid in $listenerPids) {
                if (Test-ProcessDescendsFrom -ProcessId $listenerPid -AncestorId $ExpectedProcess.Id) {
                    Write-Status "Backend ist bereit! Listener-PID $listenerPid ist Child von Start-PID $($ExpectedProcess.Id)." 'Green'
                    return $true
                }
            }

            if ($listenerPids.Count -gt 0) {
                Write-Status "Healthcheck OK, aber Port $BackendPort gehört PID(s) $($listenerPids -join ', ') statt erwartetem PID $($ExpectedProcess.Id). Warte weiter..." 'Yellow'
            }
        }

        Start-Sleep -Milliseconds 500
    }

    Write-Status "Backend-Timeout nach ${MaxStartupWaitSeconds}s!" 'Red'
    return $false
}

function Wait-ForBackendShutdown {
    param(
        [int]$TimeoutSeconds = 10,
        [System.Diagnostics.Process]$ExpectedProcess
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($ExpectedProcess) {
            try {
                $ExpectedProcess.Refresh()
            } catch {}
        }

        $isHealthy = Test-BackendHealth
        $listenerPids = Get-BackendListenerPids
        $listenerGone = $listenerPids.Count -eq 0
        $processExited = $true

        if ($ExpectedProcess) {
            try {
                $processExited = $ExpectedProcess.HasExited
            } catch {
                $processExited = $true
            }
        }

        if ((-not $isHealthy) -and $listenerGone -and $processExited) {
            Start-Sleep -Milliseconds 300
            if ((-not (Test-BackendHealth)) -and ((Get-BackendListenerPids).Count -eq 0)) {
                return $true
            }
        }

        Start-Sleep -Milliseconds 300
    }

    return ((-not (Test-BackendHealth)) -and ((Get-BackendListenerPids).Count -eq 0))
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process) {
        return
    }

    try {
        if ($Process.HasExited) {
            return
        }
    } catch {
        return
    }

    try {
        $null = Start-Process -FilePath 'taskkill.exe' `
            -ArgumentList @('/PID', $Process.Id, '/T', '/F') `
            -WindowStyle Hidden `
            -Wait `
            -PassThru
    } catch {
        try {
            if (-not $Process.HasExited) {
                $Process.Kill()
                $Process.WaitForExit()
            }
        } catch {}
    }
}

function Stop-BackendListeners {
    $listenerPids = Get-BackendListenerPids
    foreach ($listenerPid in $listenerPids) {
        try {
            $null = Start-Process -FilePath 'taskkill.exe' `
                -ArgumentList @('/PID', $listenerPid, '/T', '/F') `
                -WindowStyle Hidden `
                -Wait `
                -PassThru
        } catch {
            try {
                Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
            } catch {}
        }
    }
}

function Get-VersionedPublishedExe {
    param([string]$BaseDir)

    $releaseDir = Join-Path $BaseDir 'Release'
    if (-not (Test-Path $releaseDir)) {
        return $null
    }

    $exe = Get-ChildItem -Path $releaseDir -Filter 'PBStudio.UI.exe' -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\Release\\[^\\]+\\[^\\]+\\PBStudio\.UI\.exe$' } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1

    if ($exe) {
        return $exe.FullName
    }

    return $null
}

function Get-LatestPublishedExe {
    param([string]$BaseDir)

    if (-not (Test-Path $BaseDir)) {
        return $null
    }

    $latestFile = Join-Path $BaseDir 'latest.txt'
    if (Test-Path $latestFile) {
        $relativeTarget = (Get-Content $latestFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if ($relativeTarget) {
            $candidate = Join-Path $BaseDir $relativeTarget
            $exe = Join-Path $candidate 'PBStudio.UI.exe'
            if (Test-Path $exe) {
                return (Resolve-Path $exe).Path
            }
        }
    }

    $versionedExe = Get-VersionedPublishedExe -BaseDir $BaseDir
    if ($versionedExe) {
        return $versionedExe
    }

    $flatExe = Join-Path $BaseDir 'PBStudio.UI.exe'
    if (Test-Path $flatExe) {
        Write-Status "Warnung: fallback auf Flat-Publish-Artefakt in $BaseDir" 'Yellow'
        return (Resolve-Path $flatExe).Path
    }

    return $null
}

function Resolve-FrontendExe {
    $candidates = @()

    if ($PublishedDir) {
        if (Test-Path $PublishedDir -PathType Container) {
            $candidate = Join-Path $PublishedDir 'PBStudio.UI.exe'
            if (Test-Path $candidate) {
                return (Resolve-Path $candidate).Path
            }
        } elseif (Test-Path $PublishedDir -PathType Leaf) {
            return (Resolve-Path $PublishedDir).Path
        }
    }

    if ($PreferredPublishMode) {
        $preferred = Get-LatestPublishedExe -BaseDir (Join-Path $ProjectRoot (Join-Path 'artifacts\publish' $PreferredPublishMode))
        if ($preferred) {
            return $preferred
        }
    }

    $candidates += @(
        (Join-Path $ProjectRoot 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe'),
        (Join-Path $ProjectRoot 'PBStudio.UI\bin\Debug\net9.0-windows\PBStudio.UI.exe')
    )

    foreach ($mode in @('framework', 'selfcontained', 'singlefile')) {
        $candidate = Get-LatestPublishedExe -BaseDir (Join-Path $ProjectRoot (Join-Path 'artifacts\publish' $mode))
        if ($candidate) {
            return $candidate
        }
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

Write-Status '=== PB Studio AMD Launcher ===' 'Yellow'
$backendWasAlreadyRunning = Test-BackendHealth
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
    if (Test-BackendHealth) {
        Write-Status "Backend läuft bereits auf http://${BackendHost}:${BackendPort}" 'Green'
    } else {
        Write-Status 'Starte Python Backend...'

        $backendArgs = @('-m', 'uvicorn', 'backend.main:app', '--host', $BackendHost, '--port', $BackendPort)
        if ($Debug) { $backendArgs += '--reload' }

        $env:PYTHONPATH = Join-Path $ProjectRoot 'src'

        if (-not (Test-Path $LogsDir)) {
            New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
        }

        $backendProcess = Start-Process -FilePath $PythonExe `
            -ArgumentList $backendArgs `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Minimized `
            -RedirectStandardOutput $BackendStdOutLog `
            -RedirectStandardError $BackendStdErrLog `
            -PassThru
        $startedBackend = $true

        Write-Status "Backend-PID: $($backendProcess.Id)"
        Write-Status "Backend-Logs: $BackendStdOutLog | $BackendStdErrLog"

        if (-not (Wait-ForBackend -ExpectedProcess $backendProcess)) {
            Write-Status 'Backend konnte nicht gestartet werden!' 'Red'
            Stop-ProcessTree -Process $backendProcess
            exit 1
        }
    }
}

if ($BackendOnly) {
    if ($startedBackend -and $backendProcess) {
        Write-Status "Backend läuft auf http://${BackendHost}:${BackendPort}" 'Green'
        Write-Status 'BackendOnly aktiv. Warte auf Backend-Ende...' 'Yellow'
        try {
            while (Test-BackendHealth) {
                Start-Sleep -Seconds 1
            }
            exit 0
        } finally {
            Write-Status '=== PB Studio beendet ===' 'Yellow'
        }
    }

    Write-Status "Backend läuft bereits auf http://${BackendHost}:${BackendPort}" 'Green'
    Write-Status 'BackendOnly: bestehender Backend-Prozess bleibt unverändert.' 'Yellow'
    Write-Status '=== PB Studio beendet ===' 'Yellow'
    exit 0
}

if (-not $BackendOnly) {
    $frontendExe = Resolve-FrontendExe
    if ($frontendExe) {
        Write-Status "Starte Frontend: $frontendExe"

        $env:PBSTUDIO_BACKEND_DIR = Join-Path $ProjectRoot 'backend'
        if (-not $FrontendOnly) {
            $env:PBSTUDIO_BACKEND_MANAGED_EXTERNALLY = '1'
        } else {
            Remove-Item Env:PBSTUDIO_BACKEND_MANAGED_EXTERNALLY -ErrorAction SilentlyContinue
        }
        try {
            $frontendProcess = Start-Process -FilePath $frontendExe -PassThru
        } finally {
            $env:PBSTUDIO_BACKEND_MANAGED_EXTERNALLY = $previousExternalBackendFlag
            $env:PBSTUDIO_BACKEND_DIR = $previousBackendDir
        }
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

if (-not $FrontendOnly -and $startedBackend -and ((Test-BackendHealth) -or ((Get-BackendListenerPids).Count -gt 0))) {
    Write-Status 'Stoppe Backend...'
    try {
        Invoke-RestMethod -Uri "http://${BackendHost}:${BackendPort}/shutdown" -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
    } catch {}

    if (-not (Wait-ForBackendShutdown -TimeoutSeconds 10 -ExpectedProcess $backendProcess)) {
        if ($backendProcess -and -not $backendProcess.HasExited) {
            Stop-ProcessTree -Process $backendProcess
        }
        Stop-BackendListeners
        [void](Wait-ForBackendShutdown -TimeoutSeconds 5)
    }
    Write-Status 'Backend gestoppt'
} elseif ($FrontendOnly -and -not $backendWasAlreadyRunning -and (Test-BackendHealth)) {
    Write-Status 'FrontendOnly: stoppe von der UI gestartetes Backend...' 'Yellow'
    try {
        Invoke-RestMethod -Uri "http://${BackendHost}:${BackendPort}/shutdown" -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
    } catch {}

    if (-not (Wait-ForBackendShutdown -TimeoutSeconds 10)) {
        Stop-BackendListeners
        [void](Wait-ForBackendShutdown -TimeoutSeconds 5)
    }
    Write-Status 'Backend gestoppt'
}

Write-Status '=== PB Studio beendet ===' 'Yellow'
