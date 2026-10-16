"""The Slice section of the library inspector: pick quality and filament, slice for the P1S, get advice."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from .. import advice, plate, slicer
from . import theme
from .bridge import PrinterBridge

SEVERITY_COLOR = {"error": theme.BAD, "warn": theme.WARN, "info": theme.MUTED}


class _SliceThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, model: Path, dest: Path, settings: slicer.Settings, cancel: threading.Event):
        super().__init__()
        self.model, self.dest, self.settings, self.cancel = model, dest, settings, cancel

    def run(self) -> None:
        try:
            self.done.emit(slicer.slice_model(self.model, self.dest, self.settings, cancel=self.cancel))
        except Exception as exc:
            self.failed.emit(str(exc))


class SlicePanel(QWidget):
    sliced = Signal(object)  # slicer.SliceResult

    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.slicer = slicer.find_slicer()
        self.model: Path | None = None
        self.fit: plate.FitReport | None = None
        self._thread: _SliceThread | None = None
        self._cancel = threading.Event()
        self.nozzle = "0.4"
        self.processes: list[str] = []
        self.filaments: list[str] = []
        self.fil_combos: list[QComboBox] = []

        self.quality = QComboBox()
        self.infill = QSpinBox(); self.infill.setRange(0, 100); self.infill.setSuffix(" %"); self.infill.setSpecialValueText("Preset")
        self.walls = QSpinBox(); self.walls.setRange(0, 10); self.walls.setSpecialValueText("Preset")
        self.supports = QComboBox(); self.supports.addItems(["Preset", "On", "Off"])
        self.bed = QComboBox(); self.bed.addItem("Preset")
        self.bed.addItems(slicer.BED_TYPES)
        self.brim = QCheckBox("Brim (helps big or tall parts stick)")
        self.purge = QCheckBox("Reduce colour-change waste")
        self.form = QFormLayout()
        self.form.addRow("Quality", self.quality)
        self.fil_rows = QVBoxLayout()
        self.form.addRow("Filament", self.fil_rows)
        self.form.addRow("Infill", self.infill)
        self.form.addRow("Walls", self.walls)
        self.form.addRow("Supports", self.supports)
        self.form.addRow("Plate", self.bed)
        self.advice = QLabel("")
        self.advice.setWordWrap(True)
        self.advice.setTextFormat(Qt.RichText)
        self.button = QPushButton("Slice for P1S")
        self.button.setObjectName("primary")
        self.cancel_btn = QPushButton("Cancel")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.button, 1)
        row.addWidget(self.cancel_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.form)
        lay.addWidget(self.brim)
        lay.addWidget(self.purge)
        lay.addWidget(self.advice)
        lay.addLayout(row)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)
        self.progress.hide()
        self.cancel_btn.hide()

        if self.slicer is None:
            self.button.setEnabled(False)
            self.status.setText("<span style='color:%s'>Bambu Studio was not found. Install it (it supplies the "
                                "slicing engine and P1S profiles) and restart.</span>" % theme.WARN)
        else:
            self._load_presets()
        self.button.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self._cancel.set)
        for w in (self.quality, self.supports, self.bed):
            w.currentIndexChanged.connect(self.refresh_advice)

    # ---- presets
    def _load_presets(self) -> None:
        root = self.slicer.profiles
        self.processes = slicer.process_presets(root, self.nozzle)
        self.filaments = slicer.filament_presets(root, self.nozzle)
        self.quality.clear()
        for name in self.processes:
            self.quality.addItem(slicer.short_name(name), name)
        i = self.quality.findText("0.20mm Standard")
        self.quality.setCurrentIndex(max(i, 0))

    def _ams_options(self) -> list[tuple[str, str, str]]:
        """(label, preset, colour) for each loaded AMS spool."""
        out = []
        for t in self.bridge.state.ams_trays:
            if t.empty or not t.material:
                continue
            preset = slicer.suggest_filament(t.material, t.brand, self.filaments)
            if preset:
                label = f"AMS {t.ams_id + 1}·{t.slot + 1}  {t.brand or t.material}"
                out.append((label, preset, t.color))
        return out

    def set_model(self, path: Path, filaments: int, fit: plate.FitReport | None, bed_hint: str = "") -> None:
        """Called when a file is selected; builds one filament row per filament the model uses."""
        self.model, self.fit = path, fit
        self.status.setText("")
        for c in self.fil_combos:
            self.fil_rows.removeWidget(c)
            c.deleteLater()
        self.fil_combos = []
        ams = self._ams_options()
        used: set[str] = set()
        for i in range(max(1, filaments)):
            combo = QComboBox()
            for label, preset, color in ams:
                combo.addItem(f"● {label}", (preset, color))
            for preset in self.filaments:
                combo.addItem(slicer.short_name(preset) + ("" if "P1S" in preset else "  (X1C)"), (preset, ""))
            pick = next((k for k, (_, p, _c) in enumerate(ams) if p not in used), None)
            if pick is None:
                pick = combo.findText("Generic PLA") if combo.findText("Generic PLA") >= 0 else 0
            combo.setCurrentIndex(pick)
            used.add(combo.currentData()[0])
            combo.currentIndexChanged.connect(self.refresh_advice)
            self.fil_combos.append(combo)
            self.fil_rows.addWidget(combo)
        self.purge.setVisible(filaments > 1)
        self.refresh_advice()

    # ---- advice + settings
    def settings(self) -> slicer.Settings:
        picks = [c.currentData() for c in self.fil_combos] or [("Generic PLA", "")]
        return slicer.Settings(
            process=self.quality.currentData() or "0.20mm Standard @BBL X1C",
            filaments=[p for p, _ in picks], colors=[c for _, c in picks], nozzle=self.nozzle,
            infill=f"{self.infill.value()}%" if self.infill.value() else "", walls=self.walls.value(),
            supports={"Preset": None, "On": True, "Off": False}[self.supports.currentText()],
            bed_type="" if self.bed.currentIndex() == 0 else self.bed.currentText(),
            brim=True if self.brim.isChecked() else None, reduce_purge=self.purge.isChecked())

    def refresh_advice(self) -> None:
        s = self.settings()
        try:
            height = float((self.quality.currentData() or "").split("mm")[0])
        except ValueError:
            height = 0.0
        nozzle_type = self.bridge.state.raw.get("nozzle_type") or None
        items = advice.advise(s.filaments, nozzle_type=nozzle_type, bed_type=s.bed_type or "", supports=s.supports,
                              fit=self.fit, layer_height=height)
        self.advice.setText("<br>".join(
            f"<span style='color:{SEVERITY_COLOR[sev]}'>{'●' if sev != 'info' else '·'}</span> {text}"
            for sev, text in items))

    # ---- run
    def start(self) -> None:
        if not self.model or self._thread is not None:
            return
        dest = slicer.output_path(self.model)
        self._cancel.clear()
        self.progress.show()
        self.cancel_btn.show()
        self.button.setEnabled(False)
        self.status.setText("Slicing…")
        self._thread = _SliceThread(self.model, dest, self.settings(), self._cancel)
        self._thread.done.connect(self._done)
        self._thread.failed.connect(self._failed)
        self._thread.start()

    def _finish(self) -> None:
        self.progress.hide()
        self.cancel_btn.hide()
        self.button.setEnabled(self.slicer is not None)
        if self._thread:
            self._thread.wait()
        self._thread = None

    def _done(self, result: slicer.SliceResult) -> None:
        self._finish()
        mins = result.seconds // 60
        self.status.setText(f"<span style='color:{theme.OK}'>Sliced: {mins // 60}h {mins % 60:02d}m, "
                            f"{result.grams:.1f} g, {result.layers} layers → {result.path.name}</span>")
        self.sliced.emit(result)

    def _failed(self, message: str) -> None:
        self._finish()
        self.status.setText(f"<span style='color:{theme.BAD}'>Slicing failed: {message}</span>")

    def wait(self) -> None:
        if self._thread:
            self._thread.wait()
