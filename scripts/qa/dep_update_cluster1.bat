@echo off
REM Retired dependency mutation helper. Dependency changes require an approved
REM requirements update and setup workflow; this script never mutates the venv.
cd /d "%~dp0\..\.."
call "%~dp0..\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%

echo ABORT: dep_update_cluster1.bat ist stillgelegt.
echo Abhaengigkeiten nur ueber freigegebene requirements und setup.bat aendern.
exit /b 2
