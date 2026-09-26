# Universal Visual Tracker Overlay

A **local, visual-only Windows overlay** for improving on-screen visibility while gaming, watching footage, or using other desktop applications.

It captures the visible client area of a selected window, runs **RF-DETR Nano** object detection locally, feeds detections into **Roboflow Trackers / ByteTrack**, and draws transparent click-through boxes above the selected program.

## What it does

- Select almost any visible Windows application from a dropdown.
- Capture the application's visible client area.
- Detect standard COCO objects locally with RF-DETR Nano.
- Track detections across frames with ByteTrack.
- Draw a transparent always-on-top overlay with bounding boxes, class names, confidence, and persistent track IDs.
- Optionally filter to classes such as `person`, `car`, `dog`, etc.
- Leaves mouse and keyboard input alone.

## What it deliberately does not do

- No mouse movement or aim control.
- No key presses.
- No reading another process's memory.
- No hidden/occluded-object or through-wall detection.
- No network inference required after model assets are downloaded.

## Windows install

1. Install **Python 3.11 64-bit**.
2. Download or clone this repository.
3. Double-click `install_windows.bat`.
4. Double-click `run_overlay.bat`.
5. Pick the program/window you want.
6. Click **START VISUAL TRACKING**.

The installer explicitly installs NumPy first to avoid the common `No module named 'numpy'` error. The first RF-DETR run may download model weights.

## Performance

RF-DETR Nano is used because it is the smallest current Apache-2.0 RF-DETR detector. Actual FPS depends heavily on GPU, resolution, and PyTorch acceleration.

If performance is poor:
- set processing FPS to 10-20;
- reduce the target program's window size;
- use a CUDA-enabled PyTorch build if you have a supported NVIDIA GPU;
- filter to the classes you actually want to see.

## Important limitation

The stock RF-DETR model is trained on the COCO object classes. It can identify things like people, cars, bicycles, animals, bags, bottles, chairs, monitors, etc., but it does **not automatically know game-specific concepts** like "enemy player", "loot", "boss", "ore", or "quest NPC".

For those, the architecture is already suitable, but you need a custom/fine-tuned detector trained on screenshots from the target game.

## Core projects

- Roboflow RF-DETR: https://github.com/roboflow/rf-detr
- Roboflow Trackers: https://github.com/roboflow/trackers

Both support the local Python workflow used here.
