@echo off
cd /d C:\Users\david\Documents\Pb_studio_AMD_version
call .venv\Scripts\activate.bat
set PYTHONPATH=src
echo ===AUDIT_RUN_START=== > pytest_audit.log
python -m pytest Tests\ -q >> pytest_audit.log 2>&1
echo. >> pytest_audit.log
echo ===AUDIT_RUN_DONE=== >> pytest_audit.log
