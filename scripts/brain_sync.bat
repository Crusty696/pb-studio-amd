@echo off
rem PB Studio - Brain Sync & Status Wrapper für Gemini CLI
rem Etabliert das Gemini-Pendant zu /brain-sync und /brain-status

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
cd /d "%REPO_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtuelle Umgebung .venv nicht gefunden!
    echo Bitte setup.bat oder setup_pb_studio.ps1 ausfuehren.
    exit /b 1
)

.venv\Scripts\python "%SCRIPT_DIR%brain_sync.py" %*
exit /b %ERRORLEVEL%
