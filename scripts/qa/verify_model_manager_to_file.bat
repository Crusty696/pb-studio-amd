@echo off
REM Variant of verify_model_manager.bat that redirects ALL output to a log file
REM so a remote agent can read the build result via filesystem without needing
REM Terminal/PowerShell visibility access.
setlocal enabledelayedexpansion
cd /d "%~dp0..\.."
set "PBSTUDIO_PROJECT_ROOT=%CD%"
for /f "delims=" %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ". ([IO.Path]::Combine($env:PBSTUDIO_PROJECT_ROOT,'scripts','runtime_contract.ps1')); (Get-PBStudioBackendEndpoint -ProjectRoot $env:PBSTUDIO_PROJECT_ROOT).Origin"') do set "PBSTUDIO_BACKEND_ORIGIN=%%I"
if not defined PBSTUDIO_BACKEND_ORIGIN exit /b 1
set LOG=%~dp0verify_model_manager.log
echo Verify start %date% %time% > "%LOG%"

(
    echo === [1/5] Git index.lock cleanup ===
    if exist ".git\index.lock" ( del /F ".git\index.lock" 2^>nul ^&^& echo  -^> deleted ) else ( echo  -^> none )

    echo.
    echo === [2/5] Last 6 commits ===
    git --no-pager log --oneline -6

    echo.
    echo === [3/5] dotnet Release build ===
    dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --nologo -v minimal
    echo BUILD_RC=!ERRORLEVEL!

    echo.
    echo === [4/5] Backend /models/list ===
    curl -s -m 3 "!PBSTUDIO_BACKEND_ORIGIN!/models/list"
    echo.

    echo.
    echo === [5/5] /models/recommendations?mode=balance ===
    curl -s -m 3 "!PBSTUDIO_BACKEND_ORIGIN!/models/recommendations?task=video_captioning&mode=balance"
    echo.

    echo.
    echo === DONE %date% %time% ===
) >> "%LOG%" 2>&1

echo Build log: %LOG%
endlocal
