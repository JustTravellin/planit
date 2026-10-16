from __future__ import annotations

import time

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..health import Alert
from ..state import PrinterState
from . import theme
from .bridge import PrinterBridge


class HealthTab(QWidget):
    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.summary = QLabel("Waiting for the printer…")
        self.summary.setObjectName("big")

        self.alerts = QTableWidget(0, 3)
        self.alerts.setHorizontalHeaderLabels(["Time", "Alert", "Details"])
        self.alerts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.alerts.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.alerts.verticalHeader().hide()
        self.alerts.setEditTriggers(QTableWidget.NoEditTriggers)
        clear = QPushButton("Clear alerts")
        clear.clicked.connect(lambda: self.alerts.setRowCount(0))
        ab = QGroupBox("Alerts this session")
        al = QVBoxLayout(ab)
        al.addWidget(self.alerts)
        al.addWidget(clear)

        self.fw = QTableWidget(0, 2)
        self.fw.setHorizontalHeaderLabels(["Module", "Firmware"])
        self.fw.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.fw.verticalHeader().hide()
        self.fw.setEditTriggers(QTableWidget.NoEditTriggers)
        self.info = QLabel("")
        self.info.setObjectName("muted")
        fb = QGroupBox("Printer info")
        fl = QVBoxLayout(fb)
        fl.addWidget(self.info)
        fl.addWidget(self.fw)

        cols = QHBoxLayout()
        cols.addWidget(ab, 3)
        cols.addWidget(fb, 2)
        lay = QVBoxLayout(self)
        lay.addWidget(self.summary)
        lay.addLayout(cols, 1)

        bridge.alert.connect(self.add_alert)
        bridge.stateChanged.connect(self.update_state)

    def add_alert(self, a: Alert) -> None:
        self.alerts.insertRow(0)
        color = QColor(theme.BAD if a.severity == "error" else theme.WARN)
        for c, text in enumerate((time.strftime("%H:%M:%S", time.localtime(a.time)), a.title, a.detail)):
            item = QTableWidgetItem(text)
            if c == 1:
                item.setForeground(color)
            self.alerts.setItem(0, c, item)
        self._update_summary()

    def update_state(self, s: PrinterState) -> None:
        dbm = s.wifi_dbm
        self.info.setText(f"Wi-Fi signal: {dbm} dBm" if dbm is not None else "Wi-Fi signal: unknown")
        mods = sorted(s.modules.items())
        self.fw.setRowCount(len(mods))
        for i, (name, ver) in enumerate(mods):
            self.fw.setItem(i, 0, QTableWidgetItem(name))
            self.fw.setItem(i, 1, QTableWidgetItem(ver))
        self._update_summary(s)

    def _update_summary(self, s: PrinterState | None = None) -> None:
        errors = sum(1 for r in range(self.alerts.rowCount())
                     if self.alerts.item(r, 1).foreground().color().name().lower() == theme.BAD.lower())
        if errors:
            self.summary.setText(f"{errors} error(s) reported")
            self.summary.setStyleSheet(f"color: {theme.BAD};")
        elif self.alerts.rowCount():
            self.summary.setText(f"{self.alerts.rowCount()} warning(s)")
            self.summary.setStyleSheet(f"color: {theme.WARN};")
        else:
            self.summary.setText("No problems reported")
            self.summary.setStyleSheet(f"color: {theme.OK};")
