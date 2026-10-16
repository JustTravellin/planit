from __future__ import annotations

import time

from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ..db import Database
from .bridge import PrinterBridge
from .util import fmt_seconds


class HistoryTab(QWidget):
    def __init__(self, bridge: PrinterBridge, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.stats = QLabel("")
        self.stats.setObjectName("big")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Started", "Name", "Result", "Duration", "Filament"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay = QVBoxLayout(self)
        lay.addWidget(self.stats)
        lay.addWidget(self.table, 1)
        bridge.event.connect(lambda *_: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        s = self.db.stats()
        rate = f"{s['success_rate'] * 100:.0f}% success" if s["success_rate"] is not None else "no prints yet"
        self.stats.setText(f"{s['total']} prints · {fmt_seconds(s['seconds'])} · {s['grams']:.0f} g · {rate}")
        rows = self.db.list_prints()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            values = [
                time.strftime("%Y-%m-%d %H:%M", time.localtime(r["started_at"])),
                r["name"],
                r["result"] or "running",
                fmt_seconds(r["seconds"]) if r["seconds"] else "",
                f"{r['filament_g']:.1f} g" if r["filament_g"] else "",
            ]
            for c, v in enumerate(values):
                self.table.setItem(i, c, QTableWidgetItem(v))
