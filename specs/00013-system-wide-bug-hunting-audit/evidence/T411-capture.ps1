param(
    [Parameter(Mandatory = $true)]
    [string]$RunRoot,
    [Parameter(Mandatory = $true)]
    [string]$Checkout,
    [Parameter(Mandatory = $true)]
    [string]$PythonExe,
    [Parameter(Mandatory = $true)]
    [ValidateSet("raft", "siglip", "moondream", "clap", "audio")]
    [string]$Workload,
    [double]$Seconds = 18.0
)

$ErrorActionPreference = "Stop"
$Checkout = [IO.Path]::GetFullPath($Checkout)
$RunRoot = [IO.Path]::GetFullPath($RunRoot)
$captureRoot = Join-Path $RunRoot (
    "captures\{0}-{1}" -f $Workload, [guid]::NewGuid().ToString("N")
)
[IO.Directory]::CreateDirectory($captureRoot) | Out-Null

$env:PYTHONPATH = Join-Path $Checkout "src"
$env:PBSTUDIO_T411_PROJECT_DIR = Join-Path $RunRoot "fixture"
$env:PBSTUDIO_T411_PROJECT_DB = Join-Path $RunRoot "fixture\project.db"

$probe = Join-Path $Checkout (
    "specs\00013-system-wide-bug-hunting-audit\evidence\T411-hardware-probe.py"
)
$stdout = Join-Path $captureRoot "stdout.log"
$stderr = Join-Path $captureRoot "stderr.log"
$process = Start-Process $PythonExe `
    -ArgumentList @($probe, $Workload, "--seconds", [string]$Seconds) `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr

$deadline = (Get-Date).AddSeconds(240)
do {
    Start-Sleep -Milliseconds 250
    $process.Refresh()
    $ready = (Test-Path $stdout) -and (
        (Get-Content $stdout -Raw) -match "T411_READY="
    )
} while (-not $ready -and -not $process.HasExited -and (Get-Date) -lt $deadline)

if (-not $ready) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    throw "$Workload did not become ready: $(Get-Content $stderr -Raw)"
}
$readyLine = Get-Content $stdout |
    Where-Object { $_ -like "T411_READY=*" } |
    Select-Object -Last 1
$readyPayload = $readyLine.Substring(11) | ConvertFrom-Json
$inferencePid = [int]$readyPayload.pid

$allSamples = @()
$samplingErrors = @()
$samplingDeadline = (Get-Date).AddSeconds([Math]::Max(3, $Seconds - 2))
while ((Get-Date) -lt $samplingDeadline -and -not $process.HasExited) {
    try {
        $counter = Get-Counter "\GPU Engine(*)\Utilization Percentage"
        $allSamples += @(
            $counter.CounterSamples |
                Select-Object Timestamp, InstanceName, CookedValue
        )
    } catch {
        $samplingErrors += $_.Exception.Message
    }
    Start-Sleep -Milliseconds 100
    $process.Refresh()
}
$pidSamples = @(
    $allSamples |
        Where-Object { $_.InstanceName -match "pid_$($inferencePid)_" }
)

ConvertTo-Json -InputObject $allSamples -Depth 4 |
    Set-Content (Join-Path $captureRoot "gpu-all.json") -Encoding utf8
ConvertTo-Json -InputObject $pidSamples -Depth 4 |
    Set-Content (Join-Path $captureRoot "gpu-pid.json") -Encoding utf8

if (-not $process.HasExited) {
    Wait-Process -Id $process.Id -Timeout 240
}
$resultLine = Get-Content $stdout |
    Where-Object { $_ -like "T411_RESULT=*" } |
    Select-Object -Last 1
if (-not $resultLine) {
    throw "$Workload produced no result: $(Get-Content $stderr -Raw)"
}
$result = $resultLine.Substring(12) | ConvertFrom-Json
$rxSamples = @(
    $pidSamples |
        Where-Object {
            $_.InstanceName -match "luid_0x00000000_0x00012a2a"
        }
)
$otherSamples = @(
    $pidSamples |
        Where-Object {
            $_.InstanceName -match "luid_" -and
            $_.InstanceName -notmatch "luid_0x00000000_0x00012a2a"
        }
)
$summary = [ordered]@{
    workload = $Workload
    capture_root = $captureRoot
    launcher_pid = $process.Id
    pid = $inferencePid
    result_pid = $result.pid
    ready = $result.ready
    iterations = $result.iterations
    adapter = $result.adapter
    provider = $result.provider
    session_contracts = $result.session_contracts
    all_engine_samples = $allSamples.Count
    pid_engine_samples = $pidSamples.Count
    sampling_errors = $samplingErrors
    rx_engine_max = ($rxSamples | Measure-Object CookedValue -Maximum).Maximum
    other_engine_max = ($otherSamples | Measure-Object CookedValue -Maximum).Maximum
}
$summary | ConvertTo-Json -Depth 8 |
    Set-Content (Join-Path $captureRoot "summary.json") -Encoding utf8
$summary | ConvertTo-Json -Depth 8
