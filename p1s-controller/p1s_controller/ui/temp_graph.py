from __future__ import annotations

import time
from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import Qt

from . import theme

WINDOW_SECONDS = 600


class TempGraph(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent, background=theme.PANEL)
        self.setMinimumHeight(180)
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setMouseEnabled(False, False)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.getAxis("bottom").setPen(theme.BORDER)
        self.getAxis("left").setPen(theme.BORDER)
        self.getAxis("bottom").setTextPen(theme.MUTED)
        self.getAxis("left").setTextPen(theme.MUTED)
        self.setLabel("bottom", "seconds ago")
        self.addLegend(offset=(10, 5))
        self._data = {k: deque(maxlen=WINDOW_SECONDS) for k in ("t", "nozzle", "bed", "chamber", "nozzle_t", "bed_t")}
        self._curves = {
            "nozzle": self.plot(pen=pg.mkPen(theme.BAD, width=2), name="Nozzle"),
            "bed": self.plot(pen=pg.mkPen(theme.WARN, width=2), name="Bed"),
            "chamber": self.plot(pen=pg.mkPen(theme.ACCENT, width=2), name="Chamber"),
            "nozzle_t": self.plot(pen=pg.mkPen(theme.BAD, width=1, style=Qt.DashLine)),
            "bed_t": self.plot(pen=pg.mkPen(theme.WARN, width=1, style=Qt.DashLine)),
        }
        self._last = 0.0

    def add_sample(self, nozzle: float, bed: float, chamber: float, nozzle_t: float, bed_t: float,
                   now: float | None = None) -> None:
        now = now if now is not None else time.time()
        if now - self._last < 1.0:  # at most one point per second
            return
        self._last = now
        for key, value in zip(("t", "nozzle", "bed", "chamber", "nozzle_t", "bed_t"),
                              (now, nozzle, bed, chamber, nozzle_t, bed_t)):
            self._data[key].append(value)
        xs = [t - now for t in self._data["t"]]
        for key, curve in self._curves.items():
            curve.setData(xs, list(self._data[key]))
        self.setXRange(-WINDOW_SECONDS, 0, padding=0)
