"""Maintenance reminders by printing hours."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import maintenance
from ..db import Database
from . import theme
from .bridge import PrinterBridge


class MaintenanceTab(QWidget):
    message = Signal(str, str)

    def __init__(self, bridge: PrinterBridge, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._warned: set[int] = set()
        self.total = QLabel("")
        self.total.setObjectName("big")
        self.note = QLabel("Hours come from the prints this app has recorded. The intervals are starting points: "
                           "adjust them to how you use the printer and what Bambu's wiki recommends.")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Task", "Interval (h)", "Progress", "Status", ""])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 340)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 200)
        self.name = QLineEdit(placeholderText="New task, e.g. Replace carbon filter")
        self.hours = QDoubleSpinBox()
        self.hours.setRange(1, 5000)
        self.hours.setValue(100)
        self.hours.setSuffix(" h")
        add = QPushButton("Add task")
        row = QHBoxLayout()
        row.addWidget(self.name, 1)
        row.addWidget(self.hours)
        row.addWidget(add)
        lay = QVBoxLayout(self)
        lay.addWidget(self.total)
        lay.addWidget(self.note)
        lay.addWidget(self.table, 1)
        lay.addLayout(row)
        add.clicked.connect(self._add)
        bridge.event.connect(lambda e, _j: e in ("finished", "failed", "cancelled") and self.check())
        self.refresh()

    def refresh(self) -> None:
        stats = maintenance.statuses(self.db)
        self.total.setText(f"{self.db.print_hours():.1f} print hours recorded")
        self.table.setRowCount(len(stats))
        for i, t in enumerate(stats):
            name = QTableWidgetItem(t.name)
            name.setToolTip(t.note)
            self.table.setItem(i, 0, name)
            spin = QDoubleSpinBox()
            spin.setRange(1, 5000)
            spin.setValue(t.interval)
            spin.editingFinished.connect(lambda tid=t.id, s=spin: (self.db.maintenance_set_interval(tid, s.value()),
                                                                   self.refresh()))
            self.table.setCellWidget(i, 1, spin)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(min(100, int(t.fraction * 100)))
            color = theme.BAD if t.overdue else theme.WARN if t.soon else theme.ACCENT
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; border-radius: 6px; }}")
            self.table.setCellWidget(i, 2, bar)
            status = QTableWidgetItem(t.text)
            self.table.setItem(i, 3, status)
            cell = QWidget()
            h = QHBoxLayout(cell)
            h.setContentsMargins(4, 2, 4, 2)
            done = QPushButton("Mark done")
            delete = QPushButton("Delete")
            done.clicked.connect(lambda _=False, tid=t.id: (self.db.maintenance_done(tid), self._warned.discard(tid),
                                                            self.refresh()))
            delete.clicked.connect(lambda _=False, tid=t.id: (self.db.maintenance_delete(tid), self.refresh()))
            h.addWidget(done)
            h.addWidget(delete)
            self.table.setCellWidget(i, 4, cell)
            self.table.setRowHeight(i, 40)

    def check(self) -> None:
        """After each print: refresh and announce tasks that just came due."""
        self.refresh()
        for t in maintenance.due(self.db):
            if t.id not in self._warned:
                self._warned.add(t.id)
                self.message.emit("Maintenance due", f"{t.name}: {t.text.lower()}.")

    def _add(self) -> None:
        if self.name.text().strip():
            self.db.maintenance_add(self.name.text().strip(), self.hours.value())
            self.name.clear()
            self.refresh()
