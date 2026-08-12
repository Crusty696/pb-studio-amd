@echo off
setlocal
cd /d "%~dp0"
for %%I in ("%~dp0..\..") do set "PBSTUDIO_PROJECT_ROOT=%%~fI"
for /f "delims=" %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ". ([IO.Path]::Combine($env:PBSTUDIO_PROJECT_ROOT,'scripts','runtime_contract.ps1')); (Get-PBStudioBackendEndpoint -ProjectRoot $env:PBSTUDIO_PROJECT_ROOT).Origin"') do set "PBSTUDIO_BACKEND_ORIGIN=%%I"
if not defined PBSTUDIO_BACKEND_ORIGIN exit /b 1
echo === python.exe processes === > check_stress.log
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE >> check_stress.log
echo. >> check_stress.log
echo === stress_main.log size === >> check_stress.log
dir stress_main.log >> check_stress.log
echo. >> check_stress.log
echo === backend health === >> check_stress.log
curl -s -m 5 "%PBSTUDIO_BACKEND_ORIGIN%/health" >> check_stress.log 2>&1
echo. >> check_stress.log
echo === backend_4h.log tail === >> check_stress.log
powershell -Command "Get-Content backend_4h.log -Tail 20" >> check_stress.log 2>&1
echo done > check_done.flag
