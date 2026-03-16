#Requires -Version 5.1
param(
    [string]$BaseUrl = 'http://127.0.0.1:8765',
    [string]$ProjectPath = $PSScriptRoot,
    [string]$OutputPath = '',
    [string]$AllowedProjectRoot = '',
    [switch]$ReuseExistingBackend
)

$ErrorActionPreference = 'Stop'
$ProjectPath = (Resolve-Path $ProjectPath).Path

$script:StartedBackend = $false
$script:BackendProcess = $null

function Step($name, [scriptblock]$action) {
    Write-Host "[SMOKE] $name" -ForegroundColor Cyan
    & $action
}

function Convert-JsonResponse($response) {
    if ($null -eq $response) {
        return $null
    }

    $content = $response.Content
    if ([string]::IsNullOrWhiteSpace($content)) {
        return $null
    }

    return $content | ConvertFrom-Json -NoEnumerate
}

function Get-Json($url) {
    $response = Invoke-WebRequest -Uri ($BaseUrl + $url) -Method Get -TimeoutSec 60
    return Convert-JsonResponse $response
}

function Post-Json($url, $body) {
    $json = if ($null -eq $body) { $null } else { $body | ConvertTo-Json -Depth 10 }

    for ($attempt = 1; $attempt -le 2; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri ($BaseUrl + $url) -Method Post -ContentType 'application/json' -Body $json -TimeoutSec 300
            return Convert-JsonResponse $response
        }
        catch {
            if ($attempt -ge 2) {
                throw
            }

            Start-Sleep -Milliseconds 750
            if (-not (Test-Health)) {
                throw "Backend unavailable during POST $url"
            }
        }
    }
}

function Test-Health {
    try {
        $health = Get-Json '/health'
        return $health.status -eq 'ok'
    } catch {
        return $false
    }
}

function Resolve-PythonExe {
    $candidates = @(
        (Join-Path $ProjectPath '.venv\Scripts\python.exe'),
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

    throw 'Python executable not found for backend startup.'
}

function Wait-BackendStopped {
    param(
        [int]$TimeoutSeconds = 20,
        [int]$RequiredConsecutiveFailures = 3
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $failures = 0
    while ((Get-Date) -lt $deadline) {
        if (Test-Health) {
            $failures = 0
        }
        else {
            $failures += 1
            if ($failures -ge $RequiredConsecutiveFailures) {
                Start-Sleep -Seconds 2
                return $true
            }
        }
        Start-Sleep -Milliseconds 500
    }

    return $false
}

function Ensure-Backend {
    if (Test-Health) {
        if ($ReuseExistingBackend) {
            Write-Host '  backend already running (reuse enabled)'
            return
        }

        Write-Host '  restarting existing backend for isolated smoke run'
        try {
            Invoke-RestMethod -Uri ($BaseUrl + '/shutdown') -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
        }
        catch { }

        if (-not (Wait-BackendStopped)) {
            throw 'Existing backend stayed alive; refusing non-isolated smoke run.'
        }
    }

    $pythonExe = Resolve-PythonExe
    $env:PYTHONPATH = Join-Path $ProjectPath 'src'
    $args = @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8765')
    $script:BackendProcess = Start-Process -FilePath $pythonExe -ArgumentList $args -WorkingDirectory $ProjectPath -WindowStyle Minimized -PassThru
    $script:StartedBackend = $true

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health) {
            Write-Host "  backend started (pid=$($script:BackendProcess.Id))"
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw 'Backend failed to start for release smoke.'
}

function Get-AllowedProjectRoot {
    if ($AllowedProjectRoot) {
        if (-not (Test-Path $AllowedProjectRoot)) {
            New-Item -ItemType Directory -Path $AllowedProjectRoot -Force | Out-Null
        }
        return (Resolve-Path $AllowedProjectRoot).Path
    }

    try {
        $pythonExe = Resolve-PythonExe
        $configured = & $pythonExe -c "from backend.config import config; print(config.project_dir)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $configured) {
            $configuredPath = $configured.Trim()
            if (-not (Test-Path $configuredPath)) {
                New-Item -ItemType Directory -Path $configuredPath -Force | Out-Null
            }
            return (Resolve-Path $configuredPath).Path
        }
    } catch {}

    $fallback = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'PBStudio'
    if (-not (Test-Path $fallback)) {
        New-Item -ItemType Directory -Path $fallback -Force | Out-Null
    }
    return (Resolve-Path $fallback).Path
}

function Ensure-VerificationMedia {
    $fixtureRoot = Join-Path (Get-AllowedProjectRoot) 'E2E_Complete'
    $scriptPath = Join-Path $ProjectPath 'scripts\ensure_verification_media.py'
    if (-not (Test-Path $scriptPath)) {
        throw "Verification media helper missing: $scriptPath"
    }

    $pythonExe = Resolve-PythonExe
    $output = & $pythonExe $scriptPath $fixtureRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Verification media generation failed for $fixtureRoot"
    }

    $result = @{}
    foreach ($line in $output) {
        if ($line -match '^(?<key>[^=]+)=(?<value>.+)$') {
            $result[$Matches['key']] = $Matches['value']
        }
    }

    foreach ($required in @('audio', 'video_a', 'video_b')) {
        if (-not $result.ContainsKey($required) -or -not (Test-Path $result[$required])) {
            throw "Verification media missing after generation: $required"
        }
    }

    return $result
}

