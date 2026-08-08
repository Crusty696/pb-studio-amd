#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Start', 'Stop')]
    [string]$Operation,
    [Parameter(Mandatory = $true)]
    [ValidateSet('Backend', 'Ui', 'Stress')]
    [string]$Kind,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$StateName,
    [ValidateSet('Normal', 'Minimized', 'Hidden')]
    [string]$WindowStyle = 'Hidden',
    [ValidateSet('Graceful', 'Crash')]
    [string]$StopMode = 'Graceful',
    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$LogName = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$logsRoot = Join-Path $repoRoot 'logs'
New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null
$statePath = Join-Path $logsRoot ($StateName + '.process.json')

function Get-ExpectedExecutable {
    param([Parameter(Mandatory = $true)][string]$ProcessKind)

    if ($ProcessKind -eq 'Ui') {
        return [IO.Path]::GetFullPath(
            (Join-Path $repoRoot 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe')
        )
    }

    . (Join-Path $PSScriptRoot 'runtime_contract.ps1')
    $runtime = Get-PBStudioRuntimeContract `
        -ProjectRoot $repoRoot `
        -RequirePython `
        -RequireFFmpeg `
        -ApplyEnvironment
    return [IO.Path]::GetFullPath($runtime.PythonExe)
}

function Test-OwnerCapability {
    $value = [string]$env:PBSTUDIO_OWNER_CAPABILITY
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $false
    }
    try {
        return ([Convert]::FromBase64String($value)).Length -eq 32
    } catch {
        return $false
    }
}

function Get-TrackedProcess {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        throw "Owned process state missing: $statePath"
    }
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    if ([string]$state.kind -ne $Kind) {
        throw "Owned process kind mismatch for $StateName"
    }
    $process = Get-Process -Id ([int]$state.pid) -ErrorAction Stop
    $expectedExecutable = Get-ExpectedExecutable -ProcessKind $Kind
    if ([IO.Path]::GetFullPath($process.Path) -ne $expectedExecutable) {
        throw "Owned process executable mismatch for PID $($state.pid)"
    }
    if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$state.start_time_utc_ticks) {
        throw "Owned process identity mismatch for PID $($state.pid)"
    }
    return $process
}

if ($Operation -eq 'Start') {
    if ($Kind -in @('Backend', 'Ui') -and -not (Test-OwnerCapability)) {
        throw 'PBSTUDIO_OWNER_CAPABILITY must be a base64-encoded 32-byte value'
    }
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $existing = Get-TrackedProcess
            throw "Owned process already running: PID $($existing.Id)"
        } catch [Microsoft.PowerShell.Commands.ProcessCommandException] {
            Remove-Item -LiteralPath $statePath -Force
        }
    }

    $expectedExecutable = Get-ExpectedExecutable -ProcessKind $Kind
    if (-not (Test-Path -LiteralPath $expectedExecutable -PathType Leaf)) {
        throw "Owned process executable missing: $expectedExecutable"
    }

    if ($Kind -eq 'Backend') {
        . (Join-Path $PSScriptRoot 'runtime_contract.ps1')
        $runtime = Get-PBStudioRuntimeContract `
            -ProjectRoot $repoRoot `
            -RequirePython `
            -RequireFFmpeg `
            -ApplyEnvironment
        $arguments = @($runtime.BackendArguments)
    } elseif ($Kind -eq 'Stress') {
        $stressScript = Join-Path $repoRoot 'src\tools\execute_4h_stress_test.py'
        if (-not (Test-Path -LiteralPath $stressScript -PathType Leaf)) {
            throw "Stress script missing: $stressScript"
        }
        $arguments = @($stressScript)
    } else {
        $arguments = @()
    }

    $startArguments = @{
        FilePath = $expectedExecutable
        WorkingDirectory = $repoRoot
        WindowStyle = $WindowStyle
        PassThru = $true
    }
    if ($arguments.Count -gt 0) {
        $startArguments.ArgumentList = $arguments
    }
    if (-not [string]::IsNullOrWhiteSpace($LogName)) {
        $startArguments.RedirectStandardOutput = Join-Path $logsRoot ($LogName + '.stdout.log')
        $startArguments.RedirectStandardError = Join-Path $logsRoot ($LogName + '.stderr.log')
    }
    if ($Kind -eq 'Stress') {
        Remove-Item Env:PBSTUDIO_OWNER_CAPABILITY -ErrorAction SilentlyContinue
    }
    $process = Start-Process @startArguments
    $process.Refresh()
    [ordered]@{
        schema_version = 1
        kind = $Kind
        pid = $process.Id
        executable = $expectedExecutable
        start_time_utc_ticks = $process.StartTime.ToUniversalTime().Ticks
    } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
    Write-Output $process.Id
    exit 0
}

try {
    $ownedProcess = Get-TrackedProcess
} catch [Microsoft.PowerShell.Commands.ProcessCommandException] {
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    exit 0
}
if ($Kind -eq 'Backend' -and $StopMode -eq 'Graceful') {
    if (-not (Test-OwnerCapability)) {
        throw 'PBSTUDIO_OWNER_CAPABILITY is required for graceful backend shutdown'
    }
    try {
        Invoke-RestMethod `
            -Uri 'http://127.0.0.1:8765/shutdown' `
            -Method Post `
            -Headers @{
                'X-PBStudio-Owner-Capability' = $env:PBSTUDIO_OWNER_CAPABILITY
            } `
            -TimeoutSec 5 | Out-Null
        $ownedProcess.WaitForExit(10000) | Out-Null
    } catch {
        Write-Warning "Graceful shutdown failed: $($_.Exception.Message)"
    }
}

$ownedProcess.Refresh()
if (-not $ownedProcess.HasExited) {
    & taskkill.exe /PID $ownedProcess.Id /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop owned $Kind process PID $($ownedProcess.Id)"
    }
}
Remove-Item -LiteralPath $statePath -Force
