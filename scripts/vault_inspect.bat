@echo off
setlocal EnableDelayedExpansion
set "VAULT=C:\Users\david\Brain\10_Projects\PB_studio"
set "LOG=C:\Users\david\Documents\Pb_studio_AMD_version\vault_inspect.log"
cd /d "%VAULT%"
powershell -NoProfile -Command "Get-Content 'INDEX.md' -TotalCount 30" > "%LOG%" 2>&1
echo === END === >> "%LOG%"
exit /b 0
