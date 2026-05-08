@echo off
echo CLEANUP START > cleanup2.log
echo CWD=%CD% >> cleanup2.log
echo Trying delete files... >> cleanup2.log
del /F /Q "C:\Users\david\Documents\Pb_studio_AMD_version\verify_build.bat" >> cleanup2.log 2>&1
echo verify_build.bat: ERRORLEVEL=%ERRORLEVEL% >> cleanup2.log
del /F /Q "C:\Users\david\Documents\Pb_studio_AMD_version\build_verify.log" >> cleanup2.log 2>&1
echo build_verify.log: ERRORLEVEL=%ERRORLEVEL% >> cleanup2.log
del /F /Q "C:\Users\david\Documents\Pb_studio_AMD_version\build_verify.flag" >> cleanup2.log 2>&1
echo build_verify.flag: ERRORLEVEL=%ERRORLEVEL% >> cleanup2.log
echo CLEANUP END >> cleanup2.log
exit
