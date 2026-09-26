import sys
import time
import ctypes
from dataclasses import dataclass

import cv2
import mss
import numpy as np
import win32gui
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

try:
    import dxcam
except Exception:
    dxcam = None

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


def get_client_screen_rect(hwnd):
    l, t, r, b = win32gui.GetClientRect(hwnd)
    l, t = win32gui.ClientToScreen(hwnd, (l, t))
    r, b = win32gui.ClientToScreen(hwnd, (r, b))
    return l, t, r, b


def visible_windows():
    items = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return
        try:
            l, t, r, b = get_client_screen_rect(hwnd)
            if r - l >= 80 and b - t >= 80:
                items.append((title, hwnd))
        except Exception:
            pass

    win32gui.EnumWindows(callback, None)
    return sorted(items, key=lambda x: x[0].lower())


def coco_name(class_id):
    if isinstance(COCO_CLASSES, dict):
        return str(COCO_CLASSES.get(class_id, class_id))
    if 0 <= class_id < len(COCO_CLASSES):
        return str(COCO_CLASSES[class_id])
    return str(class_id)


def offset_detections(det, xoff, yoff):
    if det is None or len(det) == 0:
        return sv.Detections.empty()
    det.xyxy = det.xyxy.astype(np.float32, copy=True)
    det.xyxy[:, [0, 2]] += xoff
    det.xyxy[:, [1, 3]] += yoff
    return det


def merge_detections(items):
    valid = [d for d in items if d is not None and len(d) > 0]
    if not valid:
        return sv.Detections.empty()

    xyxy = np.concatenate([d.xyxy for d in valid], axis=0)
    conf_parts = []
    cls_parts = []
    for d in valid:
        conf_parts.append(
            d.confidence if d.confidence is not None else np.ones(len(d), dtype=np.float32)
        )
        cls_parts.append(
            d.class_id if d.class_id is not None else np.full(len(d), -1, dtype=int)
        )
    return sv.Detections(
        xyxy=xyxy,
        confidence=np.concatenate(conf_parts),
        class_id=np.concatenate(cls_parts),
    )


def classwise_nms(det, iou_threshold=0.55):
    if det is None or len(det) <= 1:
        return det

    boxes = det.xyxy.astype(np.float32)
    scores = det.confidence if det.confidence is not None else np.ones(len(det))
    classes = det.class_id if det.class_id is not None else np.zeros(len(det), dtype=int)

    keep = []
    for cls in np.unique(classes):
        idxs = np.where(classes == cls)[0]
        order = idxs[np.argsort(scores[idxs])[::-1]]

        while len(order):
            i = order[0]
            keep.append(i)
            if len(order) == 1:
                break

            rest = order[1:]
            xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
            yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
            xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
            yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])

            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
            area_r = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
            iou = inter / np.maximum(area_i + area_r - inter, 1e-6)
            order = rest[iou < iou_threshold]

    keep = np.array(sorted(keep), dtype=int)
    return det[keep]


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.boxes = []
        self.show_ids = True
        self.show_conf = False
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

    def update_tracks(self, boxes, rect):
        self.boxes = boxes
        l, t, r, b = rect
        self.setGeometry(l, t, max(1, r-l), max(1, b-t))
        if not self.isVisible():
            self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)

        for box in self.boxes:
            x, y = int(box.x1), int(box.y1)
            w, h = int(box.x2-box.x1), int(box.y2-box.y1)

            painter.setPen(QPen(QColor(0, 0, 0, 220), self.line_width + 2))
            painter.drawRect(x, y, w, h)
            painter.setPen(QPen(QColor(57, 255, 20, 255), self.line_width))
            painter.drawRect(x, y, w, h)

            parts = [box.label]
            if self.show_ids and box.track_id is not None and box.track_id >= 0:
                parts.append(f"#{box.track_id}")
            if self.show_conf:
                parts.append(f"{box.confidence:.0%}")
            text = " ".join(parts)

            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(text) + 10
            th = metrics.height() + 6
            ty = max(0, y - th)
            painter.fillRect(x, ty, tw, th, QColor(0, 0, 0, 190))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(x + 5, ty + metrics.ascent() + 3, text)


