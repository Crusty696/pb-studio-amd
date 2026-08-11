#Requires -Version 5.1
<#
.SYNOPSIS
    PB Studio AMD - Agent Driver (programmatic launch + smoke + screenshot)

.DESCRIPTION
    Agent-facing wrapper that drives the hybrid app (Python FastAPI backend on
    127.0.0.1:8765 + WPF frontend) without needing manual button clicks.

    Commands:
      check          - venv / Release exe / ffmpeg present?
      start-backend  - launch uvicorn, wait /health, print PID
      stop-backend   - POST /shutdown, then taskkill listeners
      health         - GET /health + /gpu/status + /brain/stats
      smoke          - headless: start-backend -> probe endpoints -> stop-backend
      start-full     - backend + WPF frontend (returns when frontend pid alive)
      screenshot     - capture full primary screen to PNG (Add-Type Drawing)
      full-smoke     - start-full + wait + screenshot + kill all (1-shot demo)

.PARAMETER Command
    Sub-command (see above)

.PARAMETER OutFile
    Screenshot output path (default: logs/agent_<ts>.png)

.PARAMETER WaitSec
    Seconds to wait for UI to render before screenshot (default: 25)
#>
param(
    [Parameter(Mandatory)]
    [ValidateSet('check', 'start-backend', 'stop-backend', 'health', 'smoke',
                 'start-full', 'screenshot', 'full-smoke')]
    [string]$Command,
    [string]$OutFile,
    [int]$WaitSec = 25
)

$ErrorActionPreference = 'Continue'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\')).Path.TrimEnd('\')
$BackendHost = '127.0.0.1'
$BackendPort = 8765
$BaseUrl = "http://${BackendHost}:${BackendPort}"
$BackendStartupDeadlineSeconds = 90
$OwnerCapabilityHeader = 'X-PBStudio-Owner-Capability'
$ScriptsDir = Join-Path $ProjectRoot 'scripts'
$script:Runtime = $null
$LogsDir = Join-Path $ProjectRoot 'logs'
if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }

function Log($msg, $color = 'Cyan') {
    Write-Host "[driver] " -NoNewline -ForegroundColor $color
    Write-Host $msg
}

function Initialize-DriverSession {
    if ($null -ne $script:Runtime) {
        return $script:Runtime
    }

    $runtimeScript = Join-Path $ScriptsDir 'runtime_contract.ps1'
    $ownerScript = Join-Path $ScriptsDir 'owner_capability.ps1'
    if (-not (Test-Path -LiteralPath $runtimeScript -PathType Leaf)) {
        throw "Runtime contract missing: $runtimeScript"
    }
    if (-not (Test-Path -LiteralPath $ownerScript -PathType Leaf)) {
        throw "Owner capability script missing: $ownerScript"
    }

    . $runtimeScript
    $script:Runtime = Get-PBStudioRuntimeContract `
        -ProjectRoot $ProjectRoot `
        -RequirePython `
        -RequireFFmpeg `
        -ApplyEnvironment

    $ownerCapability = [string](& $ownerScript)
    try {
        $ownerCapabilityBytes = [Convert]::FromBase64String($ownerCapability)
    } catch {
        throw 'Owner capability script returned an invalid value'
    }
    if ($ownerCapabilityBytes.Length -ne 32) {
        throw 'Owner capability script must return a base64-encoded 32-byte value'
    }
    $env:PBSTUDIO_OWNER_CAPABILITY = $ownerCapability
    return $script:Runtime
}

function Test-Health {
    try {
        $r = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $r.status -eq 'ok'
    } catch { return $false }
}

