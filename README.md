# Universal Visual Tracker Overlay

A local, visual-only Windows overlay for improving on-screen visibility while gaming or using other desktop applications.

## ONE-CLICK WINDOWS INSTALL

Download the repository and double-click:

`ONE_CLICK_INSTALL.bat`

That single file will automatically:

1. Check for Python 3.11.
2. Install Python 3.11 with Windows Package Manager if it is missing.
3. Create the private `.venv` environment.
4. Install NumPy first to prevent the common missing-NumPy error.
5. Install RF-DETR, ByteTrack/Trackers, PySide6, screen capture, and the remaining dependencies.
6. Create a desktop shortcut named **Universal Visual Tracker Overlay**.
7. Launch the program when setup finishes.

After the first installation, just use the desktop shortcut or double-click:

`START_TRACKER.bat`

## What it does

- Select almost any visible Windows application from a dropdown.
- Capture the visible client area of that application.
- Detect standard COCO objects locally using RF-DETR Nano.
- Track detected objects across frames using ByteTrack.
- Draw a transparent, click-through overlay with boxes, class labels, confidence, and persistent tracking IDs.
- Optionally filter to specific classes such as `person`, `car`, `dog`, etc.
- Leaves mouse and keyboard input alone.

## What it does not do

- No mouse movement or aim control.
- No automated key presses.
- No game-process memory reading.
- No hidden or through-wall object detection.
- No control over the selected application.

## Requirements

- Windows 10 or Windows 11
- Internet connection for the first installation and initial model download
- Windows Package Manager (`winget`) if Python 3.11 is not already installed

Most current Windows 10/11 systems already include `winget` through Microsoft's **App Installer** package.

## Performance

RF-DETR Nano is used because it is the smallest current Apache-2.0 RF-DETR detector.

For better speed:
- use 10-20 processing FPS on slower systems;
- reduce the game's window resolution;
- filter to only the classes you need;
- use CUDA-enabled PyTorch on a supported NVIDIA GPU.

## Game-specific detection

The stock RF-DETR model understands standard COCO objects such as people, cars, animals, bottles, backpacks, chairs, and monitors.

It does not automatically understand game-specific concepts such as:
- enemy
- teammate
- loot
- boss
- ore
- quest NPC
- dropped weapon

Those require a detector trained or fine-tuned on screenshots from the specific game.

## Core projects

- Roboflow RF-DETR: https://github.com/roboflow/rf-detr
- Roboflow Trackers: https://github.com/roboflow/trackers
