$ErrorActionPreference = 'Stop'

$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$pythonExe = Join-Path $repoDir '.venv\Scripts\python.exe'
$wpfExe = Join-Path $repoDir 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe'
$backendOut = Join-Path $PSScriptRoot 'backend-cycle-9.stdout.log'
$backendErr = Join-Path $PSScriptRoot 'backend-cycle-9.stderr.log'
$sourceProject = 'C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245'
$outputPath = Join-Path $sourceProject 'output\t337_project_switch_cancelled_cycle12.mp4'
$backend = $null
$wpf = $null

if (Get-Process -Name 'PBStudio.UI' -ErrorAction SilentlyContinue) {
    throw 'PBStudio.UI is already running; refusing to disturb an existing session.'
}
if (Test-Path -LiteralPath $outputPath) {
    throw "T337 output target already exists: $outputPath"
}

try {
    $env:PYTHONPATH = 'src;.'
    $env:T337_BACKEND_LOG = $backendOut
    $backend = Start-Process -FilePath $pythonExe `
        -ArgumentList @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8765') `
        -WorkingDirectory $repoDir `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -WindowStyle Hidden `
        -PassThru

    $healthy = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
            $healthy = $true
            break
        }
        catch {
            if ($backend.HasExited) {
                throw "Backend exited with code $($backend.ExitCode)."
            }
        }
    }
    if (-not $healthy) {
        throw 'Backend health timeout.'
    }

    $body = @{ path = $sourceProject } | ConvertTo-Json
    $null = Invoke-RestMethod `
        -Uri 'http://127.0.0.1:8765/project/open' `
        -Method Post `
        -ContentType 'application/json' `
        -Body $body `
        -TimeoutSec 30

    $wpf = Start-Process -FilePath $wpfExe `
        -WorkingDirectory (Split-Path -Parent $wpfExe) `
        -PassThru
    Start-Sleep -Seconds 5

    & $pythonExe (Join-Path $PSScriptRoot 'run_t337_project_switch.py')
    if ($LASTEXITCODE -ne 0) {
        throw "Project-switch QC exited with code $LASTEXITCODE."
    }
}
finally {
    if ($null -ne $wpf -and -not $wpf.HasExited) {
        $wpf.CloseMainWindow() | Out-Null
        if (-not $wpf.WaitForExit(10000)) {
            $wpf.Kill()
        }
    }
    if ($null -ne $backend -and -not $backend.HasExited) {
        $backend.Kill()
        $backend.WaitForExit()
    }
}
