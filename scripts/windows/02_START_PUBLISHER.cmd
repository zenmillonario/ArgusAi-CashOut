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
echo Starting the display publisher for https://cashoutai.onrender.com
echo Keep your five existing PAPER engines running in their own windows.
echo Enter the publisher key at the hidden prompt. It is not saved.
echo The entered key overrides any publisher key in the environment for this run.
echo Leave this window open while publishing. Press Ctrl+C to stop the publisher.
py -3 "%CASHOUT_PUBLISHER%" --backend "https://cashoutai.onrender.com" --prompt-key
set "CASHOUT_EXIT_CODE=%ERRORLEVEL%"
echo.
echo Publisher finished with exit code %CASHOUT_EXIT_CODE%.
pause
exit /b %CASHOUT_EXIT_CODE%
