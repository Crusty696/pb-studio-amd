@echo off
cd /d "%~dp0"
echo === python.exe processes === > check_stress.log
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE >> check_stress.log
echo. >> check_stress.log
echo === stress_main.log size === >> check_stress.log
dir stress_main.log >> check_stress.log
echo. >> check_stress.log
echo === backend health === >> check_stress.log
curl -s -m 5 http://127.0.0.1:8765/health >> check_stress.log 2>&1
echo. >> check_stress.log
echo === backend_4h.log tail === >> check_stress.log
powershell -Command "Get-Content backend_4h.log -Tail 20" >> check_stress.log 2>&1
echo done > check_done.flag
