@echo off
setlocal enabledelayedexpansion

echo ====================================================
echo   PB Studio - DirectML Langzeit-Stresstest Launcher
echo ====================================================

if not exist .venv\Scripts\activate.bat (
    echo ERROR: Virtuelle Umgebung .venv nicht gefunden.
    echo Bitte setup.bat ausfuehren.
    exit /b 1
)

call .venv\Scripts\activate.bat

set PYTHONPATH=src

set CYCLES=20
if not "%~1"=="" (
    set CYCLES=%~1
)

echo INFO: Starte Stresstest mit %CYCLES% Zyklen...
.venv\Scripts\python.exe scripts\long_stress_run.py %CYCLES%

if !ERRORLEVEL! EQU 0 (
    echo SUCCESS: Stresstest fehlerfrei beendet.
) else (
    echo ERROR: Stresstest mit Fehler beendet.
)

exit /b !ERRORLEVEL!
