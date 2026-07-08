@echo off
REM PB Studio AMD - Run Full Tests (Doppelklick-faehig)
REM Loggt komplette Konsolen-Ausgabe nach logs\test_<ts>.log.
setlocal enabledelayedexpansion

cd /d "%~dp0"
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

set "_PS1=%~dp0run_full_test.ps1"
set "_LF=%~dp0%LOGFILE%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lf='!_LF!'; $ps1='!_PS1!'; powershell.exe -NoProfile -ExecutionPolicy Bypass -File '!_PS1!' %* *>&1 | ForEach-Object { $s=[string]$_; Write-Host $s; Add-Content -Path $lf -Value $s -Encoding utf8 }; exit $LASTEXITCODE"
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
