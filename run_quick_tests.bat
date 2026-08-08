@echo off
cd /d "%~dp0"
call "%~dp0scripts\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
echo ===QUICK_START=== > pytest_quick.log
"%PBSTUDIO_PYTHON_EXE%" -m pytest Tests\ -q -k "brain or clap or spectral or stem or vram or trigger_settings or beat_progress or pacing_progress" >> pytest_quick.log 2>&1
echo. >> pytest_quick.log
echo ===QUICK_DONE=== >> pytest_quick.log
