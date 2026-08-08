#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('build', 'launch', 'test')]
    [string]$Operation,
    [Parameter(Mandatory = $true)]
    [string]$LogFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$logsRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'logs'))
$resolvedLog = [IO.Path]::GetFullPath($LogFile)
$logsPrefix = $logsRoot.TrimEnd('\') + '\'
if (-not $resolvedLog.StartsWith(
        $logsPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
    throw 'LogFile muss unterhalb des PB-Studio-Logverzeichnisses liegen'
}

$scriptName = switch ($Operation) {
    'build' { 'build.ps1' }
    'launch' { 'launch.ps1' }
    'test' { 'run_full_test.ps1' }
}
$scriptPath = [IO.Path]::GetFullPath((Join-Path $repoRoot $scriptName))
$arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $scriptPath
)
if ($Operation -eq 'build') {
    $arguments += @('-Configuration', 'Release')
}

& powershell.exe @arguments *>&1 |
    ForEach-Object {
        $line = [string]$_
        Write-Host $line
        Add-Content -LiteralPath $resolvedLog -Value $line -Encoding utf8
    }
exit $LASTEXITCODE
