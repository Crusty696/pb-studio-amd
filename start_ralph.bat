@echo off
title Ralph - PB Studio AMD
echo ========================================
echo   Ralph fuer PB Studio AMD starten
echo   (nutzt Claude Abo, kein API Key)
echo ========================================
echo.

REM API Key leeren damit Claude Abo genutzt wird
set ANTHROPIC_API_KEY=

REM MSYS2 DLL-Workaround: Verhindert concurrent DLL loading crashes
REM Die folgenden Variablen stabilisieren Git Bash unter hoher Last
set MSYS=winsymlinks:nativestrict
set MSYS2_ARG_CONV_EXCL=*
set HOME=%USERPROFILE%

REM Git Bash Pfad pruefen
if not exist "C:\Program Files\Git\bin\bash.exe" (
    echo FEHLER: Git Bash nicht gefunden unter C:\Program Files\Git\bin\bash.exe
    echo Bitte Git for Windows installieren.
    pause
    exit /b 1
)

REM Projekt-Verzeichnis
set PROJECT_DIR=C:\Users\david\Dokumente\Pb_studio_AMD_version

REM Wechsel ins Projektverzeichnis VOR dem Bash-Aufruf
cd /d "%PROJECT_DIR%"

echo Starte Ralph im Verzeichnis: %PROJECT_DIR%
echo.

REM Ralph ausfuehren - cd entfaellt weil wir schon im richtigen Verzeichnis sind
"C:\Program Files\Git\bin\bash.exe" --login -c "unset ANTHROPIC_API_KEY; export MSYS=winsymlinks:nativestrict; export MSYS2_ARG_CONV_EXCL='*'; ralph --reset-session && ralph --live --verbose"

echo.
echo Ralph beendet.
pause
