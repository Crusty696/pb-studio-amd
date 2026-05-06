@echo off
REM PB Studio AMD - Run Full Tests (Doppelklick-faehig)
REM Loggt komplette Konsolen-Ausgabe nach logs\test_<ts>.log.
setlocal

cd /d "%~dp0"
if not exist "logs" mkdir logs

REM Timestamp via PowerShell (wmic deprecated auf Win11 24H2+)
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
if "%TS%"=="" set TS=run

set LOGFILE=logs\test_%TS%.log

echo.
echo ============================================================
echo   PB Studio AMD - Test Suite
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
  "& '%~dp0run_full_test.ps1' %* *>&1 | Tee-Object -FilePath '%~dp0%LOGFILE%'"
set RC=%ERRORLEVEL%

echo.
echo ============================================================
echo Exit-Code: %RC%
echo Log-Datei: %~dp0%LOGFILE%
echo ============================================================
echo.
pause
exit /b %RC%
