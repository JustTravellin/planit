"""Plate preview: 3D model on the build plate, sliced toolpath with a layer slider, and a fit check."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QLabel, QPushButton, QSlider, QStackedLayout, QVBoxLayout,
                               QWidget)

from .. import gcode, plate, threemf
from . import theme, viewport


class _LoadThread(QThread):
    done = Signal(object, object)  # meshes, GcodeLayers | None
    failed = Signal(str)

    def __init__(self, path: Path, plate_no: int, sliced: bool):
        super().__init__()
        self.path, self.plate_no, self.sliced = path, plate_no, sliced

    def run(self) -> None:
        try:
            try:
                meshes = threemf.read_meshes(self.path, self.plate_no)
            except Exception:  # no mesh data is fine, the toolpath still shows
                meshes = []
            layers = gcode.parse(threemf.read_gcode(self.path, self.plate_no)) if self.sliced else None
            self.done.emit(meshes, layers)
        except Exception as exc:
            self.failed.emit(str(exc))


class _Canvas(QWidget):
    """2D top-down fallback used when OpenGL isn't available."""
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
        p.setBrush(QColor(theme.PLATE))
        p.drawRect(QRectF(ox, oy, side, side))
        p.setPen(QPen(QColor(theme.GRID), 1))
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
            p.setPen(QPen(QColor(0, 174, 66, alpha), 1.4 if idx == self.current else 1))
            for x0, y0, x1, y1 in self.layers.layers[idx]:
                ax, ay = to_px(x0, y0)
                bx, by = to_px(x1, y1)
                p.drawLine(int(ax), int(ay), int(bx), int(by))


