@echo off
REM Visual review v2: wait 70s for 5-attempt threshold (3+6+12+24=45 + buffer)
cd /d "%~dp0"
echo === V2 Start: %date% %time% === > vr2.log

taskkill /F /IM python.exe /T  >nul 2>&1
taskkill /F /IM PBStudio.UI.exe /T >nul 2>&1
timeout /T 2 /NOBREAK >nul

start "PB-Backend" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python -m uvicorn backend.main:app --port 8765"
timeout /T 25 /NOBREAK >nul

start "" "PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe"
timeout /T 12 /NOBREAK >nul

echo Killing backend at %time% >> vr2.log
taskkill /F /IM python.exe /T >>vr2.log 2>&1

echo Waiting 70s (3+6+12+24+48=93s max, threshold @ attempt 5)... >> vr2.log
timeout /T 70 /NOBREAK >nul

powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr2_overlay.png'); $bmp.Dispose(); $g.Dispose();" >> vr2.log 2>&1
echo Screenshot vr2_overlay.png saved at %time% >> vr2.log

start "PB-Backend2" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python -m uvicorn backend.main:app --port 8765"
timeout /T 30 /NOBREAK >nul

powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr2_recovered.png'); $bmp.Dispose(); $g.Dispose();" >> vr2.log 2>&1

taskkill /F /IM PBStudio.UI.exe /T >nul 2>&1
taskkill /F /IM python.exe /T >nul 2>&1
echo === DONE %time% === >> vr2.log
echo OK > vr2_done.flag
