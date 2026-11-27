@echo off
setlocal
set "CASHOUT_PUBLISHER=%~dp0..\publish_nautilus.py"
if not exist "%CASHOUT_PUBLISHER%" (
    echo Cannot find the bundled publisher script. Extract the complete companion folder first.
    pause
    exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
    echo The Python launcher was not found. Use the Python 3 setup required by your existing bots.
    echo This helper does not install software or start the bots.
    pause
    exit /b 1
)
echo Checking the five existing local PAPER endpoints once.
echo This does not start bots, contact the app, or require a publisher key.
py -3 -X utf8 "%CASHOUT_PUBLISHER%" --check-local
set "CASHOUT_EXIT_CODE=%ERRORLEVEL%"
echo.
echo Check finished with exit code %CASHOUT_EXIT_CODE%.
pause
exit /b %CASHOUT_EXIT_CODE%
