# PB Studio - Full Autonomous Test Suite (Robust Version)
# Koordiniert pytest + UI-Test. Brain-Modul + P3.1 Coverage-Gap-Tests integriert (537 Tests Stand 2026-05-15).

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   PB STUDIO ROBUST TEST ORCHESTRATOR   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$python = ".\.venv\Scripts\python.exe"

# 0. Pytest-Suite (inkl. Brain-Modul + Storage + Recovery + Backup)
Write-Host "[0/3] Pytest-Suite ausführen..." -ForegroundColor Yellow
$env:PYTHONPATH = "src"
& $python -m pytest Tests/ -q --tb=short
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Pytest fehlgeschlagen - UI-Test übersprungen." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Pytest grün." -ForegroundColor Green
Write-Host ""

# 1. Start der GUI
Write-Host "[1/3] Starte PB Studio GUI via Launcher..." -ForegroundColor Yellow
$launcherProcess = Start-Process -FilePath $python -ArgumentList "run_ui.py" -PassThru -WindowStyle Hidden

# 2. Aktives Warten auf das Fenster
Write-Host "[2/3] Warte auf Erscheinen des WPF-Fensters (max 30s)..." -ForegroundColor Yellow
$timeout = 30
$elapsed = 0
$windowFound = $false

while ($elapsed -lt $timeout) {
    # Suche spezifisch nach dem Prozess unserer WPF-App
    $uiProc = Get-Process -Name "PBStudio.UI" -ErrorAction SilentlyContinue
    if ($uiProc -and $uiProc.MainWindowTitle -match "PB Studio") {
        Write-Host ""
        Write-Host "[OK] Korrektes App-Fenster erkannt: '$($uiProc.MainWindowTitle)' (PID: $($uiProc.Id))" -ForegroundColor Green
        $windowFound = $true
        break
    }
    Start-Sleep -Seconds 1
    $elapsed++
    Write-Host "." -NoNewline
}

if (-not $windowFound) {
    Write-Host ""
    Write-Host "[FAIL] Timeout: Das WPF-Fenster ist nicht erschienen." -ForegroundColor Red
    Write-Host "Bitte starte 'run_ui.py' manuell um zu sehen ob sie abstuerzt."
    exit 1
}

# Zusätzliche Pufferzeit für internes Rendering
Start-Sleep -Seconds 3

# 3. Start des ULTIMATE Test-Agenten (mit Video-Recording & Interaktion)
Write-Host "[3/3] Starte ULTIMATE Test Agenten..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
Write-Host "HINWEIS: Desktop wird jetzt aufgezeichnet!" -ForegroundColor Cyan
& $python "Tests\ultimate_ui_agent.py"
Write-Host "------------------------------------------------------------" -ForegroundColor Gray

Write-Host ""
Write-Host ">>> Test-Orchestrierung abgeschlossen. <<<" -ForegroundColor Green
Write-Host ""