function Get-BackendPids {
    $c = Get-NetTCPConnection -LocalAddress $BackendHost -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
    if (-not $c) { return @() }
    return @($c | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Resolve-Python {
    return (Initialize-DriverSession).PythonExe
}

function Resolve-FrontendExe {
    $rel = Join-Path $ProjectRoot 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe'
    $dbg = Join-Path $ProjectRoot 'PBStudio.UI\bin\Debug\net9.0-windows\PBStudio.UI.exe'
    if (Test-Path $rel) { return $rel }
    if (Test-Path $dbg) { return $dbg }
    throw "Frontend exe missing - run: dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release"
}

function Invoke-Check {
    Log "ProjectRoot: $ProjectRoot"
    try {
        $runtime = Initialize-DriverSession
    } catch {
        Log "Runtime contract FAIL: $($_.Exception.Message)" 'Red'
        exit 1
    }
    $py = $runtime.PythonExe
    $rel = Join-Path $ProjectRoot 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe'
    $ffmpeg = $runtime.FfmpegExe
    $ok = $true
    Log "Python contract OK: $py" 'Green'
    Log "LHM trust OK: manifest=$($runtime.LhmManifestSha256), library=$($runtime.LhmLibrarySha256)" 'Green'
    if (Test-Path $rel) {
        $age = (Get-Date) - (Get-Item $rel).LastWriteTime
        Log ("Release exe OK ({0:N1}h old): $rel" -f $age.TotalHours) 'Green'
    } else { Log "Release exe MISSING - run dotnet build -c Release" 'Yellow'; $ok = $false }
    $probeCode = @'
import json
import sys

import numpy
import onnxruntime

from pb_studio.core.directml_adapter import enumerate_dxgi_adapters, get_directml_adapter
from pb_studio.core.system_monitor import SystemMonitor

adapter = get_directml_adapter(refresh=True)
amd_hardware = [
    candidate
    for candidate in enumerate_dxgi_adapters()
    if candidate.vendor_id == 0x1002 and not candidate.is_software
]
monitor = SystemMonitor()
try:
    monitor_stats = monitor.get_stats(force_refresh=True)
    monitor_selected_luid = monitor.selected_adapter_luid
finally:
    monitor.close()
print(json.dumps({
    "python": ".".join(str(part) for part in sys.version_info[:3]),
    "numpy": numpy.__version__,
    "providers": onnxruntime.get_available_providers(),
    "adapter_index": adapter.device_id,
    "adapter_luid": adapter.luid,
    "adapter_name": adapter.name,
    "adapter_vendor_id": adapter.vendor_id,
    "adapter_discrete": adapter.is_discrete,
    "adapter_high_performance": adapter.high_performance_preferred,
    "adapter_vram_bytes": adapter.dedicated_vram_bytes,
    "max_amd_vram_bytes": max(item.dedicated_vram_bytes for item in amd_hardware),
    "provider_device_id": adapter.provider_tuple[1]["device_id"],
    "monitor_selected_luid": monitor_selected_luid,
    "monitor_adapter_luid": monitor_stats.get("adapter_luid"),
    "monitor_gpu_name": monitor_stats.get("gpu_name"),
    "monitoring_status": monitor_stats.get("monitoring_status"),
    "monitoring_error": monitor_stats.get("monitoring_error"),
}))
'@
    try {
        $probeEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probeCode))
        $probeOutput = & $py -c "import base64;exec(base64.b64decode('$probeEncoded'))" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw ($probeOutput -join [Environment]::NewLine)
        }
        $probe = ($probeOutput | Select-Object -Last 1) | ConvertFrom-Json
        if (-not ([string]$probe.python).StartsWith('3.11.')) { throw "Python must be 3.11.x; got $($probe.python)" }
        if ([string]$probe.numpy -ne '1.26.4') { throw "NumPy must be 1.26.4; got $($probe.numpy)" }
        if (@($probe.providers) -notcontains 'DmlExecutionProvider') { throw "DmlExecutionProvider unavailable: $(@($probe.providers) -join ',')" }
        if ([int]$probe.adapter_vendor_id -ne 0x1002 -or -not [bool]$probe.adapter_discrete -or
            -not [bool]$probe.adapter_high_performance -or
            [long]$probe.adapter_vram_bytes -ne [long]$probe.max_amd_vram_bytes -or
            [int]$probe.provider_device_id -ne [int]$probe.adapter_index) {
            throw "DirectML adapter invariant failed: index=$($probe.adapter_index), luid=$($probe.adapter_luid), name=$($probe.adapter_name)"
        }
        if ([string]$probe.monitor_selected_luid -ne [string]$probe.adapter_luid -or
            [string]$probe.monitor_adapter_luid -ne [string]$probe.adapter_luid) {
            throw "LHM/DirectML adapter LUID mismatch: directml=$($probe.adapter_luid), monitor=$($probe.monitor_selected_luid), stats=$($probe.monitor_adapter_luid)"
        }
        $monitoringStatus = [string]$probe.monitoring_status
        if ($monitoringStatus -eq 'ready') {
            if ([string]$probe.monitor_gpu_name -ne [string]$probe.adapter_name -or
                -not [string]::IsNullOrWhiteSpace([string]$probe.monitoring_error)) {
                throw "LHM ready status contains a foreign adapter identity or an error: gpu=$($probe.monitor_gpu_name), selected=$($probe.adapter_name)"
            }
            Log "LHM current adapter agreement: ready [$($probe.adapter_luid)]" 'Green'
        } elseif ($monitoringStatus -eq 'degraded' -and
            -not [string]::IsNullOrWhiteSpace([string]$probe.monitoring_error)) {
            Log "LHM current adapter agreement: degraded [$($probe.adapter_luid)] - $($probe.monitoring_error)" 'Yellow'
        } else {
            throw "LHM status is not truthful: status=$monitoringStatus, error=$($probe.monitoring_error)"
        }
        Log "Python $($probe.python) | NumPy $($probe.numpy) | DirectML adapter $($probe.adapter_name) [$($probe.adapter_index), $($probe.adapter_luid)]" 'Green'
    } catch {
        Log "Python/DirectML contract FAIL: $($_.Exception.Message)" 'Red'
        $ok = $false
    }

    try {
        $encoders = (& $ffmpeg -hide_banner -encoders 2>&1) -join [Environment]::NewLine
        foreach ($encoder in @('h264_amf', 'hevc_amf', 'av1_amf')) {
            if ($encoders -notmatch "(?m)^\s*[A-Z.]{6}\s+$encoder\s") {
                throw "Required AMF encoder missing: $encoder"
            }
        }
        Log "FFmpeg AMF contract OK: $ffmpeg" 'Green'
    } catch {
        Log "FFmpeg AMF contract FAIL: $($_.Exception.Message)" 'Red'
        $ok = $false
    }
    $listeners = Get-BackendPids
    if ($listeners) { Log "Backend already listening on $BackendPort (PIDs: $($listeners -join ','))" 'Yellow' }
    else { Log "Port $BackendPort free" 'Green' }
    if ($ok) { Log "check PASS" 'Green' } else { Log "check FAIL - missing prereqs" 'Red'; exit 1 }
}

