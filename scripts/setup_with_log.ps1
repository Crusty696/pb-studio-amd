#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SetupScript,
    [Parameter(Mandatory = $true)]
    [string]$LogFile,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SetupArguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$expectedSetup = [IO.Path]::GetFullPath(
    (Join-Path $repoRoot 'setup_pb_studio.ps1')
)
$resolvedSetup = [IO.Path]::GetFullPath($SetupScript)
$logsRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'logs'))
$resolvedLog = [IO.Path]::GetFullPath($LogFile)
$logsPrefix = $logsRoot.TrimEnd('\') + '\'

if ($resolvedSetup -ne $expectedSetup) {
    throw 'SetupScript muss das PB-Studio-Setup im Repository sein'
}
if (-not $resolvedLog.StartsWith(
        $logsPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
    throw 'LogFile muss unterhalb des PB-Studio-Logverzeichnisses liegen'
}

$allowedArguments = @(
    '-SkipBuildTools',
    '-SkipBackupPrompt',
    '-SkipModelPrecache',
    '-SkipGpuVerify',
    '-SkipPytest',
    '-NoPause',
    '-Force'
)
foreach ($argument in $SetupArguments) {
    if ($argument -notin $allowedArguments) {
        throw "Nicht unterstuetztes Setup-Argument: $argument"
    }
}

$powershellArguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $resolvedSetup
) + $SetupArguments

& powershell.exe @powershellArguments *>&1 |
    ForEach-Object {
        $line = [string]$_
        Write-Host $line
        Add-Content -LiteralPath $resolvedLog -Value $line -Encoding utf8
    }
exit $LASTEXITCODE
