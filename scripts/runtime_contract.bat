@echo off
set "PBSTUDIO_PROJECT_ROOT=%~dp0.."
for %%I in ("%PBSTUDIO_PROJECT_ROOT%") do set "PBSTUDIO_PROJECT_ROOT=%%~fI"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime_contract_check.ps1" -ProjectRoot "%PBSTUDIO_PROJECT_ROOT%" -RequirePython -RequireFFmpeg
if errorlevel 1 exit /b %ERRORLEVEL%
set "PBSTUDIO_PYTHON_EXE=%PBSTUDIO_PROJECT_ROOT%\.venv\Scripts\python.exe"
set "PYTHONPATH=%PBSTUDIO_PROJECT_ROOT%\src"
set "PBSTUDIO_FFMPEG_PATH=%PBSTUDIO_PROJECT_ROOT%\tools\ffmpeg\bin\ffmpeg.exe"
set "PBSTUDIO_FFPROBE_PATH=%PBSTUDIO_PROJECT_ROOT%\tools\ffmpeg\bin\ffprobe.exe"
