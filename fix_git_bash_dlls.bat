@echo off
title Git Bash DLL Reparatur
echo ========================================
echo   Git Bash DLL Rebase Reparatur
echo ========================================
echo.
echo WICHTIG: Alle Git Bash / MSYS2 Fenster muessen
echo geschlossen sein bevor du das ausfuehrst!
echo.
echo Dieses Script fixt den "error while loading
echo shared libraries" Fehler bei Git Bash.
echo.
pause

echo.
echo Starte DLL Rebase...
"C:\Program Files\Git\usr\bin\dash.exe" -c "/usr/bin/rebaseall -v"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   DLL Rebase erfolgreich!
    echo ========================================
    echo Git Bash sollte jetzt ohne Fehler laufen.
) else (
    echo.
    echo ========================================
    echo   FEHLER beim DLL Rebase
    echo ========================================
    echo Stelle sicher dass ALLE Git Bash Fenster
    echo geschlossen sind und starte als Admin.
)

echo.
pause
