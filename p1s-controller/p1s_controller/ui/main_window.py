from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox, QStackedWidget,
                               QSystemTrayIcon, QToolBar, QWidget, QSizePolicy)

from ..db import Database
from . import theme
from .bridge import PrinterBridge
from .dashboard import Dashboard
from .control_tab import ControlTab
from .filament_tab import FilamentTab
from .health_tab import HealthTab
from .history_tab import HistoryTab
from .library import Library
from .settings_tab import SettingsTab
from .terminal import Terminal
from .wizard import SetupWizard

EVENT_TEXT = {
    "started": "Print started", "paused": "Print paused", "resumed": "Print resumed",
    "finished": "Print finished", "failed": "Print FAILED", "cancelled": "Print cancelled",
}


class SideTabs(QWidget):
    """Left navigation rail + page stack. Same small API as QTabWidget."""

    def __init__(self):
        super().__init__()
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(168)
        self.nav.setFocusPolicy(Qt.NoFocus)
        self.stack = QStackedWidget()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

    def addTab(self, widget: QWidget, title: str) -> int:
        self.nav.addItem(title)
        idx = self.stack.addWidget(widget)
        if idx == 0:
            self.nav.setCurrentRow(0)
        return idx

    def setCurrentWidget(self, widget: QWidget) -> None:
        self.nav.setCurrentRow(self.stack.indexOf(widget))

    def setCurrentIndex(self, idx: int) -> None:
        self.nav.setCurrentRow(idx)

    def currentWidget(self) -> QWidget:
        return self.stack.currentWidget()


class MainWindow(QMainWindow):
    def __init__(self, bridge: PrinterBridge, db: Database):
        super().__init__()
        self.bridge, self.db = bridge, db
        self.setWindowTitle("P1S Controller")
        self.resize(1200, 780)

        self.dashboard = Dashboard(bridge)
        self.library = Library(bridge, db)
        self.control = ControlTab(bridge)
        self.terminal = Terminal(bridge)
        self.health = HealthTab(bridge)
        self.history = HistoryTab(bridge, db)
        self.filament = FilamentTab(bridge, db)
        self.settings = SettingsTab(bridge)
        tabs = SideTabs()
        for widget, title in ((self.dashboard, "Dashboard"), (self.library, "Library"), (self.control, "Control"),
                              (self.terminal, "Terminal"), (self.history, "History"), (self.filament, "Filament"),
                              (self.health, "Health"), (self.settings, "Settings")):
            tabs.addTab(widget, title)
        self.tabs = tabs
        self.setCentralWidget(tabs)

        bar = QToolBar()
        bar.setMovable(False)
        bar.setObjectName("header")
        app_name = QLabel("P1S Controller")
        app_name.setObjectName("brand")
        self.conn_label = QLabel("● Not connected")
        self.conn_label.setStyleSheet(f"color: {theme.MUTED}; padding: 0 8px;")
        self.state_chip = QLabel("")
        self.state_chip.setObjectName("chip")
        self.state_chip.hide()
        self.control_box = QCheckBox("Allow control")
        self.control_box.setToolTip("Off = read-only. Turn on to pause, stop, send prints, set temperatures.")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(app_name)
        bar.addWidget(self.conn_label)
        bar.addWidget(self.state_chip)
        bar.addWidget(spacer)
        bar.addWidget(self.control_box)
        self.addToolBar(bar)

        self.tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            pm = QPixmap(32, 32)
            pm.fill(QColor(theme.ACCENT))
            self.tray = QSystemTrayIcon(QIcon(pm), self)
            self.tray.show()

        self.control_box.toggled.connect(self._control_toggled)
        bridge.connectionChanged.connect(self._on_connection)
        bridge.stateChanged.connect(self._on_state)
        bridge.event.connect(self._on_event)
        bridge.alert.connect(self._on_alert)
        self.settings.wizardRequested.connect(self.open_wizard)

    def _control_toggled(self, on: bool) -> None:
        if on:
            answer = QMessageBox.question(
                self, "Allow control",
                "This lets the app move the printer, change temperatures and start or stop prints. Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                self.control_box.blockSignals(True)
                self.control_box.setChecked(False)
                self.control_box.blockSignals(False)
                return
        self.bridge.set_allow_control(on)

    def _on_connection(self, ok: bool, message: str) -> None:
        color = theme.OK if ok else theme.MUTED
        self.conn_label.setText(f"● {message}")
        self.conn_label.setStyleSheet(f"color: {color}; padding: 0 8px;")

    def _on_state(self, s) -> None:
        color = theme.STATE_COLORS.get(s.gcode_state, theme.MUTED)
        text = s.gcode_state.title()
        if s.gcode_state in ("RUNNING", "PAUSE"):
            text += f" {s.percent}% · {s.remaining_minutes} min left"
        self.state_chip.setText(text)
        self.state_chip.setStyleSheet(f"color: {color}; border: 1px solid {color};")
        self.state_chip.show()

    def _on_event(self, event: str, job: str) -> None:
        if self.tray and self.settings.notify.isChecked() and event in EVENT_TEXT:
            self.tray.showMessage(EVENT_TEXT[event], job or "", QSystemTrayIcon.Information, 8000)

    def _on_alert(self, alert) -> None:
        if self.tray and self.settings.notify.isChecked():
            icon = QSystemTrayIcon.Critical if alert.severity == "error" else QSystemTrayIcon.Warning
            self.tray.showMessage(alert.title, alert.detail, icon, 10000)

    def open_wizard(self) -> None:
        SetupWizard(self.bridge, self).exec()
