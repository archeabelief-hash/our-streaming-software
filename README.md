# Universal Visual Tracker Overlay

A local, visual-only Windows overlay for improving on-screen visibility while gaming or using other desktop applications.

## ONE-CLICK WINDOWS INSTALL

Download/extract the repository, then double-click:

`INSTALL.bat`

This installer avoids PowerShell ExecutionPolicy bypasses and does not disable or modify Windows Defender.

It automatically:

1. Checks for Python 3.11.
2. Uses Windows Package Manager (`winget`) to install Python 3.11 if needed.
3. Creates a private `.venv`.
4. Installs NumPy.
5. Installs RF-DETR, Trackers/ByteTrack, DXGI screen capture, PySide6, and the remaining dependencies.
6. Launches the tracker.

After installation, use:

`START_TRACKER.bat`

If you already installed an older version, run `INSTALL.bat` again once so it installs the new `dxcam` dependency.

## Real-time modes

The current build has three modes:

- **Fast** — one full-frame detection pass per cycle for the lowest latency.
- **Balanced** — full-frame detection plus a rotating zoom scan every other cycle.
- **Long Range** — full-frame detection plus one rotating zoomed tile every cycle. This gives smaller/farther visible objects more pixels for the detector while avoiding four tile passes every frame.

The default is **Long Range**, with:
- target processing rate: 60 FPS;
- acquisition threshold: 0.25;
- first-frame track confirmation.

Actual FPS depends on your GPU/CPU and game resolution.

## Faster acquisition

ByteTrack is configured to confirm tracks after a single valid detection frame instead of waiting for multiple consecutive frames. The detection threshold is also lower than the original build, making smaller/weak detections easier to acquire.

A lower threshold can create more false positives. Raise it toward 0.35-0.45 if needed.

## Farther visible-object detection

Long Range mode uses a rotating overlapping 2x2 zoom scan. Each cycle still sees the whole application, while one section is also processed as a larger crop. This improves the detector's opportunity to see small visible objects at distance.

This does not reveal objects that are hidden, occluded, or absent from the visible pixels.

## Screen capture

The program now attempts to use **DXGI Desktop Duplication** through `dxcam` for lower-latency Windows capture. If DXGI capture is unavailable, it automatically falls back to `mss`.

## Security

The installer does **not**:
- disable Microsoft Defender;
- add antivirus exclusions;
- use PowerShell ExecutionPolicy bypass;
- modify another process;
- inject code into games;
- read game memory;
- download arbitrary executables from unknown sites.

## What the tracker does

- Select a visible Windows application.
- Capture only the visible screen pixels.
- Detect standard COCO objects locally using RF-DETR Nano.
- Track detections using ByteTrack.
- Draw transparent click-through boxes and labels.
- Leave mouse and keyboard input alone.

## What it does not do

- No aim control.
- No automated input.
- No game-memory reading.
- No hidden/through-wall detection.
- No process injection.

## Core projects

- Roboflow RF-DETR: https://github.com/roboflow/rf-detr
- Roboflow Trackers: https://github.com/roboflow/trackers
