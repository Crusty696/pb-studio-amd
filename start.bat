@echo off
REM PB Studio AMD - Start App (Doppelklick-faehig)
REM Startet Python-Backend + WPF-Frontend via launch.ps1.
setlocal

cd /d "%~dp0"

echo.
echo ============================================================
echo   PB Studio AMD - Start
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Fehler: .venv fehlt. Bitte erst setup.bat ausfuehren.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" %*
set RC=%ERRORLEVEL%

if %RC% NEQ 0 (
    echo.
    echo App mit Fehlern beendet ^(Exit-Code %RC%^).
    pause
)
exit /b %RC%
