@echo off
REM PB Studio AMD - Run Full Tests (Doppelklick-faehig)
setlocal

cd /d "%~dp0"

echo.
echo ============================================================
echo   PB Studio AMD - Test Suite
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Fehler: .venv fehlt. Bitte erst setup.bat ausfuehren.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_full_test.ps1" %*
set RC=%ERRORLEVEL%
echo.
echo Exit-Code: %RC%
pause
exit /b %RC%
