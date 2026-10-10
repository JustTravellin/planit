from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QLineEdit, QPushButton, QWidget, QHBoxLayout, QVBoxLayout

from .. import config
from .bridge import PrinterBridge


class SettingsTab(QWidget):
    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        cfg = config.load()
        self.ip = QLineEdit(cfg.ip if cfg else "", placeholderText="192.168.1.50")
        self.serial = QLineEdit(cfg.serial if cfg else "", placeholderText="Printer serial number")
        self.code = QLineEdit(cfg.access_code if cfg else "", placeholderText="LAN access code")
        self.code.setEchoMode(QLineEdit.Password)
        self.notify = QCheckBox("Desktop notifications when a print starts, finishes or fails")
        self.notify.setChecked(True)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        connect = QPushButton("Save and connect")
        connect.setObjectName("primary")
        disconnect = QPushButton("Disconnect")
        form = QFormLayout()
        form.addRow("Printer IP", self.ip)
        form.addRow("Serial number", self.serial)
        form.addRow("LAN access code", self.code)
        row = QHBoxLayout()
        row.addWidget(connect); row.addWidget(disconnect); row.addStretch(1)
        help_ = QLabel("On the printer: Settings → WLAN → enable LAN Only Mode. The IP address and access code are shown there; "
                       "the serial number is under Device. The access code is stored in your system keyring, never in this app's files.")
        help_.setWordWrap(True)
        help_.setObjectName("muted")
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self.status)
        lay.addWidget(self.notify)
        lay.addWidget(help_)
        lay.addStretch(1)
        connect.clicked.connect(self.save_and_connect)
        disconnect.clicked.connect(bridge.disconnect_)
        bridge.connectionChanged.connect(lambda ok, msg: self.status.setText(msg))

    def current(self) -> config.PrinterConfig | None:
        if not (self.ip.text().strip() and self.serial.text().strip() and self.code.text().strip()):
            return None
        return config.PrinterConfig(self.ip.text().strip(), self.serial.text().strip(), self.code.text().strip())

    def save_and_connect(self) -> None:
        cfg = self.current()
        if cfg is None:
            self.status.setText("Fill in the IP, serial number and access code.")
            return
        config.save(cfg)
        self.status.setText("Connecting…")
        self.bridge.connect_to(cfg)
