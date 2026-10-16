from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QWidget,
                               QHBoxLayout, QVBoxLayout)

from .. import config, notify
from .bridge import PrinterBridge


class SettingsTab(QWidget):
    wizardRequested = Signal()
    notifyChanged = Signal(object)  # notify.NotifyConfig

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
        wizard = QPushButton("Setup wizard…")
        wizard.clicked.connect(self.wizardRequested)
        form = QFormLayout()
        form.addRow("Printer IP", self.ip)
        form.addRow("Serial number", self.serial)
        form.addRow("LAN access code", self.code)
        row = QHBoxLayout()
        row.addWidget(connect); row.addWidget(disconnect); row.addWidget(wizard); row.addStretch(1)
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
        lay.addWidget(self._notify_box())
        lay.addStretch(1)
        connect.clicked.connect(self.save_and_connect)
        disconnect.clicked.connect(bridge.disconnect_)
        bridge.connectionChanged.connect(lambda ok, msg: self.status.setText(msg))

    def _notify_box(self) -> QGroupBox:
        cfg = config.load_notify()
        box = QGroupBox("Phone and chat notifications")
        self.n_kind = QComboBox()
        self.n_kind.addItem("Off", "")
        for kind, label in (("telegram", "Telegram bot"), ("discord", "Discord webhook"), ("ntfy", "ntfy"),
                            ("webhook", "Generic webhook (JSON)")):
            self.n_kind.addItem(label, kind)
        self.n_kind.setCurrentIndex(max(0, self.n_kind.findData(cfg.kind)))
        self.n_target = QLineEdit(cfg.target)
        self.n_secret = QLineEdit(cfg.secret)
        self.n_secret.setEchoMode(QLineEdit.Password)
        self.n_events = {e: QCheckBox(e) for e in notify.ALL_EVENTS}
        for e, box_ in self.n_events.items():
            box_.setChecked(e in cfg.events)
        self.n_status = QLabel("")
        self.n_status.setObjectName("muted")
        self.n_status.setWordWrap(True)
        save = QPushButton("Save")
        test = QPushButton("Send test message")
        form = QFormLayout()
        form.addRow("Service", self.n_kind)
        form.addRow("Chat ID / topic URL", self.n_target)
        form.addRow("Bot token / webhook URL", self.n_secret)
        events = QHBoxLayout()
        for b in self.n_events.values():
            events.addWidget(b)
        events.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(save)
        row.addWidget(test)
        row.addStretch(1)
        lay = QVBoxLayout(box)
        lay.addLayout(form)
        lay.addLayout(events)
        lay.addLayout(row)
        lay.addWidget(self.n_status)
        hint = QLabel("Telegram: create a bot with @BotFather, paste its token, and your chat ID. Discord: paste a channel "
                      "webhook URL. ntfy: paste your topic URL (https://ntfy.sh/your-topic). Messages go to that service "
                      "over HTTPS. The token is stored in your system keyring. Health alerts are always sent.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self._update_labels()
        self.n_kind.currentIndexChanged.connect(self._update_labels)
        save.clicked.connect(self.save_notify)
        test.clicked.connect(self.test_notify)
        return box

    def _update_labels(self) -> None:
        kind = self.n_kind.currentData()
        self.n_target.setEnabled(kind in ("telegram", "ntfy"))
        self.n_secret.setEnabled(bool(kind))

    def notify_config(self) -> notify.NotifyConfig:
        return notify.NotifyConfig(self.n_kind.currentData() or "", self.n_target.text().strip(),
                                   self.n_secret.text().strip(), [e for e, b in self.n_events.items() if b.isChecked()])

    def save_notify(self) -> None:
        cfg = self.notify_config()
        config.save_notify(cfg)
        self.notifyChanged.emit(cfg)
        self.n_status.setText("Saved." if cfg.enabled else "Saved. Notifications are off or incomplete.")

    def test_notify(self) -> None:
        cfg = self.notify_config()
        if not cfg.enabled:
            self.n_status.setText("Fill in the service details first.")
            return
        try:
            notify.send(cfg, "P1S Controller", "Test message. If you can read this, notifications work.")
            self.n_status.setText("Test message sent.")
        except Exception as exc:
            self.n_status.setText(f"Could not send: {exc}")

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
