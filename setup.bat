@echo off
REM PB Studio AMD - One-Shot Setup Wrapper (Doppelklick-faehig)
REM Hebt sich selbst auf Admin-Rechte falls noetig.
REM Loggt komplette Konsolen-Ausgabe nach logs\setup_run_<ts>.log
REM (PS1-Skript loggt zusaetzlich nach logs\setup_log_<ts>.txt + setup_transcript_<ts>.txt)
setlocal enabledelayedexpansion

REM -----------------------------------------------------------------------
REM Self-elevate to Admin via PowerShell Start-Process -Verb RunAs.
REM MUSS vor allem anderen stehen. Net-session-Check verhindert Loop.
REM -----------------------------------------------------------------------
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if "%1"=="--no-elevation" (
        shift
        goto :continue
    )
    echo Admin-Rechte werden angefordert (fuer optionale System-Installationen) ...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
      "try { Start-Process cmd.exe -Verb RunAs -ArgumentList '/c \"\"%~f0\"\" --no-elevation %*' -WorkingDirectory '%~dp0' -ErrorAction Stop } catch { exit 1 }"
    if !ERRORLEVEL! EQU 0 (
        exit /b 0
    )
    echo.
    echo [WARN] Admin-Erhoehung abgelehnt/fehlgeschlagen. Fahre im User-Scope fort...
    echo [WARN] Einige winget-Installationen werden im User-Scope ausgefuehrt.
    echo.
)
:continue
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
echo   - Brain-Stack (torch-directml, transformers, sqlite-vec, librosa)
echo   - FFmpeg + LibreHardwareMonitor in tools\
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

REM Streaming-Tee: stdout+stderr auf Konsole UND utf8-Log (PS5.1 kompatibel).
REM Alle Skip-Flags werden an PS1 weitergereicht (%*).
set "_PS1=%~dp0setup_pb_studio.ps1"
set "_LF=%~dp0%LOGFILE%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lf='!_LF!'; $ps1='!_PS1!'; powershell.exe -NoProfile -ExecutionPolicy Bypass -File '!_PS1!' %* *>&1 | ForEach-Object { $s=[string]$_; Write-Host $s; Add-Content -Path $lf -Value $s -Encoding utf8 }; exit $LASTEXITCODE"
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
