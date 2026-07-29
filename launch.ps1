#Requires -Version 5.1
<#!
.SYNOPSIS
    PB Studio AMD - Launcher Script
.DESCRIPTION
    Startet das Python FastAPI Backend und das C# WPF Frontend.
    Backend: localhost:8765 (Python + FastAPI + Uvicorn)
    Frontend: PBStudio.UI.exe (.NET 9.0 WPF)
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Debug,
    [switch]$NoPause,
    [string]$PublishedDir,
    [ValidateSet('framework', 'selfcontained', 'singlefile')]
    [string]$PreferredPublishMode
)

# Continue: native exe stderr (uvicorn Startup-Msgs etc.) darf nicht abbrechen.
# Kritische Fehler werden via explizite exit-Aufrufe behandelt.
$ErrorActionPreference = 'Continue'

$LogsDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }
$LaunchLog = Join-Path $LogsDir ("launch_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

function Append-Log([string]$msg) {
    Add-Content -Path $LaunchLog -Value "[$(Get-Date -Format HH:mm:ss)] $msg" -Encoding utf8
}

# Globaler Trap: schreibt Fehler ins Log und haelt Fenster offen
trap {
    $err = $_
    $msg = "FATAL: $($err.Exception.Message)`n$($err.ScriptStackTrace)"
    Append-Log $msg
    Write-Host ""
    Write-Host "  [FATAL] Unbehandelter Fehler - Log: $LaunchLog" -ForegroundColor Red
    Write-Host "  $($err.Exception.Message)" -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Press Enter to exit" }
    exit 99
}

Append-Log "launch.ps1 gestartet"
$ProjectRoot = $PSScriptRoot
. (Join-Path $ProjectRoot 'scripts\runtime_contract.ps1')
$BackendPort = 8765
$BackendHost = '127.0.0.1'
$HealthCheckUrl = "http://${BackendHost}:${BackendPort}/health"
$MaxStartupWaitSeconds = 30
$startedBackend = $false
$backendProcess = $null
$backendWasAlreadyRunning = $false
$previousExternalBackendFlag = $env:PBSTUDIO_BACKEND_MANAGED_EXTERNALLY
$previousBackendDir = $env:PBSTUDIO_BACKEND_DIR
# $LogsDir already set above; $BackendStdOutLog + $BackendStdErrLog follow
$BackendStdOutLog = Join-Path $LogsDir 'backend_live.out.log'
$BackendStdErrLog = Join-Path $LogsDir 'backend_live.err.log'

function Initialize-OwnerCapability {
    if (-not [string]::IsNullOrWhiteSpace($env:PBSTUDIO_OWNER_CAPABILITY)) {
        return
    }
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    } finally {
        $generator.Dispose()
    }
    $env:PBSTUDIO_OWNER_CAPABILITY = [Convert]::ToBase64String($bytes)
}

