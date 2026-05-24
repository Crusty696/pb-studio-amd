@echo off
REM PB Studio AMD - Start App (Doppelklick-faehig)
REM Auto-Rebuild: prueft ob Source neuer als DLL, baut bei Bedarf.
REM Startet Python-Backend + WPF-Frontend via launch.ps1.
REM Loggt komplette Konsolen-Ausgabe nach logs\start_<ts>.log.
setlocal enabledelayedexpansion

cd /d "%~dp0"

REM Pruefe ob portables .NET SDK vorhanden ist und konfiguriere Umgebung
if exist "%~dp0tools\dotnet\dotnet.exe" (
    set "DOTNET_ROOT=%~dp0tools\dotnet"
    set "PATH=%~dp0tools\dotnet;%PATH%"
    echo [INFO] Nutze portables .NET SDK unter tools\dotnet.
)

REM logs-Verzeichnis MUSS vor dem Tee-Object-Pipe existieren
if not exist "logs" mkdir logs

REM Timestamp via PowerShell (wmic ist auf Win11 24H2+ deprecated/entfernt)
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
if "!TS!"=="" set TS=run

set LOGFILE=logs\start_!TS!.log

echo.
echo ============================================================
echo   PB Studio AMD - Start
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

REM ============================================================
REM [1/2] BUILD - Auto-Rebuild wenn Source neuer als DLL
REM ============================================================
echo [1/2] Build-Check...
echo [1/2] Build-Check... >> "!LOGFILE!"

set DLL=PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.dll
set BUILD_NEEDED=0

REM Pruefe ob DLL existiert
if not exist "!DLL!" (
    echo   DLL fehlt - Build erforderlich.
    echo   DLL fehlt - Build erforderlich. >> "!LOGFILE!"
    set BUILD_NEEDED=1
)

REM Pruefe Timestamp: Source neuer als DLL?
if "!BUILD_NEEDED!"=="0" (
    set "_DLLPATH=%~dp0!DLL!"
    set "_SRCPATH=%~dp0PBStudio.UI"
    for /f "delims=" %%R in ('powershell -NoProfile -Command "$d=(Get-Item '!_DLLPATH!' -EA SilentlyContinue).LastWriteTimeUtc;$s=(Get-ChildItem -Path '!_SRCPATH!' -Recurse -Include '*.cs','*.xaml','*.csproj'|Sort-Object LastWriteTimeUtc -Desc|Select-Object -First 1).LastWriteTimeUtc;if(-not $d){'BUILD'}elseif($s-gt$d){'BUILD'}else{'SKIP'}"') do set TSCHECK=%%R
    if "!TSCHECK!"=="BUILD" (
        echo   Source neuer als DLL - Build erforderlich.
        echo   Source neuer als DLL - Build erforderlich. >> "!LOGFILE!"
        set BUILD_NEEDED=1
    ) else (
        echo   DLL aktuell - kein Build noetig.
        echo   DLL aktuell - kein Build noetig. >> "!LOGFILE!"
    )
)

REM Build ausfuehren wenn noetig
if "!BUILD_NEEDED!"=="1" (
    echo   Starte Build: Release...
    echo   Starte Build: Release... >> "!LOGFILE!"
    set "_BPS1=%~dp0build.ps1"
    set "_BLF=%~dp0!LOGFILE!"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
      "$lf='!_BLF!'; $ps1='!_BPS1!'; powershell.exe -NoProfile -ExecutionPolicy Bypass -File '!_BPS1!' -Configuration Release *>&1 | ForEach-Object { $s=[string]$_; Write-Host $s; Add-Content -Path $lf -Value $s -Encoding utf8 }; exit $LASTEXITCODE"
    set BUILD_RC=!ERRORLEVEL!
    if !BUILD_RC! NEQ 0 (
        echo.
        echo ============================================================
        echo ABORT: Build fehlgeschlagen ^(Exit-Code !BUILD_RC!^).
        echo ABORT: Kein Launch - bitte Fehler im Log pruefen.
        echo ABORT: Log: %~dp0!LOGFILE!
        echo ============================================================
        echo ABORT: Build fehlgeschlagen Exit-Code !BUILD_RC! >> "!LOGFILE!"
        pause
        exit /b !BUILD_RC!
    )
    echo   Build erfolgreich.
    echo   Build erfolgreich. >> "!LOGFILE!"
)

REM ============================================================
REM [2/2] LAUNCH - Backend + Frontend starten
REM ============================================================
echo.
echo [2/2] Launch...
echo [2/2] Launch... >> "!LOGFILE!"

set "_PS1=%~dp0launch.ps1"
set "_LF=%~dp0%LOGFILE%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lf='!_LF!'; $ps1='!_PS1!'; powershell.exe -NoProfile -ExecutionPolicy Bypass -File '!_PS1!' %* *>&1 | ForEach-Object { $s=[string]$_; Write-Host $s; Add-Content -Path $lf -Value $s -Encoding utf8 }; exit $LASTEXITCODE"
set RC=!ERRORLEVEL!

echo.
echo ============================================================
if !RC! EQU 0 (
    echo App beendet.
) else (
    echo ABORT: App mit Fehlern beendet ^(Exit-Code !RC!^).
    echo ABORT: Logdatei: %~dp0%LOGFILE%
)
echo Log-Datei: %~dp0%LOGFILE%
echo ============================================================
echo.
pause
exit /b !RC!
