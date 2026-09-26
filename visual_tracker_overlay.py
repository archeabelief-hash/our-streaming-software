import sys
import time
import ctypes
from dataclasses import dataclass

import cv2
import mss
import numpy as np
import win32gui
from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QSpinBox,
    QDoubleSpinBox, QVBoxLayout, QWidget
)

import supervision as sv
from rfdetr import RFDETRNano
from rfdetr.assets.coco_classes import COCO_CLASSES
from trackers import ByteTrackTracker


# Make Win32 coordinates match physical pixels on scaled displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


@dataclass
class TrackBox:
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    confidence: float
    track_id: int | None


def visible_windows():
    items = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return
        try:
            left, top, right, bottom = get_client_screen_rect(hwnd)
        except Exception:
            return
        if right - left < 80 or bottom - top < 80:
            return
        items.append((title, hwnd))

    win32gui.EnumWindows(callback, None)
    items.sort(key=lambda x: x[0].lower())
    return items


def get_client_screen_rect(hwnd):
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    screen_left, screen_top = win32gui.ClientToScreen(hwnd, (left, top))
    screen_right, screen_bottom = win32gui.ClientToScreen(hwnd, (right, bottom))
    return screen_left, screen_top, screen_right, screen_bottom


def coco_name(class_id: int) -> str:
    if isinstance(COCO_CLASSES, dict):
        return str(COCO_CLASSES.get(class_id, class_id))
    if 0 <= class_id < len(COCO_CLASSES):
        return str(COCO_CLASSES[class_id])
    return str(class_id)


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.boxes: list[TrackBox] = []
        self.show_ids = True
        self.show_conf = True
        self.line_width = 3
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.hide()

    def set_target_rect(self, rect):
        left, top, right, bottom = rect
        self.setGeometry(left, top, max(1, right - left), max(1, bottom - top))

    def update_tracks(self, boxes, rect):
        self.boxes = boxes
        self.set_target_rect(rect)
        if not self.isVisible():
            self.show()
        self.raise_()
        self.update()

    def clear_tracks(self):
        self.boxes = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)

        for box in self.boxes:
            # High-visibility green with a dark shadow edge.
            painter.setPen(QPen(QColor(0, 0, 0, 220), self.line_width + 2))
            painter.drawRect(int(box.x1), int(box.y1),
                             int(box.x2 - box.x1), int(box.y2 - box.y1))
            painter.setPen(QPen(QColor(57, 255, 20, 255), self.line_width))
            painter.drawRect(int(box.x1), int(box.y1),
                             int(box.x2 - box.x1), int(box.y2 - box.y1))

            parts = [box.label]
            if self.show_ids and box.track_id is not None:
                parts.append(f"#{box.track_id}")
            if self.show_conf:
                parts.append(f"{box.confidence:.0%}")
            text = " ".join(parts)

            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(text) + 10
            th = metrics.height() + 6
            tx = int(box.x1)
            ty = max(0, int(box.y1) - th)

            painter.fillRect(tx, ty, tw, th, QColor(0, 0, 0, 190))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(tx + 5, ty + metrics.ascent() + 3, text)


class CaptureWorker(QObject):
    tracks_ready = Signal(object, object, float)
    status = Signal(str)
    finished = Signal()

    def __init__(self, hwnd, threshold, class_filter, max_fps):
        super().__init__()
        self.hwnd = hwnd
        self.threshold = threshold
        self.class_filter = {x.strip().lower() for x in class_filter.split(",") if x.strip()}
        self.max_fps = max(1, int(max_fps))
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        try:
            self.status.emit("Loading RF-DETR Nano locally...")
            model = RFDETRNano()
            tracker = ByteTrackTracker()
            self.status.emit("Tracking started.")

            frame_period = 1.0 / self.max_fps
            last_report = time.perf_counter()
            frames = 0
            fps = 0.0

            with mss.mss() as sct:
                while self.running:
                    loop_start = time.perf_counter()

                    if not win32gui.IsWindow(self.hwnd):
                        self.status.emit("Target window was closed.")
                        break

                    try:
                        rect = get_client_screen_rect(self.hwnd)
                    except Exception:
                        time.sleep(0.05)
                        continue

                    left, top, right, bottom = rect
                    width = right - left
                    height = bottom - top
                    if width <= 1 or height <= 1 or win32gui.IsIconic(self.hwnd):
                        time.sleep(0.1)
                        continue

                    raw = np.asarray(sct.grab({
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height
                    }))

                    # mss returns BGRA. RF-DETR receives RGB PIL input.
                    rgb = cv2.cvtColor(raw, cv2.COLOR_BGRA2RGB)
                    image = Image.fromarray(rgb)

                    detections = model.predict(image, threshold=self.threshold)

                    if self.class_filter and len(detections) > 0:
                        mask = np.array([
                            coco_name(int(cid)).lower() in self.class_filter
                            for cid in detections.class_id
                        ], dtype=bool)
                        detections = detections[mask]

                    if len(detections) > 0:
                        tracked = tracker.update(detections)
                    else:
                        # Keep tracker state advancing when no detections are visible.
                        tracked = tracker.update(sv.Detections.empty())

                    boxes = []
                    if len(tracked) > 0:
                        ids = tracked.tracker_id
                        for i, xyxy in enumerate(tracked.xyxy):
                            cid = int(tracked.class_id[i]) if tracked.class_id is not None else -1
                            conf = float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
                            tid = int(ids[i]) if ids is not None and ids[i] is not None else None
                            boxes.append(TrackBox(
                                float(xyxy[0]), float(xyxy[1]),
                                float(xyxy[2]), float(xyxy[3]),
                                coco_name(cid), conf, tid
                            ))

                    frames += 1
                    now = time.perf_counter()
                    if now - last_report >= 1.0:
                        fps = frames / (now - last_report)
                        frames = 0
                        last_report = now

                    self.tracks_ready.emit(boxes, rect, fps)

                    elapsed = time.perf_counter() - loop_start
                    delay = frame_period - elapsed
                    if delay > 0:
                        time.sleep(delay)

        except Exception as exc:
            self.status.emit(f"ERROR: {type(exc).__name__}: {exc}")
        finally:
            self.finished.emit()


