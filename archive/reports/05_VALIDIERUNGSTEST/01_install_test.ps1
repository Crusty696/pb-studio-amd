# ============================================
# PB Studio AMD - Installationstest
# Ausführen auf AMD-System mit RX 7800 XT
# ============================================

$ErrorActionPreference = "Stop"
$TestDir = "C:\Temp\pb_studio_amd_test"
$ReportFile = "$TestDir\INSTALL_REPORT.txt"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PB Studio AMD - Installationstest" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Timestamp
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "`nStart: $Timestamp"

# 1. Testverzeichnis erstellen
Write-Host "`n[1/7] Testverzeichnis erstellen..." -ForegroundColor Yellow
if (Test-Path $TestDir) {
    Remove-Item -Recurse -Force $TestDir
}
New-Item -ItemType Directory -Path $TestDir | Out-Null

# Report initialisieren
@"
# PB Studio AMD - Installationstest Report
# Erstellt: $Timestamp
# ========================================

"@ | Out-File $ReportFile

# 2. Python-Version prüfen
Write-Host "`n[2/7] Python-Version prüfen..." -ForegroundColor Yellow
$PythonVersion = python --version 2>&1
Write-Host "  Gefunden: $PythonVersion"

if ($PythonVersion -notmatch "Python 3\.11") {
    Write-Host "  FEHLER: Python 3.11.x erforderlich!" -ForegroundColor Red
    "FEHLER: Falsche Python-Version: $PythonVersion" | Out-File $ReportFile -Append
    "Erforderlich: Python 3.11.x" | Out-File $ReportFile -Append
    exit 1
}
"Python-Version: $PythonVersion [OK]" | Out-File $ReportFile -Append

# 3. Virtual Environment erstellen
Write-Host "`n[3/7] Virtual Environment erstellen..." -ForegroundColor Yellow
python -m venv "$TestDir\.venv"
& "$TestDir\.venv\Scripts\Activate.ps1"
"Virtual Environment: Erstellt [OK]" | Out-File $ReportFile -Append

# 4. Pip aktualisieren
Write-Host "`n[4/7] Pip aktualisieren..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel --quiet
$PipVersion = pip --version
"Pip-Version: $PipVersion [OK]" | Out-File $ReportFile -Append

# 5. Pakete installieren
Write-Host "`n[5/7] Pakete installieren..." -ForegroundColor Yellow
Write-Host "  Dies kann 5-10 Minuten dauern..." -ForegroundColor Gray

# Basis zuerst
Write-Host "  - numpy..." -ForegroundColor Gray
pip install numpy==1.26.4 --quiet 2>&1 | Out-Null

# AMD DirectML Runtime
Write-Host "  - onnxruntime-genai-directml..." -ForegroundColor Gray
pip install onnxruntime-genai-directml==0.11.4 --quiet 2>&1 | Out-Null

# Audio
Write-Host "  - librosa, soundfile..." -ForegroundColor Gray
pip install librosa==0.11.0 soundfile --quiet 2>&1 | Out-Null

# Video
Write-Host "  - opencv-python..." -ForegroundColor Gray
pip install opencv-python==4.12.0.88 --quiet 2>&1 | Out-Null

Write-Host "  - scenedetect..." -ForegroundColor Gray
pip install scenedetect==0.6.7.1 --quiet 2>&1 | Out-Null

Write-Host "  - transformers, pillow..." -ForegroundColor Gray
pip install transformers pillow huggingface-hub --quiet 2>&1 | Out-Null

# Datenbank
Write-Host "  - chromadb..." -ForegroundColor Gray
pip install chromadb==1.4.0 --quiet 2>&1 | Out-Null

# FFmpeg
Write-Host "  - ffmpeg-python..." -ForegroundColor Gray
pip install ffmpeg-python --quiet 2>&1 | Out-Null

# Utilities
Write-Host "  - tqdm, click, pydantic..." -ForegroundColor Gray
pip install tqdm click pydantic --quiet 2>&1 | Out-Null

"Pakete installiert [OK]" | Out-File $ReportFile -Append

# 6. Pip check
Write-Host "`n[6/7] Abhängigkeitskonflikte prüfen (pip check)..." -ForegroundColor Yellow
$PipCheck = pip check 2>&1
Write-Host $PipCheck

"`n## Pip Check Ergebnis:" | Out-File $ReportFile -Append
$PipCheck | Out-File $ReportFile -Append

# 7. Pip freeze
Write-Host "`n[7/7] Installierte Pakete dokumentieren..." -ForegroundColor Yellow
$PipFreeze = pip freeze
$PipFreeze | Out-File "$TestDir\pip_freeze.txt"

"`n## Alle installierten Pakete (pip freeze):" | Out-File $ReportFile -Append
"Siehe: pip_freeze.txt" | Out-File $ReportFile -Append

# Zusammenfassung
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Installation abgeschlossen!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nNächster Schritt: 02_import_test.py ausführen"
Write-Host "Report: $ReportFile"

"`n## Status: Installation abgeschlossen" | Out-File $ReportFile -Append
"Nächster Schritt: 02_import_test.py ausführen" | Out-File $ReportFile -Append
