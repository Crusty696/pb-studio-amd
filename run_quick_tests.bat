@echo off
cd /d C:\Users\david\Documents\Pb_studio_AMD_version
call .venv\Scripts\activate.bat
set PYTHONPATH=src
echo ===QUICK_START=== > pytest_quick.log
python -m pytest Tests\ -q -k "brain or clap or spectral or stem or vram or trigger_settings or beat_progress or pacing_progress" >> pytest_quick.log 2>&1
echo. >> pytest_quick.log
echo ===QUICK_DONE=== >> pytest_quick.log
