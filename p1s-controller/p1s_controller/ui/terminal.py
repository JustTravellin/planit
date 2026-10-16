from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
import json

from .. import commands
from .bridge import PrinterBridge


class Terminal(QWidget):
    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumBlockCount(2000)
        self.input = QLineEdit(placeholderText="G-code, e.g. M115  (needs 'Allow control')")
        self.send_btn = QPushButton("Send")
        self.raw = QCheckBox("Show raw printer reports")
        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        lay = QVBoxLayout(self)
        lay.addWidget(self.log, 1)
        lay.addLayout(row)
        lay.addWidget(self.raw)
        self.input.returnPressed.connect(self._send)
        self.send_btn.clicked.connect(self._send)
        bridge.rawMessage.connect(self._on_raw)
        bridge.controlChanged.connect(self._refresh)
        bridge.connectionChanged.connect(lambda *_: self._refresh())
        self._refresh()

    def _refresh(self, *_a) -> None:
        on = self.bridge.connected and self.bridge.allow_control
        self.input.setEnabled(on)
        self.send_btn.setEnabled(on)

    def _send(self) -> None:
        line = self.input.text().strip()
        if not line:
            return
        try:
            self.bridge.send(commands.gcode_line(line))
            self.log.appendPlainText(f"> {line}")
            self.input.clear()
        except Exception as exc:
            self.log.appendPlainText(f"! {exc}")

    def _on_raw(self, report: dict) -> None:
        printed = report.get("print", {})
        if printed.get("command") == "gcode_line":
            self.log.appendPlainText(f"< {printed.get('result', '')} {printed.get('reason', '')}".rstrip())
        elif self.raw.isChecked():
            self.log.appendPlainText(json.dumps(report)[:600])
