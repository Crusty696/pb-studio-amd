@echo off
REM PB Studio AMD - Run Full Tests (Doppelklick-faehig)
REM Loggt komplette Konsolen-Ausgabe nach logs\test_<ts>.log.
setlocal enabledelayedexpansion

cd /d "%~dp0"
call "%~dp0scripts\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
REM logs-Verzeichnis MUSS vor dem Tee-Object-Pipe existieren
if not exist "logs" mkdir logs

REM Timestamp via PowerShell (wmic deprecated auf Win11 24H2+)
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
if "!TS!"=="" set TS=run

set LOGFILE=logs\test_!TS!.log

echo.
echo ============================================================
echo   PB Studio AMD - Test Suite
echo ============================================================
echo Log-Datei: %~dp0%LOGFILE%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ABORT: .venv fehlt. Bitte erst setup.bat ausfuehren.
    echo ABORT: .venv fehlt > "!LOGFILE!"
    echo Log: %~dp0!LOGFILE!
    pause
    exit /b 1
)

set "_LF=%~dp0%LOGFILE%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\invoke_project_script_with_log.ps1" -Operation test -LogFile "!_LF!"
set RC=!ERRORLEVEL!

echo.
echo ============================================================
if !RC! EQU 0 (
    echo Tests abgeschlossen.
) else (
    echo ABORT: Tests mit Fehlern beendet ^(Exit-Code !RC!^).
    echo ABORT: Logdatei: %~dp0%LOGFILE%
)
echo Exit-Code: !RC!
echo Log-Datei: %~dp0%LOGFILE%
echo ============================================================
echo.
pause
exit /b !RC!
