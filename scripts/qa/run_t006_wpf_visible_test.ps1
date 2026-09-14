#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $ProjectRoot

# 1. Check port 8765 is free
$connections = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($connections) {
    Write-Error "Port 8765 has active listener before test!"
}

# Enable WPF software rendering for PrintWindow compatibility during automated GUI capture
New-Item -Path 'HKCU:\Software\Microsoft\Avalon.Graphics' -Force | Out-Null
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Avalon.Graphics' -Name 'DisableHWAcceleration' -Value 1 -Type DWord

# 2. Runtime contract & owner capability
. (Join-Path $ProjectRoot 'scripts\runtime_contract.ps1')
$Runtime = Get-PBStudioRuntimeContract -ProjectRoot $ProjectRoot -RequirePython -RequireFFmpeg -ApplyEnvironment

$bytes = New-Object byte[] 32
$generator = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
$ownerCap = [Convert]::ToBase64String($bytes)
$env:PBSTUDIO_OWNER_CAPABILITY = $ownerCap
$env:PBSTUDIO_BACKEND_MANAGED_EXTERNALLY = "1"
$env:PBSTUDIO_BACKEND_DIR = Join-Path $ProjectRoot 'backend'

# 3. Start backend
$backendOut = Join-Path $ProjectRoot 'logs\t006_backend.out.log'
$backendErr = Join-Path $ProjectRoot 'logs\t006_backend.err.log'
if (-not (Test-Path (Join-Path $ProjectRoot 'logs'))) { New-Item -ItemType Directory -Path (Join-Path $ProjectRoot 'logs') -Force | Out-Null }

Write-Host "Starting backend..." -ForegroundColor Cyan
$backendProc = Start-Process -FilePath $Runtime.PythonExe `
    -ArgumentList $Runtime.BackendArguments `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Minimized `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -PassThru

# 4. Wait for backend health
$healthy = $false
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($res.status -eq 'ok') { $healthy = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}

if (-not $healthy) {
    Write-Host "Backend failed to become healthy!" -ForegroundColor Red
    try { Stop-Process -Id $backendProc.Id -Force } catch {}
    exit 1
}
Write-Host "Backend healthy on 127.0.0.1:8765" -ForegroundColor Green

$openBody = '{"path":"C:\\Users\\david\\Documents\\PBStudio\\test_august"}'
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8765/project/open" -Method Post -Body $openBody -ContentType "application/json" -TimeoutSec 10 | Out-Null
    Write-Host "Loaded project test_august into backend" -ForegroundColor Green
} catch {
    Write-Host "Note: Project open returned: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 5. Start WPF Frontend
$frontendExe = Join-Path $ProjectRoot 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe'
if (-not (Test-Path $frontendExe)) {
    Write-Error "PBStudio.UI.exe not found at $frontendExe. Run dotnet build first!"
}

Write-Host "Starting WPF Frontend in foreground..." -ForegroundColor Cyan
$frontendProc = Start-Process -FilePath $frontendExe -WorkingDirectory $ProjectRoot -PassThru

# 6. Wait for WPF window
$winDeadline = (Get-Date).AddSeconds(30)
$foundWindow = $false
if (-not ([System.Management.Automation.PSTypeName]'Win32HelperV2').Type) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32HelperV2 {
    [DllImport("user32.dll", EntryPoint="FindWindowW", CharSet=CharSet.Unicode)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
}

$hwnd = [IntPtr]::Zero
while ((Get-Date) -lt $winDeadline) {
    $hwnd = [Win32HelperV2]::FindWindow($null, "PB Studio AMD")
    if ($hwnd -ne [IntPtr]::Zero) {
        $foundWindow = $true
        break
    }
    # Fallback to process MainWindowHandle
    $frontendProc.Refresh()
    if ($frontendProc.MainWindowHandle -ne [IntPtr]::Zero) {
        $hwnd = $frontendProc.MainWindowHandle
        $foundWindow = $true
        break
    }
    Start-Sleep -Milliseconds 500
}

if (-not $foundWindow) {
    Write-Host "WPF Window 'PB Studio AMD' not found!" -ForegroundColor Red
    try { Stop-Process -Id $frontendProc.Id -Force } catch {}
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8765/shutdown" -Method Post -Headers @{ 'X-PBStudio-Owner-Capability' = $ownerCap } -TimeoutSec 5 | Out-Null
    } catch {}
    exit 1
}

Write-Host "WPF Window found: HWND $hwnd" -ForegroundColor Green
[Win32HelperV2]::ShowWindow($hwnd, 9) # SW_RESTORE
[Win32HelperV2]::SetForegroundWindow($hwnd)
Start-Sleep -Seconds 3

$r1Exit = 1
$r2Exit = 1
try {
    # 7. Run GUI tests: Round 1 & Round 2
    Write-Host "Running GUI screenshot test Round 1..." -ForegroundColor Cyan
    $env:PBSTUDIO_GUI_RUN = "00023_t006_round1"
    & $Runtime.PythonExe Tests\gui_screenshot_v4.py
    $r1Exit = $LASTEXITCODE

    Write-Host "Running GUI screenshot test Round 2 (re-visit tabs)..." -ForegroundColor Cyan
    $env:PBSTUDIO_GUI_RUN = "00023_t006_round2"
    & $Runtime.PythonExe Tests\gui_screenshot_v4.py
    $r2Exit = $LASTEXITCODE
} finally {
    # 8. Clean graceful shutdown
    Write-Host "Closing WPF frontend gracefully..." -ForegroundColor Cyan
    try {
        $frontendProc.CloseMainWindow() | Out-Null
        $frontendProc.WaitForExit(10000)
    } catch {}
    if (-not $frontendProc.HasExited) {
        try { Stop-Process -Id $frontendProc.Id -Force } catch {}
    }

    Write-Host "Shutting down backend gracefully..." -ForegroundColor Cyan
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8765/shutdown" -Method Post -Headers @{ 'X-PBStudio-Owner-Capability' = $ownerCap } -TimeoutSec 10 | Out-Null
    } catch {}
    $backendProc.WaitForExit(15000)
    if (-not $backendProc.HasExited) {
        try { Stop-Process -Id $backendProc.Id -Force } catch {}
    }

    Write-Host "Verifying port 8765 is closed..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    $finalConn = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
    if ($finalConn) {
        Write-Host "WARNING: Port 8765 still listening" -ForegroundColor Yellow
    } else {
        Write-Host "Port 8765 cleanly released" -ForegroundColor Green
    }

    # Restore WPF hardware acceleration
    Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Avalon.Graphics' -Name 'DisableHWAcceleration' -ErrorAction SilentlyContinue
}

Write-Host "T006 GUI Run Complete. Round 1 exit: $r1Exit, Round 2 exit: $r2Exit" -ForegroundColor $(if ($r1Exit -eq 0 -and $r2Exit -eq 0) { 'Green' } else { 'Red' })
if ($r1Exit -ne 0 -or $r2Exit -ne 0) { exit 1 } else { exit 0 }
