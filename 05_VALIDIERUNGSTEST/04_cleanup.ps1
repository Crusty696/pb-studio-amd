# ============================================
# PB Studio AMD - Cleanup
# Löscht Test-Umgebung
# ============================================

$TestDir = "C:\Temp\pb_studio_amd_test"

Write-Host "PB Studio AMD - Cleanup" -ForegroundColor Yellow
Write-Host "========================"

if (Test-Path $TestDir) {
    Write-Host "`nLösche: $TestDir"
    
    # Deaktiviere venv falls aktiv
    if ($env:VIRTUAL_ENV) {
        deactivate 2>$null
    }
    
    Remove-Item -Recurse -Force $TestDir
    Write-Host "✅ Gelöscht" -ForegroundColor Green
} else {
    Write-Host "Verzeichnis existiert nicht: $TestDir" -ForegroundColor Gray
}

Write-Host "`nFertig."
