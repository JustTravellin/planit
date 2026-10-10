from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..db import Database
from .bridge import PrinterBridge


class AddSpoolDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add spool")
        self.name = QLineEdit()
        self.material = QComboBox(editable=True)
        self.material.addItems(["PLA", "PETG", "ABS", "ASA", "TPU", "PA", "PC"])
        self.brand = QLineEdit()
        self.color = "FFFFFF"
        self.color_btn = QPushButton("Pick colour")
        self.color_btn.clicked.connect(self._pick)
        self.weight = QDoubleSpinBox(); self.weight.setRange(1, 10000); self.weight.setValue(1000); self.weight.setSuffix(" g")
        form = QFormLayout(self)
        form.addRow("Name", self.name); form.addRow("Material", self.material)
        form.addRow("Brand", self.brand); form.addRow("Colour", self.color_btn); form.addRow("Weight", self.weight)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        form.addRow(box)

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor("#" + self.color), self)
        if c.isValid():
            self.color = c.name()[1:].upper()
            self.color_btn.setStyleSheet(f"background: #{self.color}; color: black;")


class FilamentTab(QWidget):
    """Spool inventory. Spools assigned to an AMS slot are drawn down when a print started here finishes."""

    def __init__(self, bridge: PrinterBridge, db: Database, parent=None):
        super().__init__(parent)
        self.bridge, self.db = bridge, db
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Spool", "Material", "Remaining (g)", "Of (g)", "AMS slot"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        add, remove = QPushButton("Add spool…"), QPushButton("Remove selected")
        row = QHBoxLayout()
        row.addWidget(add); row.addWidget(remove); row.addStretch(1)
        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self.table, 1)
        add.clicked.connect(self._add)
        remove.clicked.connect(self._remove)
        bridge.event.connect(lambda *_: self.refresh())
        self.refresh()

    def _slot_options(self) -> list[tuple[str, int | None]]:
        options: list[tuple[str, int | None]] = [("—", None)]
        for t in self.bridge.state.ams_trays:
            options.append((f"AMS{t.ams_id + 1} slot {t.slot + 1}", t.global_index))
        if len(options) == 1:  # not connected yet: offer the standard 4 slots
            options += [(f"AMS1 slot {i + 1}", i) for i in range(4)]
        return options

    def refresh(self) -> None:
        spools = self.db.list_spools()
        self.table.setRowCount(len(spools))
        for r, s in enumerate(spools):
            name = QTableWidgetItem(f"●  {s.name}")
            name.setForeground(QColor("#" + (s.color or "808080")))
            name.setData(0x100, s.id)  # Qt.UserRole
            self.table.setItem(r, 0, name)
            self.table.setItem(r, 1, QTableWidgetItem(s.material))
            spin = QDoubleSpinBox(); spin.setRange(0, 10000); spin.setValue(s.remaining_g)
            spin.editingFinished.connect(lambda sid=s.id, w=spin: self.db.set_remaining(sid, w.value()))
            self.table.setCellWidget(r, 2, spin)
            self.table.setItem(r, 3, QTableWidgetItem(f"{s.initial_g:.0f}"))
            combo = QComboBox()
            for label, value in self._slot_options():
                combo.addItem(label, value)
            combo.setCurrentIndex(max(0, combo.findData(s.slot)))
            combo.activated.connect(lambda _i, sid=s.id, w=combo: self.db.assign_slot(sid, w.currentData()))
            self.table.setCellWidget(r, 4, combo)

    def _add(self) -> None:
        d = AddSpoolDialog(self)
        if d.exec() and d.name.text().strip():
            self.db.add_spool(d.name.text().strip(), d.material.currentText(), d.color, d.brand.text(), d.weight.value())
            self.refresh()

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.db.delete_spool(self.table.item(row, 0).data(0x100))
            self.refresh()
