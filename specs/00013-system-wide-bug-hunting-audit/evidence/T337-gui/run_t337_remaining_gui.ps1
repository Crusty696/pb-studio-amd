$ErrorActionPreference = 'Stop'

$probe = Join-Path $PSScriptRoot 'run_t337_win32_dialog_probe.ps1'
$projectSwitch = Join-Path $PSScriptRoot 'run_t337_project_switch.ps1'

[void][scriptblock]::Create([System.IO.File]::ReadAllText($probe))
[void][scriptblock]::Create([System.IO.File]::ReadAllText($projectSwitch))

& $probe
if ($LASTEXITCODE -ne 0) {
    throw "Win32 dialog probe failed with exit code $LASTEXITCODE."
}

& $projectSwitch
if ($LASTEXITCODE -ne 0) {
    throw "Project-switch QC failed with exit code $LASTEXITCODE."
}
