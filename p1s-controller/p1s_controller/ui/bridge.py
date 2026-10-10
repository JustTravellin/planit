"""Qt wrapper around MqttClient: keeps network threads away from widgets."""
from __future__ import annotations

import copy
import threading

from PySide6.QtCore import QObject, Signal

from ..config import PrinterConfig
from ..db import Database
from ..history import HistoryRecorder
from ..mqtt_client import ControlDisabled, MqttClient
from ..state import PrinterState


class PrinterBridge(QObject):
    stateChanged = Signal(object)          # PrinterState snapshot
    event = Signal(str, str)               # event name, job name
    connectionChanged = Signal(bool, str)  # connected, message
    controlChanged = Signal(bool)
    rawMessage = Signal(dict)
    _rawIn = Signal(dict)
    _connIn = Signal(bool, str)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.state = PrinterState()
        self.recorder = HistoryRecorder(db)
        self.client: MqttClient | None = None
        self.config: PrinterConfig | None = None
        self.connected = False
        self._allow_control = False
        self._rawIn.connect(self._ingest)
        self._connIn.connect(self._on_connection)

    # --- connection ----------------------------------------------------------
    def connect_to(self, cfg: PrinterConfig) -> None:
        self.disconnect_()
        self.config = cfg
        client = MqttClient(cfg.ip, cfg.serial, cfg.access_code, allow_control=self._allow_control)
        client.on_raw = self._rawIn.emit
        client.on_connection = self._connIn.emit
        self.client = client

        def run() -> None:
            try:
                client.connect()
            except OSError as exc:
                self._connIn.emit(False, f"Could not reach {cfg.ip}: {exc}")

        threading.Thread(target=run, daemon=True).start()

    def disconnect_(self) -> None:
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None
        self._on_connection(False, "Disconnected")

    def _on_connection(self, ok: bool, message: str) -> None:
        self.connected = ok
        self.connectionChanged.emit(ok, message)

    # --- data in -------------------------------------------------------------
    def _ingest(self, report: dict) -> None:
        self.rawMessage.emit(report)
        self.state.update(report)
        if "print" not in report:
            return
        snapshot = PrinterState(raw=copy.deepcopy(self.state.raw))
        name = self.recorder.observe(snapshot)
        self.stateChanged.emit(snapshot)
        if name:
            self.event.emit(name, snapshot.job_name)

    # --- control -------------------------------------------------------------
    @property
    def allow_control(self) -> bool:
        return self._allow_control

    def set_allow_control(self, allowed: bool) -> None:
        self._allow_control = allowed
        if self.client is not None:
            self.client.allow_control = allowed
        self.controlChanged.emit(allowed)

    def send(self, payload: dict) -> None:
        if self.client is None or not self.connected:
            raise RuntimeError("Not connected to the printer.")
        if not self._allow_control:
            raise ControlDisabled("Control is turned off. Tick 'Allow control' first.")
        self.client.send(payload)