class PlatePreview(QWidget):
    fitUpdated = Signal(object)  # plate.FitReport | None

    def __init__(self, parent=None, use_gl: bool | None = None):
        super().__init__(parent)
        self._thread: _LoadThread | None = None
        self.layers: gcode.GcodeLayers | None = None
        self.meshes: list[threemf.Mesh] = []
        self.fit: plate.FitReport | None = None
        self.bed, self.height = (256.0, 256.0), 256.0
        self.colors: list[str] = []
        self.use_gl = viewport.AVAILABLE if use_gl is None else use_gl and viewport.AVAILABLE
        self.canvas = _Canvas()  # fallback and test surface; layers kept in sync
        self.gl = viewport.Viewport3D() if self.use_gl else None

        self.slider = QSlider(Qt.Vertical)
        self.slider.setInvertedAppearance(False)
        self.slider.setEnabled(False)
        self.label = QLabel("Select a file")
        self.label.setObjectName("muted")
        self.fit_label = QLabel("")
        self.fit_label.setTextFormat(Qt.RichText)

        # toolbar: camera presets on the left, model/sliced toggle on the right
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.view_buttons: dict[str, QPushButton] = {}
        for key, text in (("iso", "Iso"), ("top", "Top"), ("front", "Front"), ("left", "Left"), ("right", "Right")):
            b = QPushButton(text)
            b.setObjectName("tool")
            b.clicked.connect(lambda _=False, k=key: self.gl and self.gl.view(k))
            self.view_buttons[key] = b
            bar.addWidget(b)
        fit = QPushButton("Fit")
        fit.setObjectName("tool")
        fit.clicked.connect(self._frame)
        bar.addWidget(fit)
        bar.addStretch(1)
        self.model_btn = QPushButton("Model")
        self.sliced_btn = QPushButton("Sliced")
        for b in (self.model_btn, self.sliced_btn):
            b.setCheckable(True)
            b.setObjectName("seg")
            bar.addWidget(b)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.model_btn)
        group.addButton(self.sliced_btn)
        self.model_btn.setChecked(True)
        self.model_btn.clicked.connect(lambda: self._set_mode(False))
        self.sliced_btn.clicked.connect(lambda: self._set_mode(True))
        if not self.use_gl:
            for b in self.view_buttons.values():
                b.hide()
            fit.hide()

        stage = QHBoxLayout()
        view_host = QWidget()
        stack = QStackedLayout(view_host)
        stack.addWidget(self.gl if self.gl else self.canvas)
        stage.addWidget(view_host, 1)
        stage.addWidget(self.slider)

        foot = QHBoxLayout()
        foot.addWidget(self.fit_label, 1)
        foot.addWidget(self.label)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(bar)
        lay.addLayout(stage, 1)
        lay.addLayout(foot)
        self.slider.valueChanged.connect(self._on_slider)
        self._set_mode(False)

    # ---- loading
    def load(self, path: Path, plate_no: int = 1, sliced: bool = True) -> None:
        self.label.setText("Reading file…")
        self.slider.setEnabled(False)
        self._thread = _LoadThread(path, plate_no, sliced)
        self._thread.done.connect(self._loaded)
        self._thread.failed.connect(lambda msg: self.label.setText(f"Could not read file: {msg}"))
        self._thread.start()

    def wait(self) -> None:
        if self._thread:
            self._thread.wait()
            QApplication.processEvents()

    def set_bed(self, bed: tuple[float, float], height: float) -> None:
        self.bed, self.height = bed, height
        self.canvas.BED = max(bed)
        if self.gl:
            self.gl.set_bed(bed[0], bed[1], height)

    def _loaded(self, meshes, layers) -> None:
        self.set_meshes(meshes, self.colors)
        if layers is not None:
            self.set_layers(layers)
        self._update_fit()
        self._set_mode(layers is not None and not meshes)

    def set_meshes(self, meshes: list[threemf.Mesh], colors: list[str] | None = None) -> None:
        self.meshes = meshes
        if self.gl:
            self.gl.set_meshes(meshes, colors)
        self._update_fit()

    def set_layers(self, layers: gcode.GcodeLayers) -> None:
        self.layers = layers
        self.canvas.layers = layers
        n = len(layers.layers)
        self.sliced_btn.setEnabled(n > 0)
        if self.gl and n:
            self.gl.set_toolpath(layers)
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, n - 1))
        self.slider.setValue(max(0, n - 1))
        self.slider.blockSignals(False)
        self._on_slider(self.slider.value())

    def clear(self) -> None:
        self.layers, self.meshes, self.fit = None, [], None
        self.canvas.layers = None
        if self.gl:
            self.gl.clear_model()
        self.sliced_btn.setEnabled(False)
        self.slider.setEnabled(False)
        self.fit_label.setText("")
        self.label.setText("")
        self._set_mode(False)
        self.canvas.update()

    # ---- fit check
    def _update_fit(self) -> None:
        arrays = [m.verts for m in self.meshes]
        if not arrays and self.layers and self.layers.layers:
            lx0, ly0, lx1, ly1 = self.layers.bounds
            import numpy as np
            arrays = [np.array([[lx0, ly0, 0], [lx1, ly1, max(self.layers.heights or [0])]])]
        b = plate.bounds_of(arrays)
        if b is None:
            self.fit, text = None, ""
        else:
            self.fit = plate.fit_report(*b, bed=self.bed, height=self.height)
            x, y, z = self.fit.size
            m = self.fit.margins
            dims = f"{x:.1f} × {y:.1f} × {z:.1f} mm"
            if self.fit.fits:
                text = (f"<span style='color:{theme.OK}'>✔ Fits the plate</span> · {dims}"
                        f" · <span style='color:{theme.MUTED}'>edge gaps L {m['left']:.0f} R {m['right']:.0f} "
                        f"F {m['front']:.0f} B {m['back']:.0f} mm</span>")
            else:
                text = (f"<span style='color:{theme.BAD}'>✖ Does not fit: {'; '.join(self.fit.issues)}</span>"
                        f" · {dims}")
        self.fit_label.setText(text)
        self.fitUpdated.emit(self.fit)
        self._frame()

    def _frame(self) -> None:
        if self.gl and self.fit:
            self.gl.frame(self.fit.lo, self.fit.hi)

    # ---- view state
    def _set_mode(self, sliced: bool) -> None:
        sliced = sliced and self.layers is not None and bool(self.layers.layers)
        self.sliced_btn.setChecked(sliced)
        self.model_btn.setChecked(not sliced)
        self.slider.setEnabled(sliced)
        self.slider.setVisible(sliced)
        if self.gl:
            self.gl.show_model(not sliced)
        if not sliced and self.meshes:
            self.label.setText(f"{len(self.meshes)} object{'s' if len(self.meshes) != 1 else ''} on plate")
        elif sliced:
            self._on_slider(self.slider.value())

    def _on_slider(self, value: int) -> None:
        layers = self.layers
        if not layers or not layers.layers:
            self.label.setText("No extrusion moves found")
            return
        self.canvas.current = value
        if self.gl:
            self.gl.set_layer(value)
        height = layers.heights[value] if value < len(layers.heights) else 0
        self.label.setText(f"Layer {value + 1}/{len(layers.layers)}  ·  Z {height:.2f} mm")
        self.canvas.update()


GcodePreview = PlatePreview  # old name
