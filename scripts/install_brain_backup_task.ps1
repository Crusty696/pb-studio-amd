# Plan Phase 6: install Windows Task Scheduler entry for weekly brain backup.
# Runs scripts\brain_backup_run.py every Sunday 03:30, with the project .venv python.
# Removes prior task with same name first.

$ErrorActionPreference = "Stop"

$RepoRoot = git rev-parse --show-toplevel
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$ScriptPath = Join-Path $RepoRoot "scripts\brain_backup_run.py"
$TaskName = "PBStudio_BrainBackup"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe"
    exit 1
}
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Backup script not found at $ScriptPath"
    exit 1
}

# Drop existing task if present (idempotent)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task $TaskName"
}

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $RepoRoot

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Sunday `
    -At "03:30"

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "PB Studio Brain Store wöchentliches VACUUM INTO Backup (Plan Phase 6)"

Write-Host "Scheduled task '$TaskName' installed."
Write-Host "Run manually with: Start-ScheduledTask -TaskName $TaskName"
