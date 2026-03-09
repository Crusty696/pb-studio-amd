# build.ps1 - Windows PowerShell Build-Skript für PBStudio.UI

param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug",
    
    [switch]$Run,
    [switch]$Clean
)

$ProjectName = "PBStudio.UI"
$ProjectPath = Get-Location

Write-Host "=================================================="
Write-Host "PBStudio.UI - Build-Skript"
Write-Host "=================================================="
Write-Host "Configuration: $Configuration"
Write-Host "Projekt-Pfad: $ProjectPath"
Write-Host ""

# Clean
if ($Clean) {
    Write-Host "Cleaning..." -ForegroundColor Cyan
    dotnet clean -c $Configuration
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# Restore
Write-Host "Restoring NuGet packages..." -ForegroundColor Cyan
dotnet restore
if ($LASTEXITCODE -ne 0) { 
    Write-Host "NuGet restore failed!" -ForegroundColor Red
    exit 1 
}

# Build
Write-Host "Building project..." -ForegroundColor Cyan
dotnet build -c $Configuration --no-restore
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1 
}

Write-Host "Build successful!" -ForegroundColor Green

# Run
if ($Run) {
    Write-Host "Starting application..." -ForegroundColor Cyan
    dotnet run -c $Configuration --no-build
}

Write-Host "Done!" -ForegroundColor Green
