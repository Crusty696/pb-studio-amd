# Start Ralph fuer PB Studio AMD (PowerShell Version)
# Nutzt Claude Abo, kein API Key

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ralph fuer PB Studio AMD starten" -ForegroundColor Cyan
Write-Host "  (nutzt Claude Abo, kein API Key)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# API Key leeren
$env:ANTHROPIC_API_KEY = ""

# MSYS2 DLL-Workaround Variablen setzen
$env:MSYS = "winsymlinks:nativestrict"
$env:MSYS2_ARG_CONV_EXCL = "*"
$env:HOME = $env:USERPROFILE

# Git Bash pruefen
$gitBash = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path $gitBash)) {
    Write-Host "FEHLER: Git Bash nicht gefunden: $gitBash" -ForegroundColor Red
    Write-Host "Bitte Git for Windows installieren." -ForegroundColor Yellow
    Read-Host "Enter druecken zum Beenden"
    exit 1
}

# Ins Projektverzeichnis wechseln
$projectDir = "C:\Users\david\Dokumente\Pb_studio_AMD_version"
Set-Location $projectDir

Write-Host "Starte Ralph im Verzeichnis: $projectDir" -ForegroundColor Green
Write-Host ""

# Ralph via Git Bash starten
# --login initialisiert die Shell komplett (reduziert DLL-Probleme)
# Semikolons statt && fuer bessere Fehlerbehandlung
& $gitBash --login -c "unset ANTHROPIC_API_KEY; export MSYS=winsymlinks:nativestrict; export MSYS2_ARG_CONV_EXCL='*'; ralph --reset-session && ralph --live --verbose"

Write-Host ""
Write-Host "Ralph beendet." -ForegroundColor Yellow
Read-Host "Enter druecken zum Beenden"