function Invoke-StartBackend {
    $runtime = Initialize-DriverSession
    if (Test-Health) {
        $pids = Get-BackendPids
        Log "Backend already running (PIDs: $($pids -join ','))" 'Yellow'
        return
    }
    $py = Resolve-Python
    Log "Starting uvicorn on $BackendPort..."
    $stdout = Join-Path $LogsDir 'driver_backend.out.log'
    $stderr = Join-Path $LogsDir 'driver_backend.err.log'
    $p = Start-Process -FilePath $py `
        -ArgumentList @($runtime.BackendArguments) `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    Log "Backend PID: $($p.Id) | logs: $stdout"
    $deadline = (Get-Date).AddSeconds($BackendStartupDeadlineSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health) {
            Log "Backend healthy on $BaseUrl/health" 'Green'
            return
        }
        Start-Sleep -Milliseconds 500
    }
    Log "Backend startup timeout (${BackendStartupDeadlineSeconds}s) - check $stderr" 'Red'
    exit 2
}

function Invoke-StopBackend {
    [void](Initialize-DriverSession)
    if (-not (Test-Health) -and (Get-BackendPids).Count -eq 0) {
        Log "Backend already stopped" 'Yellow'
        return
    }
    Log "POST $BaseUrl/shutdown ..."
    try {
        Invoke-RestMethod -Uri "$BaseUrl/shutdown" -Method Post -TimeoutSec 5 `
            -Headers @{ $OwnerCapabilityHeader = $env:PBSTUDIO_OWNER_CAPABILITY } `
            -ErrorAction SilentlyContinue | Out-Null
    } catch {}
    $shutdownDeadline = (Get-Date).AddSeconds(330)
    while ((Get-Date) -lt $shutdownDeadline -and (Get-BackendPids).Count -gt 0) {
        Start-Sleep -Milliseconds 500
    }
    foreach ($p in Get-BackendPids) {
        Log "taskkill /T /F /PID $p"
        Start-Process taskkill -ArgumentList '/PID',$p,'/T','/F' -WindowStyle Hidden -Wait | Out-Null
    }
    Start-Sleep -Milliseconds 500
    if (Test-Health) { Log "Backend STILL alive" 'Red'; exit 3 } else { Log "Backend stopped" 'Green' }
}

function Invoke-Health {
    [void](Initialize-DriverSession)
    if (-not (Test-Health)) { Log "Backend not reachable" 'Red'; exit 4 }
    $h = Invoke-RestMethod -Uri "$BaseUrl/health"
    Log "health: $($h | ConvertTo-Json -Compress)" 'Green'
    $ownerHeaders = @{ $OwnerCapabilityHeader = $env:PBSTUDIO_OWNER_CAPABILITY }
    try { $g = Invoke-RestMethod -Uri "$BaseUrl/gpu/status" -Headers $ownerHeaders -TimeoutSec 5; Log "gpu: $($g | ConvertTo-Json -Compress -Depth 4)" 'Green' } catch { Log "gpu/status: $($_.Exception.Message)" 'Yellow' }
    try { $b = Invoke-RestMethod -Uri "$BaseUrl/brain/stats" -Headers $ownerHeaders -TimeoutSec 5; Log "brain.stats keys: $($b.PSObject.Properties.Name -join ',')" 'Green' } catch { Log "brain/stats: $($_.Exception.Message)" 'Yellow' }
}

function Invoke-Smoke {
    Invoke-StartBackend
    Invoke-Health
    Invoke-StopBackend
    Log "smoke PASS" 'Green'
}

