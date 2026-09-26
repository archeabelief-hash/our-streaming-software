@echo off
setlocal
cd /d "%~dp0"

echo === Universal Visual Tracker Overlay installer ===
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found.
  echo Install Python 3.11 64-bit from python.org, check "Add Python to PATH", then run this again.
  pause
  exit /b 1
)

if not exist .venv (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Could not create Python 3.11 virtual environment.
    echo If you have Python 3.10 instead, edit this file and replace -3.11 with -3.10.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip wheel setuptools

REM Explicit first install avoids the common "No module named numpy" problem.
python -m pip install numpy
python -m pip install -r requirements.txt

if errorlevel 1 (
  echo.
  echo Installation failed. Copy the error above into ChatGPT and I can fix the exact dependency.
  pause
  exit /b 1
)

echo.
echo Installation complete.
echo Run run_overlay.bat
pause
