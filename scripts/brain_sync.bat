@echo off
rem PB Studio - Brain Sync & Status Wrapper für Gemini CLI
rem Etabliert das Gemini-Pendant zu /brain-sync und /brain-status

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
cd /d "%REPO_ROOT%"
call "%SCRIPT_DIR%runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtuelle Umgebung .venv nicht gefunden!
    echo Bitte setup.bat oder setup_pb_studio.ps1 ausfuehren.
    exit /b 1
)

"%PBSTUDIO_PYTHON_EXE%" "%SCRIPT_DIR%brain_sync.py" %*
exit /b %ERRORLEVEL%
