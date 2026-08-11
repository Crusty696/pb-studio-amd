#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [Parameter(Mandatory = $true)]
    [ValidateRange(0, 2147483647)]
    [int]$ClipId,
    [string]$RepoRoot = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$root = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $RepoRoot).Path)
$runtimeScript = Join-Path $root 'scripts\runtime_contract.ps1'
$ownerScript = Join-Path $root 'scripts\owner_capability.ps1'
$logs = Join-Path $root 'logs'
$sessionId = [guid]::NewGuid().ToString('N')

. $runtimeScript
$runtime = Get-PBStudioRuntimeContract `
    -ProjectRoot $root `
    -RequirePython `
    -RequireFFmpeg `
    -ApplyEnvironment
$ownerCapability = [string](& $ownerScript)
$env:PBSTUDIO_OWNER_CAPABILITY = $ownerCapability
$headers = @{ 'X-PBStudio-Owner-Capability' = $ownerCapability }
$projectBody = @{ path = $ProjectPath } | ConvertTo-Json -Compress
$analysisBody = @{
    clip_id = $ClipId
    detect_scenes = $false
    generate_embeddings = $false
    analyze_motion = $false
    generate_captions = $true
    analyze_colors = $true
    analyze_audio_key = $false
    force = $false
} | ConvertTo-Json -Compress

function Start-OwnedBackend {
    param([Parameter(Mandatory = $true)][string]$Suffix)

    $stdout = Join-Path $logs "obj76_resume_${sessionId}_${Suffix}.out.log"
    $stderr = Join-Path $logs "obj76_resume_${sessionId}_${Suffix}.err.log"
    $process = Start-Process `
        -FilePath $runtime.PythonExe `
        -ArgumentList @($runtime.BackendArguments) `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if ($process.HasExited) {
            throw "Backend exited during startup: $($process.ExitCode)"
        }
        try {
            $health = Invoke-RestMethod `
                -Uri 'http://127.0.0.1:8765/health' `
                -TimeoutSec 2
            if ($health.status -eq 'ok') {
                return $process
            }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'Backend startup timeout'
}

function Stop-OwnedBackend {
    param($Process)

    if ($null -eq $Process -or $Process.HasExited) {
        return
    }
    try {
        Invoke-RestMethod `
            -Uri 'http://127.0.0.1:8765/shutdown' `
            -Method Post `
            -Headers $headers `
            -TimeoutSec 10 | Out-Null
    } catch {
    }
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline -and -not $Process.HasExited) {
        Start-Sleep -Milliseconds 500
    }
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
        $Process.WaitForExit()
    }
}

function Invoke-Analysis {
    param([Parameter(Mandatory = $true)]$Process)

    Invoke-RestMethod `
        -Uri 'http://127.0.0.1:8765/project/open' `
        -Method Post `
        -Headers $headers `
        -ContentType 'application/json' `
        -Body $projectBody `
        -TimeoutSec 60 | Out-Null
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-RestMethod `
        -Uri 'http://127.0.0.1:8765/video/analyze' `
        -Method Post `
        -Headers $headers `
        -ContentType 'application/json' `
        -Body $analysisBody `
        -TimeoutSec 300
    $watch.Stop()
    return [pscustomobject]@{
        elapsed_seconds = [math]::Round($watch.Elapsed.TotalSeconds, 3)
        response = $response
    }
}

function Get-TruthHash {
    param([Parameter(Mandatory = $true)]$Response)

    $truth = [ordered]@{
        tags = @($Response.tags)
        tag_source = $Response.tag_source
        dominant_colors = @($Response.dominant_colors)
        captions = $Response.stage_status.captions
        colors = $Response.stage_status.colors
    } | ConvertTo-Json -Compress -Depth 6
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($truth)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

$firstProcess = $null
$secondProcess = $null
try {
    $firstProcess = Start-OwnedBackend -Suffix 'first'
    $first = Invoke-Analysis -Process $firstProcess
    Stop-OwnedBackend -Process $firstProcess
    $firstProcess = $null

    $secondProcess = Start-OwnedBackend -Suffix 'second'
    $second = Invoke-Analysis -Process $secondProcess
    $firstHash = Get-TruthHash -Response $first.response
    $secondHash = Get-TruthHash -Response $second.response

    [pscustomobject]@{
        schema_version = 1
        session_id = $sessionId
        first_elapsed_seconds = $first.elapsed_seconds
        first_status = $first.response.status
        first_tags = @($first.response.tags)
        first_tag_source = $first.response.tag_source
        first_stage_status = $first.response.stage_status
        first_stage_errors = $first.response.stage_errors
        second_elapsed_seconds = $second.elapsed_seconds
        second_status = $second.response.status
        second_tags = @($second.response.tags)
        second_tag_source = $second.response.tag_source
        second_stage_status = $second.response.stage_status
        second_stage_errors = $second.response.stage_errors
        truth_hash_equal = $firstHash -eq $secondHash
        truth_sha256 = $firstHash
    } | ConvertTo-Json -Depth 8
} finally {
    Stop-OwnedBackend -Process $secondProcess
    Stop-OwnedBackend -Process $firstProcess
    Remove-Item Env:\PBSTUDIO_OWNER_CAPABILITY -ErrorAction SilentlyContinue
}
