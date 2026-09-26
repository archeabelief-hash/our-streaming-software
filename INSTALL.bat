@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Universal Visual Tracker Overlay - Safe One Click Setup

echo ============================================================
echo Universal Visual Tracker Overlay - Safe One Click Setup
echo ============================================================
echo.
echo This installer uses only standard Windows commands, winget,
echo Python, and pip. It does NOT use PowerShell ExecutionPolicy
echo bypasses or disable antivirus/security features.
echo.

set "PYTHON_EXE="

echo [1/5] Checking for Python 3.11...

where py >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    )
)

if not defined PYTHON_EXE (
    echo Python 3.11 was not found.
    echo Attempting installation through Windows Package Manager...
    echo.

    where winget >nul 2>nul
    if errorlevel 1 (
        echo ERROR: winget is not available.
        echo Install "App Installer" from the Microsoft Store, then run this file again.
        echo.
        pause
        exit /b 1
    )

    winget install --id Python.Python.3.11 --exact --accept-package-agreements --accept-source-agreements

    if errorlevel 1 (
        echo.
        echo ERROR: Python installation failed.
        pause
        exit /b 1
    )

    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    )
)

if not defined PYTHON_EXE (
    echo.
    echo ERROR: Python 3.11 could not be located after installation.
    echo Restart Windows and run this installer again.
    pause
    exit /b 1
)

echo Found Python:
echo %PYTHON_EXE%
echo.

echo [2/5] Creating private Python environment...
if not exist ".venv\Scripts\python.exe" (
    "%PYTHON_EXE%" -m venv ".venv"
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

echo.
echo [3/5] Updating Python package installer...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERROR: pip setup failed.
    pause
    exit /b 1
)

echo.
echo [4/5] Installing required packages...
"%VENV_PY%" -m pip install numpy
if errorlevel 1 (
    echo ERROR: NumPy installation failed.
    pause
    exit /b 1
)

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [5/5] Setup complete.
echo.
echo Starting Universal Visual Tracker Overlay...
echo.

call "%~dp0START_TRACKER.bat"
exit /b 0
