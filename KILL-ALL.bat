@echo off
taskkill /F /IM python.exe /T  >nul 2>&1
taskkill /F /IM PBStudio.UI.exe /T >nul 2>&1
echo killed > kill_all_done.flag
