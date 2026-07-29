@echo off
REM PB Studio AMD - One-Shot Setup Wrapper (Doppelklick-faehig)
REM Loggt komplette Konsolen-Ausgabe nach logs\setup_run_<ts>.log
REM (PS1-Skript loggt zusaetzlich nach logs\setup_log_<ts>.txt + setup_transcript_<ts>.txt)
setlocal enabledelayedexpansion

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Setup laeuft ohne Admin-Rechte. Systemweite winget-Installationen
    echo [WARN] koennen fail-closed abbrechen. Bei Bedarf dieses Skript manuell
    echo [WARN] ueber eine bereits erhoehte Eingabeaufforderung starten.
)
cd /d "%~dp0"
REM logs-Verzeichnis MUSS vor dem Tee-Object-Pipe existieren
if not exist "logs" mkdir logs

REM Timestamp via PowerShell (wmic deprecated auf Win11 24H2+)
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
if "!TS!"=="" set TS=run

set LOGFILE=logs\setup_run_!TS!.log

echo.
echo ============================================================
echo   PB Studio AMD - One-Shot Setup
echo ============================================================
echo.
echo Installiert / aktualisiert:
echo   - Python 3.11 venv
echo   - AMD-Stack (ONNX Runtime DirectML, transformers, sqlite-vec, librosa)
echo   - Hashverifiziertes FFmpeg in tools\
echo   - LHM-Monitoring nur mit freigegebenem lokalen Bundle-Manifest
echo   - .NET 9 SDK falls fehlt
echo   - Pre-commit Hook
echo.
echo Log-Datei: %LOGFILE%
echo Dauer beim ersten Lauf: 5-15 Minuten (je nach Internet).
echo.
if not defined NOPAUSE (
    echo Druecke beliebige Taste um Setup zu starten (oder Fenster schliessen zum Abbruch^) ...
    pause >nul
)

REM Der Doppelklick-Wrapper akzeptiert absichtlich keine Argumente. Fuer
REM optionale Switches setup_pb_studio.ps1 direkt mit -File aufrufen.
set "_PS1=%~dp0setup_pb_studio.ps1"
set "_LF=%~dp0%LOGFILE%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_with_log.ps1" -SetupScript "!_PS1!" -LogFile "!_LF!"
set RC=!ERRORLEVEL!

REM ABORT-on-Error: Immer Exit-Code und Log-Pfad ausgeben
echo.
echo ============================================================
if !RC! EQU 0 (
    echo Setup erfolgreich.
) else (
    echo ABORT: Setup mit Fehlern beendet ^(Exit-Code !RC!^).
    echo ABORT: Logdatei: %~dp0%LOGFILE%
    echo ABORT: Weitere Logs: %~dp0logs\setup_log_*.txt + setup_transcript_*.txt
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
exit /b !RC!
