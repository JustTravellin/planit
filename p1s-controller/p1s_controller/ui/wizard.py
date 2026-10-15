from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWizard, QWizardPage)

from .. import config
from ..connection_test import check_connection
from .bridge import PrinterBridge


class _TestThread(QThread):
    done = Signal(bool, str)

    def __init__(self, ip: str, serial: str, code: str):
        super().__init__()
        self.args = (ip, serial, code)

    def run(self) -> None:
        self.done.emit(*check_connection(*self.args))


class _IntroPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Prepare the printer")
        text = QLabel(
            "<ol>"
            "<li>On the printer's screen open <b>Settings → WLAN</b> and turn on <b>LAN Only Mode</b> "
            "(and <b>Developer Mode</b> if your firmware offers it).</li>"
            "<li>Note the printer's <b>IP address</b> and the <b>access code</b> shown there.</li>"
            "<li>Open <b>Settings → Device</b> and note the <b>serial number</b>.</li>"
            "<li>Make sure this PC is on the same network as the printer.</li></ol>"
            "<p>Nothing is sent to any cloud service. The app talks directly to the printer on your network.</p>")
        text.setWordWrap(True)
        QVBoxLayout(self).addWidget(text)


class _DetailsPage(QWizardPage):
    def __init__(self, prefill: config.PrinterConfig | None):
        super().__init__()
        self.setTitle("Printer details")
        self.ip = QLineEdit(prefill.ip if prefill else "", placeholderText="192.168.1.50")
        self.serial = QLineEdit(prefill.serial if prefill else "", placeholderText="Serial number")
        self.code = QLineEdit(prefill.access_code if prefill else "", placeholderText="Access code")
        self.code.setEchoMode(QLineEdit.Password)
        form = QFormLayout(self)
        form.addRow("IP address", self.ip)
        form.addRow("Serial number", self.serial)
        form.addRow("Access code", self.code)
        for w in (self.ip, self.serial, self.code):
            w.textChanged.connect(self.completeChanged)

    def isComplete(self) -> bool:
        return all(w.text().strip() for w in (self.ip, self.serial, self.code))


class _TestPage(QWizardPage):
    def __init__(self, details: _DetailsPage):
        super().__init__()
        self.setTitle("Test the connection")
        self.details = details
        self.ok = False
        self._thread: _TestThread | None = None
        self.result = QLabel("Press the button to check the connection. This only reads from the printer.")
        self.result.setWordWrap(True)
        self.button = QPushButton("Test connection")
        lay = QVBoxLayout(self)
        lay.addWidget(self.result)
        lay.addWidget(self.button)
        self.button.clicked.connect(self.run_test)

    def run_test(self) -> None:
        self.button.setEnabled(False)
        self.result.setText("Testing…")
        d = self.details
        self._thread = _TestThread(d.ip.text().strip(), d.serial.text().strip(), d.code.text().strip())
        self._thread.done.connect(self._finished)
        self._thread.start()

    def _finished(self, ok: bool, message: str) -> None:
        self.ok = ok
        self.button.setEnabled(True)
        self.result.setText(("✓ " if ok else "✗ ") + message)
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self.ok

    def initializePage(self) -> None:
        self.ok = False
        self.result.setText("Press the button to check the connection. This only reads from the printer.")


class SetupWizard(QWizard):
    def __init__(self, bridge: PrinterBridge, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect your printer")
        self.bridge = bridge
        self.details = _DetailsPage(config.load())
        self.test = _TestPage(self.details)
        self.addPage(_IntroPage())
        self.addPage(self.details)
        self.addPage(self.test)
        self.setButtonText(QWizard.FinishButton, "Save and connect")

    def accept(self) -> None:
        cfg = config.PrinterConfig(self.details.ip.text().strip(), self.details.serial.text().strip(),
                                   self.details.code.text().strip())
        config.save(cfg)
        self.bridge.connect_to(cfg)
        super().accept()
