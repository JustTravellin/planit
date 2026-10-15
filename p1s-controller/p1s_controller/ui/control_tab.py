from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

from .. import commands
from ..state import PrinterState
from .bridge import PrinterBridge

JOG_STEPS = [0.1, 1, 10]


class ControlTab(QWidget):
    """Manual jog, fans, extrusion and AMS load/unload. Disabled while printing."""

    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.state = PrinterState()
        self._ams_rows: list[QWidget] = []

        self.note = QLabel("")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)

        # --- jog
        jog = QGroupBox("Move")
        g = QGridLayout(jog)
        self.step = QComboBox()
        for s in JOG_STEPS:
            self.step.addItem(f"{s:g} mm", s)
        self.step.setCurrentIndex(1)
        self.jog_buttons: list[QPushButton] = []
        layout = [("Y+", "Y", 1, 0, 1), ("X-", "X", -1, 1, 0), ("X+", "X", 1, 1, 2),
                  ("Y-", "Y", -1, 2, 1), ("Z+", "Z", 1, 0, 3), ("Z-", "Z", -1, 2, 3)]
        for label, axis, sign, r, c in layout:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, a=axis, sg=sign: self._jog(a, sg))
            g.addWidget(b, r, c)
            self.jog_buttons.append(b)
        self.home_btn = QPushButton("Home all")
        self.level_btn = QPushButton("Auto bed level")
        g.addWidget(QLabel("Step"), 3, 0)
        g.addWidget(self.step, 3, 1)
        g.addWidget(self.home_btn, 4, 0, 1, 2)
        g.addWidget(self.level_btn, 4, 2, 1, 2)
        self.home_btn.clicked.connect(lambda: self._confirm_send("Home all axes? The toolhead and bed will move.", commands.home()))
        self.level_btn.clicked.connect(lambda: self._confirm_send("Run auto bed levelling? This heats nothing but moves the toolhead and probes the bed.", commands.auto_bed_level()))

        # --- fans
        fans = QGroupBox("Fans")
        fl = QGridLayout(fans)
        self.fan_sliders: dict[str, QSlider] = {}
        for row, (name, label) in enumerate((("part", "Part cooling"), ("aux", "Auxiliary"), ("chamber", "Chamber"))):
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 100)
            val = QLabel("0%")
            sl.valueChanged.connect(lambda v, w=val: w.setText(f"{v}%"))
            sl.sliderReleased.connect(lambda n=name, w=sl: self._send(commands.set_fan(n, w.value())))
            fl.addWidget(QLabel(label), row, 0)
            fl.addWidget(sl, row, 1)
            fl.addWidget(val, row, 2)
            self.fan_sliders[name] = sl

        # --- extruder
        ext = QGroupBox("Extruder")
        el = QHBoxLayout(ext)
        self.ext_len = QDoubleSpinBox(); self.ext_len.setRange(1, 50); self.ext_len.setValue(10); self.ext_len.setSuffix(" mm")
        self.extrude_btn = QPushButton("Extrude")
        self.retract_btn = QPushButton("Retract")
        for w in (self.ext_len, self.extrude_btn, self.retract_btn):
            el.addWidget(w)
        self.extrude_btn.clicked.connect(lambda: self._extrude(1))
        self.retract_btn.clicked.connect(lambda: self._extrude(-1))

        # --- AMS
        self.ams_box = QGroupBox("AMS filament")
        self.ams_layout = QVBoxLayout(self.ams_box)
        self.unload_btn = QPushButton("Unload current filament")
        self.unload_btn.clicked.connect(lambda: self._confirm_send("Unload the current filament? The nozzle will heat.", commands.ams_unload()))
        self.ams_layout.addWidget(self.unload_btn)
        self.ams_empty = QLabel("No AMS data yet")
        self.ams_empty.setObjectName("muted")
        self.ams_layout.addWidget(self.ams_empty)

        left = QVBoxLayout()
        left.addWidget(jog); left.addWidget(fans); left.addWidget(ext); left.addStretch(1)
        right = QVBoxLayout()
        right.addWidget(self.ams_box); right.addStretch(1)
        cols = QHBoxLayout()
        cols.addLayout(left, 1); cols.addLayout(right, 1)
        lay = QVBoxLayout(self)
        lay.addWidget(self.note)
        lay.addLayout(cols, 1)

        bridge.stateChanged.connect(self.update_state)
        bridge.controlChanged.connect(lambda _on: self._refresh_enabled())
        bridge.connectionChanged.connect(lambda *_: self._refresh_enabled())
        self._refresh_enabled()

    # ---- state
    def update_state(self, s: PrinterState) -> None:
        self.state = s
        self._rebuild_ams(s)
        self._refresh_enabled()

    def _rebuild_ams(self, s: PrinterState) -> None:
        trays = s.ams_trays
        key = [(t.global_index, t.material, t.color) for t in trays]
        if key == getattr(self, "_ams_key", None):
            return
        self._ams_key = key
        for w in self._ams_rows:
            w.setParent(None)
        self._ams_rows.clear()
        self.ams_empty.setVisible(not trays)
        for t in trays:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            label = QLabel(f"AMS{t.ams_id + 1} slot {t.slot + 1}: " + ("empty" if t.empty else f"{t.material}"))
            if not t.empty:
                label.setStyleSheet(f"color: #{t.color or 'FFFFFF'};")
            btn = QPushButton("Load")
            btn.setEnabled(not t.empty and self._can_control())
            btn.setProperty("slot_empty", t.empty)
            btn.clicked.connect(lambda _=False, idx=t.global_index, n=f"AMS{t.ams_id + 1} slot {t.slot + 1}":
                                self._confirm_send(f"Load filament from {n}? The nozzle will heat.", commands.ams_load(idx)))
            rl.addWidget(label, 1)
            rl.addWidget(btn)
            self.ams_layout.insertWidget(self.ams_layout.count() - 2, row)
            self._ams_rows.append(row)

    # ---- gating
    def _can_control(self) -> bool:
        return self.bridge.connected and self.bridge.allow_control

    def _printing(self) -> bool:
        return self.state.gcode_state in ("RUNNING", "PREPARE", "PAUSE")

    def _refresh_enabled(self) -> None:
        ok = self._can_control() and not self._printing()
        for w in (*self.jog_buttons, self.step, self.home_btn, self.level_btn, self.extrude_btn,
                  self.retract_btn, self.ext_len, self.unload_btn):
            w.setEnabled(ok)
        for sl in self.fan_sliders.values():
            sl.setEnabled(self._can_control())  # fans are fine to adjust mid-print
        for row in self._ams_rows:
            for b in row.findChildren(QPushButton):
                b.setEnabled(ok and not b.property("slot_empty"))
        if not self.bridge.connected:
            self.note.setText("Not connected.")
        elif not self.bridge.allow_control:
            self.note.setText("Control is off. Tick 'Allow control' in the toolbar to use these.")
        elif self._printing():
            self.note.setText("Motion, extrusion and AMS controls are disabled while a print is running. Fans still work.")
        else:
            self.note.setText("")

    # ---- actions
    def _send(self, payload: dict) -> None:
        try:
            self.bridge.send(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Can't send", str(exc))

    def _confirm_send(self, question: str, payload: dict) -> None:
        if QMessageBox.question(self, "Confirm", question, QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            self._send(payload)

    def _jog(self, axis: str, sign: int) -> None:
        feed = 600 if axis == "Z" else 3000
        try:
            self._send(commands.move(axis, sign * self.step.currentData(), feed))
        except ValueError as exc:
            QMessageBox.warning(self, "Can't move", str(exc))

    def _extrude(self, sign: int) -> None:
        try:
            self._send(commands.extrude(sign * self.ext_len.value(), self.state.nozzle_temp))
        except ValueError as exc:
            QMessageBox.warning(self, "Can't extrude", str(exc))
