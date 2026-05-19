@echo off
REM WPF Release-Build fuer den LM-Studio-Refactor (Commit 8c46676)
cd /d "C:\Users\david\Documents\Pb_studio_AMD_version"

echo START %DATE% %TIME% > "%~dp0_build_result.txt"
echo. >> "%~dp0_build_result.txt"

REM Erst dotnet --version pruefen
echo --- dotnet --version --- >> "%~dp0_build_result.txt"
dotnet --version >> "%~dp0_build_result.txt" 2>&1
echo. >> "%~dp0_build_result.txt"

REM Release-Build
echo --- dotnet build Release --- >> "%~dp0_build_result.txt"
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release >> "%~dp0_build_result.txt" 2>&1
set BUILD_RC=%ERRORLEVEL%
echo. >> "%~dp0_build_result.txt"
echo --- BUILD EXIT CODE: %BUILD_RC% --- >> "%~dp0_build_result.txt"

REM Wenn erfolgreich: zeige den Output-Pfad
if %BUILD_RC%==0 (
    echo. >> "%~dp0_build_result.txt"
    echo --- Release-Binary --- >> "%~dp0_build_result.txt"
    dir PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.dll 2>&1 >> "%~dp0_build_result.txt"
)

echo. >> "%~dp0_build_result.txt"
echo END %DATE% %TIME% >> "%~dp0_build_result.txt"
exit /b %BUILD_RC%
