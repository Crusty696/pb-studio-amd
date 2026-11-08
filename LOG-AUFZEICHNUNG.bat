@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo FEHLER: Projekt-Python fehlt.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -u "%~dp0scripts\record_app_session.py" %*
set "RECORDER_RC=%ERRORLEVEL%"
if not "%RECORDER_RC%"=="0" echo FEHLER: Aufzeichnung beendet mit Code %RECORDER_RC%.
exit /b %RECORDER_RC%
