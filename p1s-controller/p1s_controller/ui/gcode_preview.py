from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from .. import gcode, threemf
from . import theme


class _ParseThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path: Path, plate: int):
        super().__init__()
        self.path, self.plate = path, plate

    def run(self) -> None:
        try:
            self.done.emit(gcode.parse(threemf.read_gcode(self.path, self.plate)))
        except Exception as exc:
            self.failed.emit(str(exc))


class _Canvas(QWidget):
    BED = 256.0  # P1S bed is 256 x 256 mm

    def __init__(self):
        super().__init__()
        self.layers: gcode.GcodeLayers | None = None
        self.current = 0
        self.setMinimumSize(320, 320)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 16
        ox = (self.width() - side) / 2
        oy = (self.height() - side) / 2
        scale = side / self.BED
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QColor(theme.PANEL))
        p.drawRect(QRectF(ox, oy, side, side))
        p.setPen(QPen(QColor(theme.PANEL2), 1))
        for i in range(1, 8):
            off = side * i / 8
            p.drawLine(int(ox + off), int(oy), int(ox + off), int(oy + side))
            p.drawLine(int(ox), int(oy + off), int(ox + side), int(oy + off))
        if not self.layers or not self.layers.layers:
            return

        def to_px(x: float, y: float) -> tuple[float, float]:
            return ox + x * scale, oy + side - y * scale  # G-code Y points up

        for idx in range(max(0, self.current - 3), self.current + 1):
            alpha = 255 if idx == self.current else 70
            p.setPen(QPen(QColor(62, 166, 255, alpha), 1.4 if idx == self.current else 1))
            for x0, y0, x1, y1 in self.layers.layers[idx]:
                ax, ay = to_px(x0, y0)
                bx, by = to_px(x1, y1)
                p.drawLine(int(ax), int(ay), int(bx), int(by))


class GcodePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: _ParseThread | None = None
        self.canvas = _Canvas()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.label = QLabel("Select a file and choose Preview layers")
        self.label.setObjectName("muted")
        row = QHBoxLayout()
        row.addWidget(self.slider, 1)
        row.addWidget(self.label)
        lay = QVBoxLayout(self)
        lay.addWidget(self.canvas, 1)
        lay.addLayout(row)
        self.slider.valueChanged.connect(self._on_slider)

    def load(self, path: Path, plate: int = 1) -> None:
        self.label.setText("Reading G-code…")
        self.slider.setEnabled(False)
        self._thread = _ParseThread(path, plate)
        self._thread.done.connect(self._loaded)
        self._thread.failed.connect(lambda msg: self.label.setText(f"Could not read G-code: {msg}"))
        self._thread.start()

    def set_layers(self, layers: gcode.GcodeLayers) -> None:
        self._loaded(layers)

    def _loaded(self, layers: gcode.GcodeLayers) -> None:
        self.canvas.layers = layers
        n = len(layers.layers)
        self.slider.setEnabled(n > 0)
        self.slider.setRange(0, max(0, n - 1))
        self.slider.setValue(n - 1 if n else 0)
        self._on_slider(self.slider.value())

    def _on_slider(self, value: int) -> None:
        layers = self.canvas.layers
        if not layers or not layers.layers:
            self.label.setText("No extrusion moves found")
            return
        self.canvas.current = value
        height = layers.heights[value] if value < len(layers.heights) else 0
        self.label.setText(f"Layer {value + 1}/{len(layers.layers)}  ·  Z {height:.2f} mm")
        self.canvas.update()
