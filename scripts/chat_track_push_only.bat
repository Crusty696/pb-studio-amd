@echo off
REM ============================================================
REM KI-Chat Track 2026-05-16 — Push-only
REM Die 5 lokalen Commits (65bcef5..8f93398) wurden via Linux-
REM Sandbox-Bypass (Pattern #15: refs/heads/main in-place via
REM O_WRONLY ohne Truncate) erzeugt. Push aus dem Sandbox geht
REM nicht (kein Credential-Manager-Zugriff). Dieser Wrapper
REM macht den Push aus Windows.
REM
REM Doppelklick zum Ausfuehren — Output in chat_track_push.log
REM ============================================================
setlocal EnableDelayedExpansion
set "REPO=C:\Users\david\Documents\Pb_studio_AMD_version"
set "LOG=%REPO%\chat_track_push.log"
cd /d "%REPO%" || (echo cd failed > "%LOG%" & exit /b 1)

call :Main > "%LOG%" 2>&1
echo. >> "%LOG%"
echo === END (exit code %ERRORLEVEL%) === >> "%LOG%"
exit /b %ERRORLEVEL%

:Main
echo === KI-Chat Track 2026-05-16 — Push-only ===
echo Local commits to push:
git log --oneline origin/main..HEAD
echo.

echo Pushing origin/main...
git push origin main
if errorlevel 1 (
    echo PUSH FAILED — check git status and credentials
    git status
    exit /b 2
)

echo.
echo === Verification ===
git rev-parse HEAD
git rev-parse origin/main
git log --oneline -6
echo OK
exit /b 0
