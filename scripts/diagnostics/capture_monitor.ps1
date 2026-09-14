#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$SessionId,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{7,64}$')]
    [string]$CommitSha,
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$SupervisorPid,
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$BackendPid,
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$WpfPid,
    [string]$SourceConfigPath = '',
    [ValidateRange(1, 60000)]
    [int]$PollMilliseconds = 250,
    [ValidateRange(1, 100)]
    [int]$ExitGracePolls = 4
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$root = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).Path)
$rootPrefix = $root.TrimEnd('\') + '\'
$output = [IO.Path]::GetFullPath($OutputPath)
$outputParent = Split-Path -Parent $output

function Assert-InRepo {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Purpose must stay inside the repository: $resolved"
    }
    return $resolved
}

[void](Assert-InRepo -Path $output -Purpose 'Capture output')
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    throw "Capture output directory missing: $outputParent"
}
if (Test-Path -LiteralPath $output) {
    throw "Capture output already exists; refusing to mix sessions: $output"
}
$uniqueProcessIds = @(@($SupervisorPid, $BackendPid, $WpfPid) | Select-Object -Unique)
if ($uniqueProcessIds.Count -ne 3) {
    throw 'SupervisorPid, BackendPid and WpfPid must identify three distinct processes'
}

$script:Sequence = 0L
$script:DropCount = 0L
$script:StopWritten = $false

function Write-CaptureRecord {
    param(
        [Parameter(Mandatory = $true)][string]$Tag,
        [Parameter(Mandatory = $true)][string]$Event,
        [string]$Message = '',
        [hashtable]$Data = @{}
    )

    $script:Sequence++
    $record = [ordered]@{
        schema_version = 1
        session_id = $SessionId
        sequence = $script:Sequence
        timestamp = [DateTimeOffset]::Now.ToString('o')
        drop_count = $script:DropCount
        tag = $Tag
        event = $Event
        message = $Message
        data = $Data
    }
    $line = ($record | ConvertTo-Json -Compress -Depth 8) + [Environment]::NewLine
    try {
        [IO.File]::AppendAllText($output, $line, $utf8)
    } catch {
        $script:DropCount++
        throw
    }
}

function Get-ProcessReceipt {
    param(
        [Parameter(Mandatory = $true)][string]$Role,
        [Parameter(Mandatory = $true)][int]$Id
    )

    try {
        $process = Get-Process -Id $Id -ErrorAction Stop
        $process.Refresh()
        # Force a query handle while the process is alive. Without this, a
        # Process object attached by PID can report a synthetic/null exit code
        # after Windows removes the process table entry.
        [void]$process.Handle
    } catch {
        throw "$Role process is not alive at capture start: PID $Id"
    }
    return [pscustomobject]@{
        Role = $Role
        Process = $process
        StartTimeUtc = $process.StartTime.ToUniversalTime().ToString('o')
        Executable = [string]$process.Path
        ExitRecorded = $false
    }
}

function Resolve-SourceStates {
    $definitions = @()
    if ([string]::IsNullOrWhiteSpace($SourceConfigPath)) {
        $logs = Join-Path $root 'logs'
        $definitions = @(
            @{ tag = 'LAUNCHER_OUT'; path = "logs\capture_${SessionId}_launcher.out.log"; session_owned = $true; start_offset = 0 },
            @{ tag = 'LAUNCHER_ERR'; path = "logs\capture_${SessionId}_launcher.err.log"; session_owned = $true; start_offset = 0 },
            @{ tag = 'BACKEND_OUT'; path = 'logs\backend_live.out.log'; session_owned = $false },
            @{ tag = 'BACKEND_ERR'; path = 'logs\backend_live.err.log'; session_owned = $false },
            @{ tag = 'DRIVER_BACKEND_OUT'; path = 'logs\driver_backend.out.log'; session_owned = $false },
            @{ tag = 'DRIVER_BACKEND_ERR'; path = 'logs\driver_backend.err.log'; session_owned = $false },
            @{ tag = 'WPF_LOG'; path = 'logs\wpf_app.log'; session_owned = $false },
            @{ tag = 'WPF_OUT'; path = "logs\capture_${SessionId}_wpf.out.log"; session_owned = $true; start_offset = 0 },
            @{ tag = 'WPF_ERR'; path = "logs\capture_${SessionId}_wpf.err.log"; session_owned = $true; start_offset = 0 }
        )
    } else {
        $config = Assert-InRepo -Path $SourceConfigPath -Purpose 'Source config'
        if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
            throw "Source config missing: $config"
        }
        $definitions = @(Get-Content -LiteralPath $config -Raw | ConvertFrom-Json)
    }

    $states = @()
    $seenTags = @{}
    foreach ($definition in $definitions) {
        $tag = [string]$definition.tag
        if ($tag -notmatch '^[A-Z0-9_]+$' -or $seenTags.ContainsKey($tag)) {
            throw "Source tag must be unique and contain only A-Z, 0-9 and _: $tag"
        }
        $seenTags[$tag] = $true

        $candidate = [string]$definition.path
        if (-not [IO.Path]::IsPathRooted($candidate)) {
            $candidate = Join-Path $root $candidate
        }
        $path = Assert-InRepo -Path $candidate -Purpose "Source $tag"
        $sessionOwned = [bool]$definition.session_owned
        $hasOffset = $definition.PSObject.Properties.Name -contains 'start_offset'
        if ($definition -is [hashtable]) {
            $hasOffset = $definition.ContainsKey('start_offset')
        }
        if ($hasOffset) {
            $startOffset = [long]$definition.start_offset
        } elseif (Test-Path -LiteralPath $path -PathType Leaf) {
            $startOffset = [long](Get-Item -LiteralPath $path).Length
        } else {
            $startOffset = 0L
        }
        if ($startOffset -lt 0) {
            throw "Source offset must be non-negative: $tag"
        }
        if ($sessionOwned -and $startOffset -ne 0) {
            throw "Session-owned source must start at offset 0: $tag"
        }
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $length = [long](Get-Item -LiteralPath $path).Length
            if ($startOffset -gt $length) {
                throw "Source offset exceeds current length for ${tag}: $startOffset > $length"
            }
        }

        $states += [pscustomobject]@{
            Tag = $tag
            Path = $path
            Position = $startOffset
            StartOffset = $startOffset
            SessionOwned = $sessionOwned
            Generation = 1
        }
    }
    return $states
}

