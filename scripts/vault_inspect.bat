@echo off
setlocal EnableDelayedExpansion
set "VAULT=%USERPROFILE%\Brain\10_Projects\PB_studio"
for %%I in ("%~dp0..") do set "REPO=%%~fI"
set "LOG=%REPO%\vault_inspect.log"
cd /d "%VAULT%"
powershell -NoProfile -Command "Get-Content 'INDEX.md' -TotalCount 30" > "%LOG%" 2>&1
echo === END === >> "%LOG%"
exit /b 0
