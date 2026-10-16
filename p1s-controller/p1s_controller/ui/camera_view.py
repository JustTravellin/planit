from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from ..camera import CameraClient
from .bridge import PrinterBridge


class _CameraThread(QThread):
    frame = Signal(bytes)
    failed = Signal(str)

    def __init__(self, ip: str, code: str):
        super().__init__()
        self.client = CameraClient(ip, code, self.frame.emit)

    def run(self) -> None:
        try:
            self.client.run()
        except Exception as exc:  # network or protocol failure: report, don't crash
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def stop(self) -> None:
        self.client.stop()
        self.wait(3000)


class CameraView(QWidget):
    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._thread: _CameraThread | None = None
        self._last: QPixmap | None = None
        self.image = QLabel("Camera is off")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(320, 180)
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image.setObjectName("muted")
        self.image.setWordWrap(True)
        self.button = QPushButton("Start camera")
        self.snapshot = QPushButton("Save snapshot…")
        self.snapshot.setEnabled(False)
        row = QHBoxLayout()
        row.addWidget(self.button)
        row.addWidget(self.snapshot)
        row.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.image, 1)
        lay.addLayout(row)
        self.button.clicked.connect(self.toggle)
        self.snapshot.clicked.connect(self._save)
        bridge.connectionChanged.connect(self._on_connection)
        self._refresh()

    @property
    def running(self) -> bool:
        return self._thread is not None

    def _refresh(self) -> None:
        self.button.setText("Stop camera" if self.running else "Start camera")
        self.button.setEnabled(self.running or self.bridge.connected)

    def _on_connection(self, ok: bool, _msg: str) -> None:
        if not ok and self.running:
            self.stop()
        self._refresh()

    def toggle(self) -> None:
        self.stop() if self.running else self.start()

    def start(self) -> None:
        cfg = self.bridge.config
        if cfg is None:
            return
        self.image.setText("Connecting to camera…")
        self._thread = _CameraThread(cfg.ip, cfg.access_code)
        self._thread.frame.connect(self._show_frame)
        self._thread.failed.connect(self._failed)
        self._thread.start()
        self._refresh()

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread = None
        self.image.setText("Camera is off")
        self.image.setPixmap(QPixmap())
        self._refresh()

    def _failed(self, message: str) -> None:
        self._thread = None
        self.image.setPixmap(QPixmap())
        self.image.setText(f"Camera stopped: {message}\nThe P1S camera protocol is unofficial; "
                           "check that the camera is enabled in the printer's settings.")
        self._refresh()

    def _show_frame(self, data: bytes) -> None:
        img = QImage.fromData(data, "JPEG")
        if img.isNull():
            return
        self._last = QPixmap.fromImage(img)
        self.snapshot.setEnabled(True)
        self.image.setPixmap(self._last.scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._last is not None and self.running:
            self.image.setPixmap(self._last.scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _save(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        if self._last is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save snapshot", "snapshot.png", "PNG (*.png)")
        if path:
            self._last.save(path, "PNG")
