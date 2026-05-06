@echo off
REM PB Studio AMD - One-Shot Setup Wrapper (Doppelklick-faehig)
REM Hebt sich selbst auf Admin-Rechte falls noetig.
REM Loggt komplette Konsolen-Ausgabe nach logs\setup_run_<ts>.log
REM (PS1-Skript loggt zusaetzlich nach logs\setup_log_<ts>.txt + setup_transcript_<ts>.txt)
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
if not exist "logs" mkdir logs

REM Timestamp via PowerShell (wmic deprecated auf Win11 24H2+)
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
if "%TS%"=="" set TS=run

set LOGFILE=logs\setup_run_%TS%.log

echo.
echo ============================================================
echo   PB Studio AMD - One-Shot Setup
echo ============================================================
echo.
echo Installiert / aktualisiert:
echo   - Python 3.11 venv
echo   - Brain-Stack (torch-directml, transformers, sqlite-vec, librosa)
echo   - FFmpeg + LibreHardwareMonitor in tools\
echo   - .NET 9 SDK falls fehlt
echo   - Pre-commit Hook
echo.
echo Log-Datei: %LOGFILE%
echo Dauer beim ersten Lauf: 5-15 Minuten (je nach Internet).
echo.
pause

REM Tee-Object faengt stdout+stderr ab und schreibt parallel ins Log.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "& '%~dp0setup_pb_studio.ps1' %* *>&1 | Tee-Object -FilePath '%~dp0%LOGFILE%'"
set RC=%ERRORLEVEL%

echo.
echo ============================================================
if %RC% EQU 0 (
    echo Setup erfolgreich.
) else (
    echo Setup mit Fehlern beendet ^(Exit-Code %RC%^).
)
echo.
echo Log-Dateien:
echo   %~dp0%LOGFILE%
echo   %~dp0logs\setup_log_*.txt
echo   %~dp0logs\setup_transcript_*.txt
echo ============================================================
echo.
echo Druecke beliebige Taste um Fenster zu schliessen.
pause >nul
exit /b %RC%
