$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Ensure-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Windows Package Manager (winget) is required for automatic Python installation. Install 'App Installer' from the Microsoft Store, then run this installer again."
    }
}

function Find-Python311 {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles(x86)\Python311\python.exe"
    )

    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $resolved = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim()
            if ($resolved -and (Test-Path $resolved)) { return $resolved }
        } catch {}
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        try {
            $ver = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
            if ($ver -eq "3.11") {
                return (& python -c "import sys; print(sys.executable)").Trim()
            }
        } catch {}
    }

    return $null
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "Universal Visual Tracker Overlay - One Click Setup" -ForegroundColor Green
Write-Host "This will install everything required and then launch the app."

Write-Step "Checking Python 3.11"
$Python = Find-Python311

if (-not $Python) {
    Write-Host "Python 3.11 not found. Installing automatically..."
    Ensure-Winget

    winget install --id Python.Python.3.11 --exact --silent --accept-package-agreements --accept-source-agreements

    Start-Sleep -Seconds 3
    $Python = Find-Python311

    if (-not $Python) {
        throw "Python 3.11 installation completed, but Python could not be located. Restart Windows and run this installer again."
    }
}

Write-Host "Using Python: $Python"

Write-Step "Creating local app environment"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & $Python -m venv ".venv"
}

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment creation failed."
}

Write-Step "Updating installer tools"
& $VenvPython -m pip install --upgrade pip setuptools wheel

Write-Step "Installing core numeric dependency"
& $VenvPython -m pip install --upgrade numpy

Write-Step "Installing tracker and overlay dependencies"
& $VenvPython -m pip install -r requirements.txt

Write-Step "Creating desktop shortcut"
$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut((Join-Path $Desktop "Universal Visual Tracker Overlay.lnk"))
$Shortcut.TargetPath = (Join-Path $Root "START_TRACKER.bat")
$Shortcut.WorkingDirectory = $Root
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,23"
$Shortcut.Save()

Write-Step "Setup complete"
Write-Host "A desktop shortcut named 'Universal Visual Tracker Overlay' was created." -ForegroundColor Green
Write-Host "Launching now..." -ForegroundColor Green

Start-Process -FilePath (Join-Path $Root "START_TRACKER.bat")