class CaptureWorker(QObject):
    tracks_ready = Signal(object, object, float, str)
    status = Signal(str)
    finished = Signal()

    def __init__(self, hwnd, threshold, class_filter, max_fps, mode):
        super().__init__()
        self.hwnd = hwnd
        self.threshold = threshold
        self.class_filter = {x.strip().lower() for x in class_filter.split(",") if x.strip()}
        self.max_fps = max(1, int(max_fps))
        self.mode = mode
        self.running = True

    def stop(self):
        self.running = False

    def detect(self, model, rgb):
        return model.predict(rgb, threshold=self.threshold)

    def filter_classes(self, detections):
        if self.class_filter and len(detections) > 0:
            mask = np.array([
                coco_name(int(cid)).lower() in self.class_filter
                for cid in detections.class_id
            ], dtype=bool)
            return detections[mask]
        return detections

    def zoom_tile(self, frame, tile_index):
        h, w = frame.shape[:2]
        overlap = 0.10
        tw = int(w * 0.55)
        th = int(h * 0.55)

        positions = [
            (0, 0),
            (max(0, w - tw), 0),
            (0, max(0, h - th)),
            (max(0, w - tw), max(0, h - th)),
        ]
        x0, y0 = positions[tile_index % 4]
        x1, y1 = min(w, x0 + tw), min(h, y0 + th)
        return frame[y0:y1, x0:x1], x0, y0

    def run(self):
        camera = None
        sct = None
        try:
            self.status.emit("Loading RF-DETR Nano...")
            model = RFDETRNano()

            # Fast acquisition: confirm a track on its first valid frame and permit
            # lower-confidence distant/small detections to establish tracks.
            tracker = ByteTrackTracker(
                track_activation_threshold=max(0.15, self.threshold),
                high_conf_det_threshold=max(0.15, self.threshold),
                minimum_consecutive_frames=1,
                lost_track_buffer=30,
                frame_rate=float(self.max_fps),
            )

            capture_name = "MSS"
            if dxcam is not None:
                try:
                    camera = dxcam.create(output_color="RGB")
                    capture_name = "DXGI"
                except Exception:
                    camera = None

            if camera is None:
                sct = mss.mss()

            self.status.emit(f"Tracking started | {capture_name} capture")
            frame_period = 1.0 / self.max_fps
            last_report = time.perf_counter()
            frames = 0
            fps = 0.0
            frame_index = 0

            while self.running:
                loop_start = time.perf_counter()

                if not win32gui.IsWindow(self.hwnd):
                    self.status.emit("Target window closed.")
                    break

                try:
                    rect = get_client_screen_rect(self.hwnd)
                except Exception:
                    time.sleep(0.02)
                    continue

                left, top, right, bottom = rect
                width, height = right-left, bottom-top
                if width <= 1 or height <= 1 or win32gui.IsIconic(self.hwnd):
                    time.sleep(0.05)
                    continue

                if camera is not None:
                    rgb = camera.grab(region=(left, top, right, bottom))
                    if rgb is None:
                        time.sleep(0.001)
                        continue
                else:
                    raw = np.asarray(sct.grab({
                        "left": left, "top": top,
                        "width": width, "height": height
                    }))
                    rgb = cv2.cvtColor(raw, cv2.COLOR_BGRA2RGB)

                passes = []

                # Full-frame pass provides immediate acquisition anywhere on screen.
                passes.append(self.detect(model, rgb))

                # A rotating zoomed crop makes small/far visible objects much larger
                # to the detector while limiting each frame to one extra inference.
                do_zoom = (
                    self.mode == "Long Range" or
                    (self.mode == "Balanced" and frame_index % 2 == 0)
                )
                if do_zoom:
                    tile, xoff, yoff = self.zoom_tile(rgb, frame_index)
                    tile_det = self.detect(model, tile)
                    passes.append(offset_detections(tile_det, xoff, yoff))

                detections = classwise_nms(merge_detections(passes), 0.55)
                detections = self.filter_classes(detections)

                now = time.perf_counter()
                tracked = tracker.update(
                    detections if len(detections) else sv.Detections.empty(),
                    timestamp=now
                )

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
                frame_index += 1
                if now - last_report >= 1.0:
                    fps = frames / (now - last_report)
                    frames = 0
                    last_report = now

                self.tracks_ready.emit(boxes, rect, fps, capture_name)

                delay = frame_period - (time.perf_counter() - loop_start)
                if delay > 0:
                    time.sleep(delay)

        except Exception as exc:
            self.status.emit(f"ERROR: {type(exc).__name__}: {exc}")
        finally:
            if sct is not None:
                try:
                    sct.close()
                except Exception:
                    pass
            self.finished.emit()


