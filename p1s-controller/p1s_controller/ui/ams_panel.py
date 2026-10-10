from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..state import AmsTray
from . import theme


class SlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray: AmsTray | None = None
        self.active = False
        self.setMinimumSize(96, 120)

    def set_tray(self, tray: AmsTray | None, active: bool) -> None:
        self.tray, self.active = tray, active
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(QColor(theme.PANEL2))
        p.setPen(QPen(QColor(theme.ACCENT if self.active else theme.BORDER), 2 if self.active else 1))
        p.drawRoundedRect(r, 8, 8)
        t = self.tray
        if t is None or t.empty:
            p.setPen(QColor(theme.MUTED))
            p.drawText(r, Qt.AlignCenter, "Empty")
            return
        # spool disc
        d = min(r.width() - 24, 52)
        disc = QRectF(r.center().x() - d / 2, r.top() + 12, d, d)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QColor("#" + (t.color or "808080")))
        p.drawEllipse(disc)
        p.setBrush(QColor(theme.PANEL2))
        hole = d * 0.28
        p.drawEllipse(disc.center(), hole / 2, hole / 2)
        # text
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(r.left(), disc.bottom() + 6, r.width(), 18), Qt.AlignCenter, t.material)
        # remaining bar
        bar = QRectF(r.left() + 12, r.bottom() - 22, r.width() - 24, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.BG))
        p.drawRoundedRect(bar, 3, 3)
        if t.remain >= 0:
            fill = QRectF(bar.left(), bar.top(), bar.width() * min(t.remain, 100) / 100, bar.height())
            p.setBrush(QColor(theme.OK if t.remain > 20 else theme.WARN))
            p.drawRoundedRect(fill, 3, 3)
            p.setPen(QColor(theme.MUTED))
            p.setFont(self.font())
            p.drawText(QRectF(r.left(), bar.bottom() + 1, r.width(), 14), Qt.AlignCenter, f"{t.remain}%")


class AmsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._rows: dict[int, list[SlotWidget]] = {}
        self._placeholder = QLabel("No AMS data yet")
        self._placeholder.setObjectName("muted")
        self._layout.addWidget(self._placeholder)

    def update_trays(self, trays: list[AmsTray], active: int | None) -> None:
        if trays:
            self._placeholder.hide()
        for unit_id in sorted({t.ams_id for t in trays}):
            if unit_id not in self._rows:
                row = QHBoxLayout()
                label = QLabel(f"AMS {unit_id + 1}")
                label.setObjectName("muted")
                label.setFixedWidth(46)
                row.addWidget(label)
                widgets = [SlotWidget() for _ in range(4)]
                for w in widgets:
                    row.addWidget(w)
                self._layout.addLayout(row)
                self._rows[unit_id] = widgets
        for t in trays:
            widgets = self._rows.get(t.ams_id)
            if widgets and 0 <= t.slot < 4:
                widgets[t.slot].set_tray(t, t.global_index == active)
