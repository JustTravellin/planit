from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QLabel, QMessageBox, QProgressBar, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout)

from .. import commands, ftps, threemf
from ..config import PrinterConfig
from ..state import AmsTray
from .bridge import PrinterBridge
from .util import fmt_seconds

NONE_TEXT = "— choose a slot —"


class _UploadThread(QThread):
    progress = Signal(int, int)
    done = Signal()
    failed = Signal(str)

    def __init__(self, cfg: PrinterConfig, path: Path):
        super().__init__()
        self.cfg, self.path = cfg, path

    def run(self) -> None:
        try:
            ftps.upload(self.cfg.ip, self.cfg.access_code, self.path, progress=self.progress.emit)
            self.done.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


def preflight_problems(filaments: list[threemf.FileFilament], mapping: list[int | None],
                       trays: list[AmsTray]) -> list[str]:
    """Reasons this print might go wrong; shown as warnings, not blockers."""
    by_index = {t.global_index: t for t in trays}
    problems = []
    for fil, slot in zip(filaments, mapping):
        if slot is None:
            problems.append(f"Filament {fil.index} ({fil.material}) has no slot chosen.")
            continue
        tray = by_index.get(slot)
        if tray is None or tray.empty:
            problems.append(f"Slot {slot + 1} is empty.")
            continue
        if tray.material.upper() != fil.material.upper():
            problems.append(f"Slot {slot + 1} holds {tray.material}, file wants {fil.material}.")
        if 0 <= tray.remain < 15:
            problems.append(f"Slot {slot + 1} is low ({tray.remain}% left).")
    chosen = [s for s in mapping if s is not None]
    if len(chosen) != len(set(chosen)):
        problems.append("The same slot is used for more than one filament.")
    return problems


class SendDialog(QDialog):
    def __init__(self, bridge: PrinterBridge, path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Send {path.name}")
        self.setMinimumWidth(520)
        self.bridge, self.path = bridge, path
        self.info = threemf.read(path)
        self.trays = bridge.state.ams_trays
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>{path.name}</b><br>{fmt_seconds(self.info.print_seconds)} · "
                             f"{self.info.weight_grams:.1f} g"))

        self.table = QTableWidget(len(self.info.filaments), 3)
        self.table.setHorizontalHeaderLabels(["Filament in file", "Grams", "AMS slot"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        suggestion = threemf.suggest_ams_mapping(self.info.filaments, self.trays)
        self.combos: list[QComboBox] = []
        for row, fil in enumerate(self.info.filaments):
            self.table.setItem(row, 0, QTableWidgetItem(f"{fil.index}: {fil.material} #{fil.color}"))
            self.table.setItem(row, 1, QTableWidgetItem(f"{fil.used_grams:.1f}"))
            combo = QComboBox()
            combo.addItem(NONE_TEXT, None)
            for t in self.trays:
                label = f"AMS{t.ams_id + 1} slot {t.slot + 1}: " + ("empty" if t.empty else f"{t.material} #{t.color}")
                combo.addItem(label, t.global_index)
            idx = combo.findData(suggestion[row])
            combo.setCurrentIndex(max(idx, 0))
            combo.currentIndexChanged.connect(self._refresh)
            self.table.setCellWidget(row, 2, combo)
            self.combos.append(combo)
        self.table.setMaximumHeight(40 + 34 * max(1, len(self.info.filaments)))
        lay.addWidget(self.table)

        self.warnings = QLabel("")
        self.warnings.setWordWrap(True)
        self.warnings.setStyleSheet("color: #f5a524;")
        lay.addWidget(self.warnings)

        self.bed_clear = QCheckBox("The build plate is clear and clean")
        self.filament_ok = QCheckBox("The right filament is loaded in the chosen slots")
        self.start_now = QCheckBox("Start printing right after upload")
        self.start_now.setChecked(True)
        for c in (self.bed_clear, self.filament_ok, self.start_now):
            c.stateChanged.connect(self._refresh)
            lay.addWidget(c)

        self.bar = QProgressBar()
        self.bar.hide()
        lay.addWidget(self.bar)
        row = QHBoxLayout()
        self.go = QPushButton("Send")
        self.go.setObjectName("primary")
        cancel = QPushButton("Cancel")
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.go)
        lay.addLayout(row)
        cancel.clicked.connect(self.reject)
        self.go.clicked.connect(self._go)
        self._thread: _UploadThread | None = None
        self.started = False
        self._refresh()

    def mapping(self) -> list[int | None]:
        return [c.currentData() for c in self.combos]

    def _refresh(self, *_args) -> None:
        problems = preflight_problems(self.info.filaments, self.mapping(), self.trays)
        self.warnings.setText("\n".join("⚠ " + p for p in problems))
        ready = self.bridge.connected and self.bridge.allow_control
        if self.start_now.isChecked():
            ready = ready and self.bed_clear.isChecked() and self.filament_ok.isChecked() and None not in self.mapping()
        self.go.setEnabled(ready and self._thread is None)
        if not self.bridge.allow_control:
            self.go.setToolTip("Tick 'Allow control' in the toolbar first.")
        elif not self.bridge.connected:
            self.go.setToolTip("Not connected to the printer.")
        else:
            self.go.setToolTip("")

    def _go(self) -> None:
        cfg = self.bridge.config
        if cfg is None:
            return
        self.go.setEnabled(False)
        self.bar.show()
        self._thread = _UploadThread(cfg, self.path)
        self._thread.progress.connect(lambda sent, total: (self.bar.setMaximum(total), self.bar.setValue(sent)))
        self._thread.done.connect(self._uploaded)
        self._thread.failed.connect(self._failed)
        self._thread.start()

    def _failed(self, message: str) -> None:
        self._thread = None
        self.bar.hide()
        QMessageBox.critical(self, "Upload failed", message)
        self._refresh()

    def _uploaded(self) -> None:
        self._thread = None
        if self.start_now.isChecked():
            mapping = [m for m in self.mapping() if m is not None]
            usage = {m: f.used_grams for m, f in zip(self.mapping(), self.info.filaments) if m is not None}
            try:
                self.bridge.recorder.set_expected_usage(usage, name=self.path.name.removesuffix(".gcode.3mf"))
                self.bridge.send(commands.project_file(self.path.name, plate=self.info.plate, ams_mapping=mapping))
            except Exception as exc:
                QMessageBox.critical(self, "Could not start print", str(exc))
                return
            self.started = True
        self.accept()
