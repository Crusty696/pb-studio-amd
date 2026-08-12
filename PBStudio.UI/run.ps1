# run.ps1 - Schnell-Start Skript

$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
. (Join-Path $ProjectRoot 'scripts\runtime_contract.ps1')
$BackendEndpoint = Get-PBStudioBackendEndpoint -ProjectRoot $ProjectRoot

Write-Host "Starting PBStudio.UI..." -ForegroundColor Cyan
Write-Host "Make sure Python backend is running at $($BackendEndpoint.Origin)!" -ForegroundColor Yellow
Write-Host ""

dotnet run --configuration Debug

Write-Host ""
Write-Host "Application closed." -ForegroundColor Gray