function Read-NewLines {
    param([Parameter(Mandatory = $true)]$State)

    if (-not (Test-Path -LiteralPath $State.Path -PathType Leaf)) {
        return
    }
    try {
        $length = [long](Get-Item -LiteralPath $State.Path).Length
        if ($length -lt $State.Position) {
            $lostBytes = $State.Position - $length
            $script:DropCount++
            $State.Generation++
            $State.Position = 0L
            Write-CaptureRecord -Tag $State.Tag -Event 'source_rotated' -Data @{
                generation = $State.Generation
                detected_lost_bytes = $lostBytes
            }
        }

        $stream = New-Object IO.FileStream(
            $State.Path,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::ReadWrite
        )
        try {
            [void]$stream.Seek($State.Position, [IO.SeekOrigin]::Begin)
            $reader = New-Object IO.StreamReader($stream, $utf8, $true, 4096, $true)
            try {
                while (($line = $reader.ReadLine()) -ne $null) {
                    Write-CaptureRecord -Tag $State.Tag -Event 'source_line' -Message $line -Data @{
                        generation = $State.Generation
                    }
                }
                $State.Position = $stream.Position
            } finally {
                $reader.Dispose()
            }
        } finally {
            $stream.Dispose()
        }
    } catch {
        $script:DropCount++
        Write-CaptureRecord -Tag 'CAPTURE' -Event 'source_read_failed' -Message $_.Exception.Message -Data @{
            source_tag = $State.Tag
            generation = $State.Generation
        }
    }
}

function Update-ProcessReceipt {
    param([Parameter(Mandatory = $true)]$Receipt)

    if ($Receipt.ExitRecorded) {
        return
    }
    try {
        $Receipt.Process.Refresh()
        if (-not $Receipt.Process.HasExited) {
            return
        }
        $Receipt.Process.WaitForExit()
        $exitCode = [int]$Receipt.Process.ExitCode
    } catch {
        $exitCode = $null
    }
    $Receipt.ExitRecorded = $true
    Write-CaptureRecord -Tag 'PROCESS' -Event 'process_exited' -Data @{
        role = $Receipt.Role
        pid = $Receipt.Process.Id
        start_time_utc = $Receipt.StartTimeUtc
        exit_code = $exitCode
    }
}

$processReceipts = @(
    (Get-ProcessReceipt -Role 'supervisor' -Id $SupervisorPid),
    (Get-ProcessReceipt -Role 'backend' -Id $BackendPid),
    (Get-ProcessReceipt -Role 'wpf' -Id $WpfPid)
)
$sourceStates = @(Resolve-SourceStates)
$stopReason = 'completed'

try {
    Write-CaptureRecord -Tag 'CAPTURE' -Event 'monitor_started' -Data @{
        commit_sha = $CommitSha
        raw_log_policy = 'local_private'
        source_count = $sourceStates.Count
    }
    foreach ($receipt in $processReceipts) {
        Write-CaptureRecord -Tag 'PROCESS' -Event 'process_started' -Data @{
            role = $receipt.Role
            pid = $receipt.Process.Id
            start_time_utc = $receipt.StartTimeUtc
            executable = $receipt.Executable
        }
    }
    foreach ($state in $sourceStates) {
        Write-CaptureRecord -Tag 'CAPTURE' -Event 'source_started' -Data @{
            source_tag = $state.Tag
            path = $state.Path
            start_offset = $state.StartOffset
            session_owned = $state.SessionOwned
            generation = $state.Generation
        }
    }

    $gracePolls = 0
    while ($true) {
        foreach ($state in $sourceStates) {
            Read-NewLines -State $state
        }
        foreach ($receipt in $processReceipts) {
            Update-ProcessReceipt -Receipt $receipt
        }

        if (@($processReceipts | Where-Object { -not $_.ExitRecorded }).Count -eq 0) {
            $gracePolls++
            if ($gracePolls -ge $ExitGracePolls) {
                break
            }
        } else {
            $gracePolls = 0
        }
        Start-Sleep -Milliseconds $PollMilliseconds
    }
} catch {
    $stopReason = 'monitor_error'
    try {
        Write-CaptureRecord -Tag 'CAPTURE' -Event 'monitor_error' -Message $_.Exception.Message
    } catch {}
    throw
} finally {
    if (-not $script:StopWritten) {
        $script:StopWritten = $true
        Write-CaptureRecord -Tag 'CAPTURE' -Event 'monitor_stopped' -Data @{
            reason = $stopReason
            final_drop_count = $script:DropCount
        }
    }
}
