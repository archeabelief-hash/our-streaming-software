# Universal Visual Tracker Overlay

A local, visual-only Windows overlay for improving on-screen visibility while gaming or using other desktop applications.

## ONE-CLICK WINDOWS INSTALL

Download/extract the repository, then double-click:

`SAFE_ONE_CLICK_INSTALL.bat`

This version deliberately avoids PowerShell `ExecutionPolicy Bypass` and does not disable or modify Windows Defender.

It automatically:

1. Checks for Python 3.11.
2. Uses Windows Package Manager (`winget`) to install Python 3.11 if needed.
3. Creates a private `.venv` environment inside the folder.
4. Installs NumPy.
5. Installs RF-DETR, Trackers/ByteTrack, PySide6, screen capture, and other dependencies.
6. Launches the tracker.

After installation, use:

`START_TRACKER.bat`

## Security

The installer does **not**:
- disable Microsoft Defender;
- add antivirus exclusions;
- use PowerShell ExecutionPolicy bypass;
- modify another process;
- inject code into games;
- read game memory;
- download arbitrary executables from unknown sites.

Python is installed through Microsoft's `winget` package source, and Python dependencies are installed through `pip`.

If your antivirus still reports a malware detection, do **not** override it. Record the exact threat name and the exact file Defender says is infected so it can be investigated.

## What the tracker does

- Select a visible Windows application.
- Capture the visible client area.
- Detect standard COCO objects locally with RF-DETR Nano.
- Track detections across frames with ByteTrack.
- Draw transparent click-through boxes and labels.
- Leave mouse and keyboard input alone.

## What it does not do

- No aim control.
- No automated input.
- No game memory reading.
- No hidden/through-wall detection.
- No process injection.

## Core projects

- Roboflow RF-DETR: https://github.com/roboflow/rf-detr
- Roboflow Trackers: https://github.com/roboflow/trackers
