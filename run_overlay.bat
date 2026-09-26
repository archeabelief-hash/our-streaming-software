@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Not installed yet. Running installer first...
  call install_windows.bat
)
call .venv\Scripts\activate.bat
python visual_tracker_overlay.py
if errorlevel 1 (
  echo.
  echo The overlay stopped with an error. Copy the error above into ChatGPT.
  pause
)
