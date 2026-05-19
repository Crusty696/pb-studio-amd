@echo off
REM Phase 1 — Ollama Live-Status (Auto-Diagnose)
REM Output -> phase1_ollama_check.log
cd /d "%~dp0"

set "LOG=phase1_ollama_check.log"

(
  echo === PB Studio Phase 1 - Ollama Live-Status ===
  echo Timestamp: %date% %time%
  echo.
  echo --- 1. ollama version ---
  ollama --version 2^>^&1
  echo.
  echo --- 2. ollama list (installierte Modelle) ---
  ollama list 2^>^&1
  echo.
  echo --- 3. ollama ps (aktuell geladene Modelle in VRAM) ---
  ollama ps 2^>^&1
  echo.
  echo --- 4. HTTP Health curl localhost:11434/api/version ---
  curl -s --max-time 5 http://localhost:11434/api/version 2^>^&1
  echo.
  echo.
  echo --- 5. HTTP curl localhost:11434/api/tags ---
  curl -s --max-time 5 http://localhost:11434/api/tags 2^>^&1
  echo.
  echo.
  echo --- 6. where ollama (Pfad) ---
  where ollama 2^>^&1
  echo.
  echo --- 7. Ollama-Service-Status (tasklist) ---
  tasklist /FI "IMAGENAME eq ollama.exe" 2^>^&1
  tasklist /FI "IMAGENAME eq ollama app.exe" 2^>^&1
  echo.
  echo --- 8. Ollama Models-Folder Inhalt ---
  if exist "%USERPROFILE%\.ollama\models\manifests" (
    dir /S /B "%USERPROFILE%\.ollama\models\manifests" 2^>^&1
  ) else (
    echo Manifests-Ordner nicht gefunden
  )
  echo.
  echo --- 9. Python venv ollama-package check ---
  if exist ".venv\Lib\site-packages\ollama" (
    echo INSTALLED: .venv hat ollama-package
  ) else (
    echo NOT INSTALLED: kein ollama-Python-Paket im venv
  )
  echo.
  echo === ENDE ===
) > "%LOG%" 2>&1

echo Done. Output in %LOG%
type "%LOG%"
