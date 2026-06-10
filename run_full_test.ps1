# PB Studio - Full Autonomous Test Suite (Robust Version)
# Koordiniert pytest + UI-Test. Brain-Modul + P3.1 Coverage-Gap-Tests integriert.

param(
    [switch]$NoGui
)

# Robustes Parsen für --no-gui alias
if ($args -contains "--no-gui" -or $args -contains "-no-gui" -or $args -contains "-NoGui") {
    $NoGui = $true
}

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
$pytestExitCode = $LASTEXITCODE

if ($pytestExitCode -ne 0) {
    Write-Host "[FAIL] Pytest-Suite fehlgeschlagen." -ForegroundColor Red
    exit $pytestExitCode
}
Write-Host "[OK] Pytest grün." -ForegroundColor Green
Write-Host ""

if ($NoGui) {
    Write-Host "UI-Tests uebersprungen (--no-gui gesetzt)." -ForegroundColor Cyan
    Write-Host ">>> Test-Orchestrierung erfolgreich abgeschlossen (nur Backend). <<<" -ForegroundColor Green
    exit 0
}

# 1. Start der GUI
Write-Host "[1/3] Starte PB Studio GUI via Launcher..." -ForegroundColor Yellow
$launcherProcess = Start-Process -FilePath $python -ArgumentList "run_ui.py" -PassThru -WindowStyle Hidden

$uiAgentExitCode = 0
try {
    # 2. Aktives Warten auf das Fenster
    Write-Host "[2/3] Warte auf Erscheinen des WPF-Fensters (max 30s)..." -ForegroundColor Yellow
    $timeout = 30
    $elapsed = 0
    $windowFound = $false

    while ($elapsed -lt $timeout) {
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
        $uiAgentExitCode = 1
    } else {
        # Zusätzliche Pufferzeit für internes Rendering
        Start-Sleep -Seconds 3

        # 3. Start des ULTIMATE Test-Agenten (mit Video-Recording & Interaktion)
        Write-Host "[3/3] Starte ULTIMATE Test Agenten..." -ForegroundColor Yellow
        Write-Host "------------------------------------------------------------" -ForegroundColor Gray
        Write-Host "HINWEIS: Desktop wird jetzt aufgezeichnet!" -ForegroundColor Cyan
        & $python "Tests\ultimate_ui_agent.py"
        $uiAgentExitCode = $LASTEXITCODE
        Write-Host "------------------------------------------------------------" -ForegroundColor Gray
    }
}
finally {
    # Aufräumen: GUI-Prozess immer beenden
    if ($launcherProcess) {
        Write-Host "Beende GUI-Prozess (PID: $($launcherProcess.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $launcherProcess.Id -Force -ErrorAction SilentlyContinue
    }
    # WPF-Prozess falls separat gestartet
    $uiProc = Get-Process -Name "PBStudio.UI" -ErrorAction SilentlyContinue
    if ($uiProc) {
        Stop-Process -Name "PBStudio.UI" -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
if ($uiAgentExitCode -eq 0) {
    Write-Host ">>> Test-Orchestrierung erfolgreich abgeschlossen. <<<" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[FAIL] UI Test-Agent oder GUI-Start fehlgeschlagen (Exit-Code $uiAgentExitCode)." -ForegroundColor Red
    exit $uiAgentExitCode
}
