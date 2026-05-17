@echo off
REM ============================================================
REM Verify Model-Manager-UI (Phase Ollama-Pilot, 2026-05-16)
REM Build + minimal API-Smoke-Check fuer commits c80474d/e3e8d64/f5703e2
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0..\.."

echo.
echo === [1/5] Git index.lock entfernen falls vorhanden ===
if exist ".git\index.lock" (
    del /F ".git\index.lock" >nul 2>&1
    echo  -> .git\index.lock geloescht
) else (
    echo  -> kein Lock-File da
)

echo.
echo === [2/5] Letzte 4 Commits ===
git --no-pager log --oneline -4

echo.
echo === [3/5] dotnet Release-Build PBStudio.UI ===
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --nologo -v minimal
set BUILD_RC=%ERRORLEVEL%
if not %BUILD_RC%==0 (
    echo  *** BUILD FAILED rc=%BUILD_RC% ***
    pause
    exit /b %BUILD_RC%
)
echo  -> Build OK

echo.
echo === [4/5] Backend Health-Check ===
curl -s -m 3 http://localhost:8765/models/list
if errorlevel 1 (
    echo  ! Backend nicht erreichbar - bitte erst start.bat ausfuehren
) else (
    echo.
    echo  -> /models/list reachable
)

echo.
echo === [5/5] Ollama recommendation check ===
curl -s -m 3 "http://localhost:8765/models/recommendations?task=video_captioning&mode=balance"
echo.

echo.
echo ============================================================
echo VERIFY DONE. Wenn Build OK + Backend reachable:
echo   start.bat ausfuehren -^> MODELLE-Tab (ganz rechts) klicken
echo   SETTINGS-Tab -^> KI-MODUS-Slider verstellen
echo ============================================================
pause
endlocal
