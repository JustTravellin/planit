from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from .. import commands
from ..state import PrinterState
from . import theme
from .ams_panel import AmsPanel
from .bridge import PrinterBridge
from .temp_graph import TempGraph
from .util import eta_clock, fmt_minutes


class Dashboard(QWidget):
    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.state = PrinterState()
        root = QHBoxLayout(self)

        # ---- left column: job + controls
        left = QVBoxLayout()
        job = QFrame(objectName="card")
        jl = QVBoxLayout(job)
        self.state_badge = QLabel("NOT CONNECTED")
        self.job_name = QLabel("No active print")
        self.job_name.setObjectName("big")
        self.job_name.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        for w in (self.state_badge, self.job_name, self.progress, self.detail):
            jl.addWidget(w)
        left.addWidget(job)

        ctl = QGroupBox("Controls")
        grid = QGridLayout(ctl)
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("danger")
        self.light_btn = QPushButton("Light")
        self.speed = QComboBox()
        for name in commands.SPEED_LEVELS:
            self.speed.addItem(name.title(), commands.SPEED_LEVELS[name])
        self.nozzle_in = QSpinBox(); self.nozzle_in.setRange(0, 300); self.nozzle_in.setSuffix(" °C")
        self.bed_in = QSpinBox(); self.bed_in.setRange(0, 120); self.bed_in.setSuffix(" °C")
        self.set_nozzle = QPushButton("Set nozzle")
        self.set_bed = QPushButton("Set bed")
        grid.addWidget(self.pause_btn, 0, 0); grid.addWidget(self.stop_btn, 0, 1)
        grid.addWidget(self.light_btn, 1, 0); grid.addWidget(self.speed, 1, 1)
        grid.addWidget(self.nozzle_in, 2, 0); grid.addWidget(self.set_nozzle, 2, 1)
        grid.addWidget(self.bed_in, 3, 0); grid.addWidget(self.set_bed, 3, 1)
        self.control_note = QLabel("Control is off. Tick 'Allow control' in the toolbar to use these.")
        self.control_note.setObjectName("muted")
        self.control_note.setWordWrap(True)
        grid.addWidget(self.control_note, 4, 0, 1, 2)
        left.addWidget(ctl)
        left.addStretch(1)
        root.addLayout(left, 2)

        # ---- right column: temps + AMS
        right = QVBoxLayout()
        temps = QGroupBox("Temperatures")
        tl = QVBoxLayout(temps)
        self.temp_label = QLabel("")
        self.graph = TempGraph()
        tl.addWidget(self.temp_label)
        tl.addWidget(self.graph)
        right.addWidget(temps, 3)
        ams = QGroupBox("AMS")
        al = QVBoxLayout(ams)
        self.ams = AmsPanel()
        al.addWidget(self.ams)
        right.addWidget(ams, 2)
        root.addLayout(right, 3)

        self.pause_btn.clicked.connect(self._toggle_pause)
        self.stop_btn.clicked.connect(self._stop)
        self.light_btn.clicked.connect(lambda: self._send(commands.light(not bool(self.state.chamber_light_on))))
        self.speed.activated.connect(lambda _i: self._send(commands.print_speed(self.speed.currentData())))
        self.set_nozzle.clicked.connect(lambda: self._send(commands.set_nozzle_temp(self.nozzle_in.value())))
        self.set_bed.clicked.connect(lambda: self._send(commands.set_bed_temp(self.bed_in.value())))

        bridge.stateChanged.connect(self.update_state)
        bridge.controlChanged.connect(self._refresh_enabled)
        bridge.connectionChanged.connect(lambda ok, _m: self._refresh_enabled())
        self._refresh_enabled()

    # ---- state
    def update_state(self, s: PrinterState) -> None:
        self.state = s
        gs = s.gcode_state
        color = theme.STATE_COLORS.get(gs, theme.MUTED)
        self.state_badge.setText(gs)
        self.state_badge.setStyleSheet(f"color: {color}; font-weight: 700; letter-spacing: 1px;")
        active = gs in ("RUNNING", "PREPARE", "PAUSE")
        self.job_name.setText(s.job_name or "No active print")
        self.progress.setValue(s.percent)
        if active:
            self.detail.setText(
                f"Layer {s.layer}/{s.total_layers}  ·  {fmt_minutes(s.remaining_minutes)} left"
                f"  ·  done at {eta_clock(s.remaining_minutes)}")
        else:
            self.detail.setText("")
        self.temp_label.setText(
            f"Nozzle {s.nozzle_temp:.0f}/{s.nozzle_target:.0f} °C   "
            f"Bed {s.bed_temp:.0f}/{s.bed_target:.0f} °C   Chamber {s.chamber_temp:.0f} °C")
        self.graph.add_sample(s.nozzle_temp, s.bed_temp, s.chamber_temp, s.nozzle_target, s.bed_target)
        self.ams.update_trays(s.ams_trays, s.active_tray)
        if not self.nozzle_in.hasFocus() and s.nozzle_target:
            self.nozzle_in.setValue(int(s.nozzle_target))
        if not self.bed_in.hasFocus() and s.bed_target:
            self.bed_in.setValue(int(s.bed_target))
        self.pause_btn.setText("Resume" if gs == "PAUSE" else "Pause")
        self.light_btn.setText("Light off" if s.chamber_light_on else "Light on")
        idx = self.speed.findData(s.speed_level)
        if idx >= 0 and not self.speed.view().isVisible():
            self.speed.setCurrentIndex(idx)
        self._refresh_enabled()

    def _refresh_enabled(self, *_args) -> None:
        ok = self.bridge.connected and self.bridge.allow_control
        active = self.state.gcode_state in ("RUNNING", "PREPARE", "PAUSE")
        for w in (self.light_btn, self.speed, self.nozzle_in, self.bed_in, self.set_nozzle, self.set_bed):
            w.setEnabled(ok)
        self.pause_btn.setEnabled(ok and active)
        self.stop_btn.setEnabled(ok and active)
        self.control_note.setVisible(not self.bridge.allow_control)

    # ---- actions
    def _send(self, payload: dict) -> None:
        try:
            self.bridge.send(payload)
        except Exception as exc:  # ControlDisabled / not connected
            QMessageBox.warning(self, "Can't send", str(exc))

    def _toggle_pause(self) -> None:
        paused = self.state.gcode_state == "PAUSE"
        self._send(commands.resume() if paused else commands.pause())

    def _stop(self) -> None:
        answer = QMessageBox.question(
            self, "Stop print", f"Stop '{self.state.job_name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self._send(commands.stop())
