#Requires -Version 5.1
param(
    [string]$BaseUrl = 'http://127.0.0.1:8765',
    [string]$ProjectPath = $PSScriptRoot,
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
if (-not $OutputPath) {
    $OutputPath = Join-Path $ProjectPath 'data\release_smoke_render.mp4'
}

$script:StartedBackend = $false
$script:BackendProcess = $null

function Step($name, [scriptblock]$action) {
    Write-Host "[SMOKE] $name" -ForegroundColor Cyan
    & $action
}

function Get-Json($url) {
    Invoke-RestMethod -Uri ($BaseUrl + $url) -Method Get -TimeoutSec 60
}

function Post-Json($url, $body) {
    $json = if ($null -eq $body) { $null } else { $body | ConvertTo-Json -Depth 10 }
    Invoke-RestMethod -Uri ($BaseUrl + $url) -Method Post -ContentType 'application/json' -Body $json -TimeoutSec 300
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

function Ensure-Backend {
    if (Test-Health) {
        Write-Host '  backend already running'
        return
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

try {
    Step 'Health / backend startup' {
        Ensure-Backend
        $health = Get-Json '/health'
        if ($health.status -ne 'ok') { throw 'Health check failed' }
        Write-Host "  ok | GPU available = $($health.gpu_available)"
    }

    Step 'Open active project root' {
        $project = Post-Json '/project/open' @{ path = $ProjectPath }
        Write-Host "  opened | $($project.name)"
    }

    Step 'Load audio/video clip lists' {
        $audio = Get-Json '/audio/clips?page=1&limit=20'
        $video = Get-Json '/video/clips?page=1&limit=20'
        if (-not $audio -or $audio.Count -lt 1) { throw 'No audio clips available' }
        if (-not $video -or $video.Count -lt 2) { throw 'Need at least 2 video clips' }

        $script:AudioClip = $audio[0]
        $script:VideoClipIds = @($video[0].id, $video[1].id)
        if ($video.Count -ge 3) { $script:VideoClipIds += $video[2].id }

        Write-Host "  audio=$($AudioClip.id) video=$($VideoClipIds -join ',')"
    }

    Step 'Analyze audio + waveform + beats' {
        $analysis = Post-Json '/audio/analyze' @{ clip_id = $AudioClip.id }
        if (-not $analysis) { throw 'Audio analysis failed' }

        $waveform = Get-Json "/audio/waveform/$($AudioClip.id)?bands=3"
        if (-not $waveform.bands) { throw 'Waveform missing' }

        $beats = Get-Json "/audio/beats/$($AudioClip.id)"
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
        if (Test-Path $OutputPath) { Remove-Item $OutputPath -Force }

        $timeline = Get-Json '/pacing/timeline'
        $render = Post-Json '/render/start' @{
            output_path = $OutputPath
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

        if ($final.status -notin @('cancelled', 'completed')) {
            throw "Unexpected render final status: $($final.status)"
        }
        Write-Host "  render task=$taskId final=$($final.status)"
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
