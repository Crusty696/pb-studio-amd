@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
call "%~dp0scripts\runtime_contract.bat"
if errorlevel 1 exit /b !ERRORLEVEL!

echo ====================================================
echo   PB Studio - DirectML Langzeit-Stresstest Launcher
echo ====================================================

if not exist .venv\Scripts\activate.bat (
    echo ERROR: Virtuelle Umgebung .venv nicht gefunden.
    echo Bitte setup.bat ausfuehren.
    exit /b 1
)

set CYCLES=20
if not "%~1"=="" (
    set CYCLES=%~1
)

echo INFO: Starte Stresstest mit %CYCLES% Zyklen...
"%PBSTUDIO_PYTHON_EXE%" scripts\long_stress_run.py %CYCLES%

if !ERRORLEVEL! EQU 0 (
    echo SUCCESS: Stresstest fehlerfrei beendet.
) else (
    echo ERROR: Stresstest mit Fehler beendet.
)

exit /b !ERRORLEVEL!
