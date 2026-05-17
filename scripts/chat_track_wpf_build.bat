@echo off
REM ============================================================
REM KI-Chat Track 2026-05-16 — WPF Release Build
REM Iron Rule 10: C#-Aenderung -> Release-Build erforderlich
REM Output: chat_track_wpf_build.log
REM ============================================================
setlocal EnableDelayedExpansion
set "REPO=C:\Users\david\Documents\Pb_studio_AMD_version"
set "LOG=%REPO%\chat_track_wpf_build.log"
cd /d "%REPO%" || (echo cd failed > "%LOG%" & exit /b 1)

call :Main > "%LOG%" 2>&1
echo. >> "%LOG%"
echo === END (exit code %ERRORLEVEL%) === >> "%LOG%"
exit /b %ERRORLEVEL%

:Main
echo === WPF Release Build (KI-Chat-Track) ===
echo HEAD:
git rev-parse HEAD
echo.
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --nologo
exit /b %ERRORLEVEL%
