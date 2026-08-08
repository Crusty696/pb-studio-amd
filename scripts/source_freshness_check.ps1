#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AssemblyPath,
    [Parameter(Mandatory = $true)]
    [string]$SourcePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$assembly = Get-Item -LiteralPath $AssemblyPath -ErrorAction SilentlyContinue
if (-not $assembly) {
    Write-Output 'BUILD'
    exit 0
}
$source = Get-ChildItem -LiteralPath $SourcePath -Recurse -File |
    Where-Object { $_.Extension -in @('.cs', '.xaml', '.csproj') } |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if ($source -and $source.LastWriteTimeUtc -gt $assembly.LastWriteTimeUtc) {
    Write-Output 'BUILD'
} else {
    Write-Output 'SKIP'
}