class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Visual Tracker Overlay")
        self.resize(520, 320)

        self.overlay = Overlay()
        self.thread = None
        self.worker = None
        self.windows = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        intro = QLabel(
            "Pick any visible Windows program. The app captures only what is visible "
            "on screen, detects objects locally, tracks them, and draws a click-through overlay."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.window_combo = QComboBox()
        self.refresh_windows()

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_windows)
        row = QHBoxLayout()
        row.addWidget(self.window_combo, 1)
        row.addWidget(refresh)
        form.addRow("Target program:", row)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.05, 0.95)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.45)
        form.addRow("Detection confidence:", self.threshold)

        self.classes = QLineEdit()
        self.classes.setPlaceholderText("blank = all COCO classes; example: person, car")
        form.addRow("Only show classes:", self.classes)

        self.max_fps = QSpinBox()
        self.max_fps.setRange(1, 60)
        self.max_fps.setValue(30)
        form.addRow("Max processing FPS:", self.max_fps)

        self.show_ids = QCheckBox("Show persistent track IDs")
        self.show_ids.setChecked(True)
        self.show_ids.toggled.connect(lambda v: setattr(self.overlay, "show_ids", v))

        self.show_conf = QCheckBox("Show confidence")
        self.show_conf.setChecked(True)
        self.show_conf.toggled.connect(lambda v: setattr(self.overlay, "show_conf", v))

        checks = QHBoxLayout()
        checks.addWidget(self.show_ids)
        checks.addWidget(self.show_conf)
        form.addRow("Overlay labels:", checks)

        root.addLayout(form)

        controls = QHBoxLayout()
        self.start_btn = QPushButton("START VISUAL TRACKING")
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_tracking)
        self.stop_btn.clicked.connect(self.stop_tracking)
        controls.addWidget(self.start_btn, 1)
        controls.addWidget(self.stop_btn)
        root.addLayout(controls)

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        note = QLabel(
            "Visual-only: this program does not read game memory, reveal occluded objects, "
            "move the mouse, press keys, or control another application."
        )
        note.setWordWrap(True)
        root.addWidget(note)

    def refresh_windows(self):
        previous_hwnd = self.current_hwnd()
        self.windows = visible_windows()
        self.window_combo.clear()

        selected = 0
        for i, (title, hwnd) in enumerate(self.windows):
            self.window_combo.addItem(f"{title}  [HWND {hwnd}]")
            if hwnd == previous_hwnd:
                selected = i
        if self.windows:
            self.window_combo.setCurrentIndex(selected)

    def current_hwnd(self):
        idx = self.window_combo.currentIndex()
        if 0 <= idx < len(self.windows):
            return self.windows[idx][1]
        return None

    def start_tracking(self):
        hwnd = self.current_hwnd()
        if hwnd is None:
            self.status_label.setText("No target window selected.")
            return

        self.stop_tracking(wait=True)

        self.thread = QThread()
        self.worker = CaptureWorker(
            hwnd=hwnd,
            threshold=float(self.threshold.value()),
            class_filter=self.classes.text(),
            max_fps=int(self.max_fps.value())
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.tracks_ready.connect(self.on_tracks)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.on_finished)
        self.thread.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_tracking(self, wait=False):
        if self.worker is not None:
            self.worker.stop()
        if wait and self.thread is not None and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(1000)
        self.overlay.hide()

    def on_tracks(self, boxes, rect, fps):
        self.overlay.update_tracks(boxes, rect)
        self.status_label.setText(
            f"Tracking {len(boxes)} object(s) | processing {fps:.1f} FPS"
        )

    def on_finished(self):
        self.overlay.hide()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker = None
        self.thread = None

    def closeEvent(self, event):
        self.stop_tracking(wait=True)
        self.overlay.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = ControlPanel()
    panel.show()
    sys.exit(app.exec())
