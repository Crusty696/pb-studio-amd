@echo off
set "LOG=C:\Users\david\Documents\Pb_studio_AMD_version\vault_fm_fix.log"
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\david\Documents\Pb_studio_AMD_version\scripts\vault_update_fm.ps1" > "%LOG%" 2>&1
echo === END === >> "%LOG%"
exit /b 0
