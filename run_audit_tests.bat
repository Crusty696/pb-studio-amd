@echo off
cd /d "%~dp0"
call "%~dp0scripts\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
echo ===AUDIT_RUN_START=== > pytest_audit.log
"%PBSTUDIO_PYTHON_EXE%" -m pytest Tests\ -q >> pytest_audit.log 2>&1
echo. >> pytest_audit.log
echo ===AUDIT_RUN_DONE=== >> pytest_audit.log
