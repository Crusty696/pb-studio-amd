@echo off
REM Visual review: backend up, app visible, then kill backend, capture overlay
cd /d "%~dp0"
echo === Visual Review Start: %date% %time% === > vr_test.log

taskkill /F /IM python.exe /T  >nul 2>&1
taskkill /F /IM PBStudio.UI.exe /T >nul 2>&1
timeout /T 2 /NOBREAK >nul

REM Backend in minimized window
start "PB-Backend" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python -m uvicorn backend.main:app --port 8765"
timeout /T 25 /NOBREAK >nul

REM WPF App in NORMAL window (no /MIN)
start "" "PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe"
timeout /T 12 /NOBREAK >nul

REM Initial screenshot - app visible, no overlay
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr_1_app_normal.png'); $bmp.Dispose(); $g.Dispose();" >> vr_test.log 2>&1

REM Kill backend
echo Killing backend at %time% >> vr_test.log
taskkill /F /IM python.exe /T >>vr_test.log 2>&1
echo Waiting 22s for 5-attempt threshold... >> vr_test.log
timeout /T 22 /NOBREAK >nul

REM Screenshot 2: should show overlay
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr_2_overlay_visible.png'); $bmp.Dispose(); $g.Dispose();" >> vr_test.log 2>&1

REM Restart backend
start "PB-Backend2" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python -m uvicorn backend.main:app --port 8765"
timeout /T 25 /NOBREAK >nul

REM Screenshot 3: overlay should be gone
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr_3_recovered.png'); $bmp.Dispose(); $g.Dispose();" >> vr_test.log 2>&1

REM Cleanup
taskkill /F /IM PBStudio.UI.exe /T >nul 2>&1
taskkill /F /IM python.exe /T >nul 2>&1

echo === DONE %time% === >> vr_test.log
echo OK > vr_test_done.flag
