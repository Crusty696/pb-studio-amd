@echo off
cd /d "%~dp0..\.."
set LOG=%~dp0push_to_origin.log
echo Push start %date% %time% > "%LOG%"
(
    echo === Commits to push ===
    git --no-pager log --oneline origin/main..main
    echo.
    echo === git push origin main ===
    git push origin main
    echo PUSH_RC=!ERRORLEVEL!
    echo.
    echo === New origin/main HEAD ===
    git --no-pager log --oneline origin/main -3
    echo.
    echo === DONE %date% %time% ===
) >> "%LOG%" 2>&1
endlocal
