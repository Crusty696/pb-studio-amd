@echo off
REM PB Studio AMD - One-Shot Setup Wrapper (Doppelklick-faehig)
REM Hebt sich selbst auf Admin-Rechte falls noetig.
setlocal enabledelayedexpansion

REM Self-elevate to Admin via vbs trick.
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Admin-Rechte werden angefordert ...
    set _vbs=%TEMP%\pb_setup_elevate.vbs
    > "!_vbs!" echo Set UAC = CreateObject^("Shell.Application"^)
    >>"!_vbs!" echo UAC.ShellExecute "cmd.exe", "/c """%~f0"" %*", "%~dp0", "runas", 1
    cscript //nologo "!_vbs!"
    del "!_vbs!" >nul 2>&1
    exit /b
)

cd /d "%~dp0"

echo.
echo ============================================================
echo   PB Studio AMD - One-Shot Setup
echo ============================================================
echo.
echo Dieses Skript installiert / aktualisiert:
echo   - Python 3.11 venv
echo   - Brain-Stack (torch-directml, transformers, sqlite-vec, librosa)
echo   - FFmpeg + LibreHardwareMonitor in tools\
echo   - .NET 9 SDK falls fehlt
echo   - Pre-commit Hook
echo.
echo Dauer beim ersten Lauf: 5-15 Minuten (je nach Internet).
echo.
pause

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_pb_studio.ps1" %*
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo Setup erfolgreich. Druecke Taste um Fenster zu schliessen.
) else (
    echo Setup mit Fehlern beendet ^(Exit-Code %RC%^). Siehe logs\setup_log_*.txt.
)
pause
exit /b %RC%