function Resolve-SampleAudioPath {
    $fixtures = Ensure-VerificationMedia
    return $fixtures['audio']
}

function Resolve-SampleVideoPaths {
    $fixtures = Ensure-VerificationMedia
    return @($fixtures['video_a'], $fixtures['video_b'])
}

try {
    $verifyRoot = Get-AllowedProjectRoot
    $verifyName = 'ReleaseSmoke_{0}' -f (Get-Date -Format 'yyyyMMdd_HHmmss')
    $sampleAudioPath = Resolve-SampleAudioPath
    $sampleVideoPaths = Resolve-SampleVideoPaths

    Step 'Health / backend startup' {
        Ensure-Backend
        $health = Get-Json '/health'
        if ($health.status -ne 'ok') { throw 'Health check failed' }
        Write-Host "  ok | GPU available = $($health.gpu_available)"
    }

    Step 'Create verify project in allowed root' {
        $project = Post-Json '/project/create' @{ name = $verifyName; path = $verifyRoot }
        if (-not $project.path) { throw 'Verify project creation returned no path' }
        $script:SmokeProjectPath = $project.path
        Write-Host "  opened | $($project.name) | path=$($script:SmokeProjectPath)"
    }

    Step 'Import smoke media' {
        $audioImport = Post-Json '/audio/import' @{ path = $sampleAudioPath }
        if (-not $audioImport.id) { throw 'Audio import failed for release smoke' }

        $videoImport = Post-Json '/video/import' @{ paths = $sampleVideoPaths }
        if (-not $videoImport -or $videoImport.Count -lt 2) { throw 'Video import failed for release smoke' }

        if (-not $script:OutputPath) {
            $script:OutputPath = Join-Path $script:SmokeProjectPath ('output\release_smoke_render_{0}.mp4' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
        }

        Write-Host "  audio=$sampleAudioPath"
        Write-Host "  video=$($sampleVideoPaths -join ', ')"
    }

    Step 'Load audio/video clip lists' {
        $audio = @(Get-Json '/audio/clips?page=1&limit=50')
        $video = @(Get-Json '/video/clips?page=1&limit=50')
        if (-not $audio -or $audio.Count -lt 1) { throw 'No audio clips available' }
        if (-not $video -or $video.Count -lt 2) { throw 'Need at least 2 video clips' }

        $preferredAudio = $audio |
            Where-Object { $_.duration_seconds -gt 0 -and $_.duration_seconds -le 120 } |
            Sort-Object duration_seconds |
            Select-Object -First 1
        if (-not $preferredAudio) {
            $preferredAudio = $audio |
                Where-Object { $_.duration_seconds -gt 0 } |
                Sort-Object duration_seconds |
                Select-Object -First 1
        }
        if (-not $preferredAudio) {
            $preferredAudio = $audio[0]
        }

        $preferredVideos = $video |
            Where-Object { $_.duration_seconds -gt 0 } |
            Sort-Object duration_seconds |
            Select-Object -First 3
        if ($preferredVideos.Count -lt 2) { throw 'Need at least 2 usable video clips' }

        $script:AudioClip = $preferredAudio
        $script:VideoClipIds = @($preferredVideos[0].id, $preferredVideos[1].id)
        if ($preferredVideos.Count -ge 3) { $script:VideoClipIds += $preferredVideos[2].id }

        Write-Host "  audio=$($AudioClip.id) duration=$([math]::Round([double]$AudioClip.duration_seconds,2))s video=$($VideoClipIds -join ',')"
    }

    Step 'Analyze audio + waveform + beats' {
        $analysis = Post-Json '/audio/analyze' @{ clip_id = $AudioClip.id }
        if (-not $analysis) { throw 'Audio analysis failed' }

        $waveform = Get-Json "/audio/waveform/$($AudioClip.id)?bands=3"
        if (-not $waveform.bands) { throw 'Waveform missing' }

        $beats = @(Get-Json "/audio/beats/$($AudioClip.id)")
        if ($beats.Count -lt 1) { throw 'Beats missing after analysis' }

        Write-Host "  bpm=$($analysis.bpm) beats=$($beats.Count)"
    }

    Step 'Generate pacing + timeline' {
        $body = @{
            audio_clip_id = $AudioClip.id
            video_clip_ids = $VideoClipIds
            expected_bpm = if ($AudioClip.bpm -gt 0) { [double]$AudioClip.bpm } else { 120.0 }
            use_motion_matching = $false
            use_structure_awareness = $false
            duration_limit = 5.0
            min_cut_interval = 0.5
            trigger_settings = @{
                beat_weight = 1.0
                onset_weight = 0.5
                kick_weight = 1.2
                snare_weight = 1.0
                hihat_weight = 0.3
                energy_weight = 0.8
                energy_threshold = 0.6
                min_clip_length = 1.0
                max_clip_length = 8.0
                onset_sensitivity = 0.5
            }
        }

        $null = Post-Json '/pacing/generate' $body
        $timeline = Get-Json '/pacing/timeline'
        if (-not $timeline.entries -or $timeline.entries.Count -lt 1) { throw 'Timeline generation failed' }
        Write-Host "  cuts=$($timeline.entries.Count) duration=$([math]::Round($timeline.total_duration,2))s"
    }

    Step 'Save project state' {
        $save = Post-Json '/project/save' $null
        if (-not $save.success) { throw 'Project save failed' }
        Write-Host '  save ok'
    }

    Step 'Render start + cancel proof' {
        $renderOutputPath = $script:OutputPath
        if (-not $renderOutputPath) {
            $renderOutputPath = Join-Path $script:SmokeProjectPath ('output\release_smoke_render_{0}.mp4' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
            $script:OutputPath = $renderOutputPath
        }

        $outputDir = Split-Path -Parent $renderOutputPath
        if ($outputDir) {
            New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
        }
        if (Test-Path $renderOutputPath) { Remove-Item $renderOutputPath -Force }

        $timeline = Get-Json '/pacing/timeline'
        $render = Post-Json '/render/start' @{
            output_path = $renderOutputPath
            audio_path = $timeline.audio_path
            quality = 'preview'
            resolution_width = 640
            resolution_height = 360
            fps = 24
            bitrate_mbps = 8.0
            include_audio = $true
        }

        if (-not $render.task_id) { throw 'Render start failed' }
        $taskId = $render.task_id
        Start-Sleep -Milliseconds 800
        $null = Post-Json "/render/cancel/$taskId" $null

        $final = $null
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 500
            $final = Get-Json "/render/status/$taskId"
            if ($final.status -in @('cancelled', 'completed', 'failed')) { break }
        }

        if ($final.status -eq 'failed') {
            throw "Render task failed during cancel proof: $($final.error)"
        }
        if ($final.status -notin @('cancelled', 'completed')) {
            throw "Unexpected render final status: $($final.status)"
        }
        Write-Host "  render task=$taskId final=$($final.status) output=$renderOutputPath"
    }

    Write-Host '[SMOKE] PASS' -ForegroundColor Green
}
finally {
    if ($script:StartedBackend -and $script:BackendProcess -and -not $script:BackendProcess.HasExited) {
        try {
            Invoke-RestMethod -Uri ($BaseUrl + '/shutdown') -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
            Start-Sleep -Seconds 2
        } catch {}
        if (-not $script:BackendProcess.HasExited) {
            $script:BackendProcess.Kill()
        }
    }
}
