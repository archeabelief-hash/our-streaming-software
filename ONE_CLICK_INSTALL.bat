@echo off
setlocal
cd /d "%~dp0"

title Universal Visual Tracker Overlay - One Click Setup

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ONE_CLICK_SETUP.ps1"

if errorlevel 1 (
    echo.
    echo ============================================================
    echo SETUP FAILED
    echo ============================================================
    echo Copy the error shown above into ChatGPT and I can fix it.
    echo.
    pause
    exit /b 1
)

exit /b 0