class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Visual Tracker Overlay - Low Latency")
        self.resize(560, 390)

        self.overlay = Overlay()
        self.thread = None
        self.worker = None
        self.windows = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        intro = QLabel(
            "Low-latency local visual tracking. Long Range mode adds one rotating "
            "zoom pass per frame to improve acquisition of smaller, farther visible objects."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()

        self.window_combo = QComboBox()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_windows)
        row = QHBoxLayout()
        row.addWidget(self.window_combo, 1)
        row.addWidget(refresh)
        form.addRow("Target program:", row)

        self.mode = QComboBox()
        self.mode.addItems(["Fast", "Balanced", "Long Range"])
        self.mode.setCurrentText("Long Range")
        form.addRow("Tracking mode:", self.mode)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.10, 0.90)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.25)
        form.addRow("Acquisition confidence:", self.threshold)

        self.classes = QLineEdit()
        self.classes.setPlaceholderText("blank = all classes; e.g. person")
        form.addRow("Only show classes:", self.classes)

        self.max_fps = QSpinBox()
        self.max_fps.setRange(1, 120)
        self.max_fps.setValue(60)
        form.addRow("Target processing FPS:", self.max_fps)

        self.show_ids = QCheckBox("Show track IDs")
        self.show_ids.setChecked(True)
        self.show_ids.toggled.connect(lambda v: setattr(self.overlay, "show_ids", v))

        self.show_conf = QCheckBox("Show confidence")
        self.show_conf.setChecked(False)
        self.show_conf.toggled.connect(lambda v: setattr(self.overlay, "show_conf", v))

        opts = QHBoxLayout()
        opts.addWidget(self.show_ids)
        opts.addWidget(self.show_conf)
        form.addRow("Display:", opts)
        root.addLayout(form)

        controls = QHBoxLayout()
        self.start_btn = QPushButton("START REAL-TIME TRACKING")
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
            "Fast = lowest latency. Balanced = zoom scan every other frame. "
            "Long Range = full-frame + zoom scan every frame. Detection remains visual-only."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.refresh_windows()

    def refresh_windows(self):
        previous = self.current_hwnd()
        self.windows = visible_windows()
        self.window_combo.clear()
        selected = 0
        for i, (title, hwnd) in enumerate(self.windows):
            self.window_combo.addItem(f"{title}  [HWND {hwnd}]")
            if hwnd == previous:
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
            max_fps=int(self.max_fps.value()),
            mode=self.mode.currentText(),
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
            self.thread.wait(1500)
        self.overlay.hide()

    def on_tracks(self, boxes, rect, fps, capture_name):
        self.overlay.update_tracks(boxes, rect)
        self.status_label.setText(
            f"{self.mode.currentText()} | {capture_name} | "
            f"{len(boxes)} tracked | {fps:.1f} processing FPS"
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
