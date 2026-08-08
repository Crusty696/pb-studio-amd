#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [switch]$RequirePython,
    [switch]$RequireFFmpeg
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    . (Join-Path $PSScriptRoot 'runtime_contract.ps1')
    Get-PBStudioRuntimeContract @PSBoundParameters | Out-Null
    exit 0
} catch {
    Write-Error "PB Studio runtime contract failed: $($_.Exception.Message)"
    exit 1
}