function Invoke-StartFull {
    [void](Initialize-DriverSession)
    Invoke-StartBackend
    $exe = Resolve-FrontendExe
    $env:PBSTUDIO_BACKEND_MANAGED_EXTERNALLY = '1'
    $env:PBSTUDIO_BACKEND_DIR = Join-Path $ProjectRoot 'backend'
    Log "Launching frontend: $exe"
    $p = Start-Process -FilePath $exe -PassThru
    Log "Frontend PID: $($p.Id)" 'Green'
    return $p
}

function Invoke-Screenshot {
    param(
        [string]$Path,
        [int]$FocusPid = 0,
        [switch]$WindowOnly  # if set + FocusPid given: PrintWindow (ignores z-order)
    )
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    if (-not ('W.Native' -as [type])) {
        Add-Type -Namespace W -Name Native -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool SetForegroundWindow(System.IntPtr hWnd);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool PrintWindow(System.IntPtr hWnd, System.IntPtr hdcBlt, uint nFlags);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool GetWindowRect(System.IntPtr hWnd, out RECT lpRect);
[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct RECT { public int Left, Top, Right, Bottom; }
'@
    }
    if ($WindowOnly -and $FocusPid -gt 0) {
        $proc = Get-Process -Id $FocusPid -ErrorAction Stop
        $hwnd = $proc.MainWindowHandle
        if ($hwnd -eq [IntPtr]::Zero) { Log "No MainWindowHandle for PID $FocusPid" 'Red'; return }
        [W.Native]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE
        $r = New-Object W.Native+RECT
        [void][W.Native]::GetWindowRect($hwnd, [ref]$r)
        $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
        if ($w -le 0 -or $h -le 0) { Log "Window has zero size ($w x $h)" 'Red'; return }
        $bmp = New-Object System.Drawing.Bitmap $w, $h
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $hdc = $g.GetHdc()
        $ok = [W.Native]::PrintWindow($hwnd, $hdc, 0x2)  # PW_RENDERFULLCONTENT (works on WPF/composited)
        $g.ReleaseHdc($hdc)
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
        Log "Window screenshot (PrintWindow, ok=$ok): $Path (${w}x${h})" 'Green'
        return
    }
    if ($FocusPid -gt 0) {
        try {
            $proc = Get-Process -Id $FocusPid -ErrorAction Stop
            $hwnd = $proc.MainWindowHandle
            if ($hwnd -ne [IntPtr]::Zero) {
                [W.Native]::ShowWindow($hwnd, 9) | Out-Null
                [W.Native]::SetForegroundWindow($hwnd) | Out-Null
                Log "Focused HWND $hwnd (PID $FocusPid)" 'DarkGray'
                Start-Sleep -Milliseconds 800
            }
        } catch { Log "Focus failed: $($_.Exception.Message)" 'Yellow' }
    }
    $vb = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $vb.Width, $vb.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($vb.X, $vb.Y, 0, 0, $bmp.Size)
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Log "Screenshot: $Path ($($vb.Width)x$($vb.Height) virtual)" 'Green'
}

function Invoke-FullSmoke {
    $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
    if (-not $OutFile) { $OutFile = Join-Path $LogsDir "agent_$ts.png" }
    $fe = Invoke-StartFull
    Log "Wait $WaitSec s for UI render..."
    # Poll for MainWindowHandle so we don't screenshot before the window paints
    $deadline = (Get-Date).AddSeconds($WaitSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $fe.Refresh()
            if ($fe.HasExited) { Log "Frontend exited prematurely (code $($fe.ExitCode))" 'Red'; break }
            if ($fe.MainWindowHandle -ne [IntPtr]::Zero) {
                Log "MainWindow appeared after $([int]((Get-Date) - ($deadline.AddSeconds(-$WaitSec))).TotalSeconds)s" 'DarkGray'
                break
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    Start-Sleep -Seconds 2
    Invoke-Screenshot -Path $OutFile -FocusPid $fe.Id -WindowOnly
    if ($fe -and -not $fe.HasExited) {
        Log "Stopping frontend PID $($fe.Id) ..."
        Stop-Process -Id $fe.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
    Invoke-StopBackend
    Log "full-smoke PASS - screenshot: $OutFile" 'Green'
}

switch ($Command) {
    'check'         { Invoke-Check }
    'start-backend' { Invoke-StartBackend }
    'stop-backend'  { Invoke-StopBackend }
    'health'        { Invoke-Health }
    'smoke'         { Invoke-Smoke }
    'start-full'    { Invoke-StartFull | Out-Null }
    'screenshot'    {
        if (-not $OutFile) { $OutFile = Join-Path $LogsDir ("agent_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.png') }
        Invoke-Screenshot -Path $OutFile
    }
    'full-smoke'    { Invoke-FullSmoke }
}
