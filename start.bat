@echo off
REM PB Studio AMD - Start App (Doppelklick-faehig)
REM Startet Python-Backend + WPF-Frontend via launch.ps1.
REM Loggt komplette Konsolen-Ausgabe nach logs\start_<ts>.log.
setlocal

cd /d "%~dp0"
if not exist "logs" mkdir logs

REM Timestamp via PowerShell (wmic ist auf Win11 24H2+ deprecated/entfernt)
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
if "%TS%"=="" set TS=run

set LOGFILE=logs\start_%TS%.log

echo.
echo ============================================================
echo   PB Studio AMD - Start
echo ============================================================
echo Log-Datei: %LOGFILE%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Fehler: .venv fehlt. Bitte erst setup.bat ausfuehren.
    echo Fehler: .venv fehlt > "%LOGFILE%"
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "& '%~dp0launch.ps1' %* *>&1 | Tee-Object -FilePath '%~dp0%LOGFILE%'"
set RC=%ERRORLEVEL%

echo.
echo ============================================================
if %RC% EQU 0 (
    echo App beendet.
) else (
    echo App mit Fehlern beendet ^(Exit-Code %RC%^).
)
echo Log-Datei: %~dp0%LOGFILE%
echo ============================================================
echo.
pause
exit /b %RC%
