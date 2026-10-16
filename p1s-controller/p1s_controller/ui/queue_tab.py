"""Print queue. Nothing starts by itself: you clear the plate, then press Start next."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from .. import threemf
from ..db import Database
from . import theme
from .bridge import PrinterBridge
from .send_dialog import SendDialog
from .util import fmt_seconds

STATUS_TEXT = {"pending": "Waiting", "sent": "Printing", "done": "Done", "failed": "Failed", "skipped": "Skipped"}
STATUS_COLOR = {"pending": theme.TEXT, "sent": theme.ACCENT, "done": theme.OK, "failed": theme.BAD,
                "skipped": theme.MUTED}


class QueueTab(QWidget):
    message = Signal(str, str)  # title, text: shown as a desktop/phone notification

    def __init__(self, bridge: PrinterBridge, db: Database, parent=None):
        super().__init__(parent)
        self.bridge, self.db = bridge, db
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Job", "Time · filament", "Status"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 380)
        self.table.setColumnWidth(2, 180)
        self.note = QLabel("Add sliced files from the Library. The queue never starts a print on its own: "
                           "clear the plate, then press Start next.")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        self.up = QPushButton("Move up")
        self.down = QPushButton("Move down")
        self.remove = QPushButton("Remove")
        self.clear = QPushButton("Clear finished")
        self.start = QPushButton("Start next…")
        self.start.setObjectName("primary")
        row = QHBoxLayout()
        for b in (self.up, self.down, self.remove, self.clear):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.start)
        lay = QVBoxLayout(self)
        lay.addWidget(self.note)
        lay.addWidget(self.table, 1)
        lay.addLayout(row)
        self.up.clicked.connect(lambda: self._move(-1))
        self.down.clicked.connect(lambda: self._move(1))
        self.remove.clicked.connect(self._remove)
        self.clear.clicked.connect(lambda: (self.db.queue_clear_finished(), self.refresh()))
        self.start.clicked.connect(self.start_next)
        bridge.event.connect(self._on_event)
        bridge.controlChanged.connect(lambda _: self._buttons())
        bridge.connectionChanged.connect(lambda *_: self._buttons())
        self.table.itemSelectionChanged.connect(self._buttons)
        self.refresh()

    def add(self, path: Path, plate: int = 1) -> None:
        name = path.name.removesuffix(".gcode.3mf").removesuffix(".3mf")
        self.db.queue_add(str(path), name, plate)
        self.refresh()

    def refresh(self) -> None:
        rows = self.db.queue_list()
        self.table.setRowCount(len(rows))
        pending = 0
        for i, r in enumerate(rows):
            if r["status"] == "pending":
                pending += 1
            detail = ""
            try:
                info = threemf.read(r["path"])
                detail = f"{fmt_seconds(info.print_seconds)} · {info.weight_grams:.0f} g"
            except Exception:
                detail = "file missing"
            cells = (str(pending) if r["status"] == "pending" else "", r["name"], detail, STATUS_TEXT[r["status"]])
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, r["id"])
                if c == 3:
                    item.setForeground(QColor(STATUS_COLOR[r["status"]]))
                self.table.setItem(i, c, item)
        self._buttons()

    def _selected_id(self) -> int | None:
        items = self.table.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _buttons(self) -> None:
        sel = self._selected_id()
        has_pending = self.db.queue_next() is not None
        self.up.setEnabled(sel is not None)
        self.down.setEnabled(sel is not None)
        self.remove.setEnabled(sel is not None)
        self.start.setEnabled(has_pending and self.db.queue_sent() is None)
        if not self.bridge.connected:
            self.start.setToolTip("Not connected to the printer.")
        elif not self.bridge.allow_control:
            self.start.setToolTip("Tick 'Allow control' first. You will confirm everything again in the next dialog.")
        else:
            self.start.setToolTip("")

    def _move(self, delta: int) -> None:
        sel = self._selected_id()
        if sel is not None:
            self.db.queue_move(sel, delta)
            self.refresh()

    def _remove(self) -> None:
        sel = self._selected_id()
        if sel is not None:
            self.db.queue_remove(sel)
            self.refresh()

    def start_next(self) -> None:
        job = self.db.queue_next()
        if job is None:
            return
        path = Path(job["path"])
        if not path.is_file():
            QMessageBox.warning(self, "File missing", f"{path} no longer exists. Remove it from the queue.")
            return
        dlg = SendDialog(self.bridge, path, self)
        if dlg.exec() and getattr(dlg, "started", False):
            self.db.queue_set_status(job["id"], "sent")
            self.refresh()

    def _on_event(self, event: str, job: str) -> None:
        if event not in ("finished", "failed", "cancelled"):
            return
        sent = self.db.queue_sent()
        if sent is None:
            return
        self.db.queue_set_status(sent["id"], "done" if event == "finished" else "failed")
        self.refresh()
        nxt = self.db.queue_next()
        if nxt is not None:
            self.message.emit("Queue: ready for the next job",
                              f"'{sent['name']}' {event}. Clear the plate, then start '{nxt['name']}'.")
