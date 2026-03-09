# run.ps1 - Schnell-Start Skript

Write-Host "Starting PBStudio.UI..." -ForegroundColor Cyan
Write-Host "Make sure Python backend is running on port 8765!" -ForegroundColor Yellow
Write-Host ""

dotnet run --configuration Debug

Write-Host ""
Write-Host "Application closed." -ForegroundColor Gray