function Write-Status($msg, $color = 'Cyan') {
    Write-Host '[PB Studio] ' -NoNewline -ForegroundColor $color
    Write-Host $msg
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

    return $null
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

    # FIX 2026-05-09: Sammle ALLE Kandidaten, waehle die NEUESTE per LastWriteTime
    # statt erste-gefunden-Logik. Verhindert dass alte artifacts/publish/ EXE
    # ueber frisches bin/Release/ Build geladen wird (typischer dev-loop bug).
    $candidates += @(
        (Join-Path $ProjectRoot 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe')
    )

    foreach ($mode in @('framework', 'selfcontained', 'singlefile')) {
        $publishedExe = Get-LatestPublishedExe -BaseDir (Join-Path $ProjectRoot (Join-Path 'artifacts\publish' $mode))
        if ($publishedExe) {
            $candidates += $publishedExe
        }
    }

    # Pick NEWEST candidate by LastWriteTimeUtc
    $existing = $candidates | Where-Object { Test-Path $_ } | ForEach-Object { Get-Item $_ -ErrorAction SilentlyContinue }
    $newest = $existing | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($newest) {
        Write-Status "Resolved Frontend (newest by mtime): $($newest.FullName)" 'DarkGray'
        return $newest.FullName
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
$Runtime = Get-PBStudioRuntimeContract -ProjectRoot $ProjectRoot -RequirePython -RequireFFmpeg -ApplyEnvironment
$PythonExe = $Runtime.PythonExe
$pyVersion = & $PythonExe --version 2>&1
Write-Status "Python: $pyVersion"
Write-Status "FFmpeg: $($Runtime.FfmpegVersion) ($($Runtime.FfmpegExe))"

# --- Headless Start & API-Verbindungstests für Ollama und LM Studio ---
Write-Status 'Überprüfe lokale KI-Dienste (Ollama & LM Studio)...' 'DarkGray'

# Hilfsfunktionen für echte API-Verbindungstests
function Test-OllamaApi {
    try {
        $response = Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -ErrorAction SilentlyContinue
        return ($null -ne $response) -and ($null -ne $response.models)
    } catch {
        return $false
    }
}

function Test-LmsApi([int]$port) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:${port}/v1/models" -TimeoutSec 2 -ErrorAction SilentlyContinue
        return ($null -ne $response) -and ($null -ne $response.data)
    } catch {
        return $false
    }
}

# 1. Ollama check & headless start
$ollamaRunning = Test-OllamaApi
if (-not $ollamaRunning) {
    # Falls API nicht antwortet, prüfe ob der Prozess überhaupt läuft
    $ollamaProc = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
    if ($ollamaProc) {
        Write-Status "Ollama-Prozess läuft bereits, aber die API antwortet nicht. Warte auf API..." 'Yellow'
        $ollamaRunning = $true
    }
}

if (-not $ollamaRunning) {
    $ollamaCmd = Get-Command "ollama" -ErrorAction SilentlyContinue
    if ($ollamaCmd) {
        Write-Status "Ollama-API ist inaktiv. Starte headless im Hintergrund..." 'Yellow'
        $null = Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        
        # Warte auf echte API-Bereitschaft (Modell-Schnittstelle)
        Write-Status "Warte auf Ollama-API-Bereitschaft (Modell-Schnittstelle)..." 'DarkGray'
        $deadline = (Get-Date).AddSeconds(15)
        $startedOk = $false
        while ((Get-Date) -lt $deadline) {
            if (Test-OllamaApi) {
                Write-Status "Ollama-API ist erfolgreich bereit und reagiert!" 'Green'
                $startedOk = $true
                break
            }
            Start-Sleep -Seconds 1
        }
        if (-not $startedOk) {
            Write-Status "Ollama-API antwortet nach 15s noch nicht. Wird im Hintergrund fortgesetzt." 'Yellow'
        }
    } else {
        Write-Status "Ollama ist auf diesem System nicht im PATH installiert (Überspringe Start)." 'DarkGray'
    }
} else {
    Write-Status "Ollama-API ist bereits aktiv und reagiert erfolgreich." 'Green'
}

# 2. LM Studio check & headless start
$lmsPorts = @(1234, 12341)
$activeLmsPort = $null
$lmsRunning = $false

# Prüfe, ob einer der Ports bereits auf echte API-Anfragen reagiert
foreach ($port in $lmsPorts) {
    if (Test-LmsApi -port $port) {
        $activeLmsPort = $port
        $lmsRunning = $true
        break
    }
}

if (-not $lmsRunning) {
    # Suche lms CLI
    $lmsCandidates = @(
        "$env:USERPROFILE\.lmstudio\bin\lms.exe",
        "$env:USERPROFILE\.lmstudio\bin\lms.cmd",
        "$env:LOCALAPPDATA\Programs\LM Studio\resources\app\.webpack\main\lms.exe"
    )
    $lms = $null
    foreach ($p in $lmsCandidates) {
        if (Test-Path $p) { $lms = $p; break }
    }
    if (-not $lms) {
        try { $found = (Get-Command lms -ErrorAction Stop).Source; if ($found) { $lms = $found } } catch {}
    }

    if ($lms) {
        Write-Status "LM Studio Server läuft nicht. Starte headless via lms CLI..." 'Yellow'
        $null = Start-Process -FilePath $lms -ArgumentList "server", "start" -WindowStyle Hidden
        
        # Warte auf echte API-Bereitschaft (Modell-Daten)
        Write-Status "Warte auf LM Studio API-Bereitschaft..." 'DarkGray'
        $deadline = (Get-Date).AddSeconds(20)
        $startedOk = $false
        while ((Get-Date) -lt $deadline) {
            foreach ($port in $lmsPorts) {
                if (Test-LmsApi -port $port) {
                    $activeLmsPort = $port
                    $lmsRunning = $true
                    break
                }
            }
            if ($lmsRunning) {
                Write-Status "LM Studio API ist erfolgreich bereit und reagiert (Port $activeLmsPort)!" 'Green'
                $startedOk = $true
                break
            }
            Start-Sleep -Seconds 1
        }
        if (-not $startedOk) {
            Write-Status "LM Studio API antwortet nach 20s noch nicht. Wird im Hintergrund fortgesetzt." 'Yellow'
        }
    } else {
        Write-Status "LM Studio (lms CLI) ist auf diesem System nicht installiert (Überspringe Start)." 'DarkGray'
    }
} else {
    Write-Status "LM Studio API ist bereits aktiv und reagiert erfolgreich (Port $activeLmsPort)." 'Green'
}

# Provision the destructive-operation capability only after third-party model
# runtimes have started, so they never inherit the backend/WPF secret.
Initialize-OwnerCapability

if (-not $FrontendOnly) {
    if (Test-BackendHealth) {
        Write-Status "Backend läuft bereits auf http://${BackendHost}:${BackendPort}" 'Green'
    } else {
        Write-Status 'Starte Python Backend...'

        $backendArgs = @($Runtime.BackendArguments)
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

        # Portables dotnet bevorzugen und fuer den Child-Prozess bereitstellen
        $DotnetExe = Resolve-DotnetExe
        if ($DotnetExe -and ($DotnetExe -like "*tools\dotnet*")) {
            $dotnetDir = Split-Path $DotnetExe -Parent
            $env:DOTNET_ROOT = $dotnetDir
            $env:Path = "$dotnetDir;$env:Path"
            Write-Status "Nutze portables .NET Runtime ($dotnetDir)" "DarkGray"
        }

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
        Invoke-RestMethod `
            -Uri "http://${BackendHost}:${BackendPort}/shutdown" `
            -Method Post `
            -Headers @{ 'X-PBStudio-Owner-Capability' = $env:PBSTUDIO_OWNER_CAPABILITY } `
            -TimeoutSec 5 `
            -ErrorAction SilentlyContinue | Out-Null
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
        Invoke-RestMethod `
            -Uri "http://${BackendHost}:${BackendPort}/shutdown" `
            -Method Post `
            -Headers @{ 'X-PBStudio-Owner-Capability' = $env:PBSTUDIO_OWNER_CAPABILITY } `
            -TimeoutSec 5 `
            -ErrorAction SilentlyContinue | Out-Null
    } catch {}

    if (-not (Wait-ForBackendShutdown -TimeoutSeconds 10)) {
        Stop-BackendListeners
        [void](Wait-ForBackendShutdown -TimeoutSeconds 5)
    }
    Write-Status 'Backend gestoppt'
}

Write-Status '=== PB Studio beendet ===' 'Yellow'
