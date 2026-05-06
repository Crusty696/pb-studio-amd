@echo off
REM PB Studio AMD - Run Full Tests (Doppelklick-faehig)
REM Loggt komplette Konsolen-Ausgabe nach logs\test_<ts>.log.
setlocal

cd /d "%~dp0"
if not exist "logs" mkdir logs

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set dt=%%I
set TS=%dt:~0,8%_%dt:~8,6%
if "%TS%"=="_" set TS=run

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
