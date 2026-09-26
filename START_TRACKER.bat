@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Tracker is not installed yet. Running one-click setup...
    call "%~dp0ONE_CLICK_INSTALL.bat"
    exit /b
)

start "" ".venv\Scripts\pythonw.exe" "%~dp0visual_tracker_overlay.py"
