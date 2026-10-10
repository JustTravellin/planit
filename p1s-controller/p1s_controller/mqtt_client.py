"""MQTT link to the printer (LAN mode: TLS on 8883, user "bblp", access code as password)."""
from __future__ import annotations

import json
import logging
import ssl
import threading
from typing import Any, Callable

import paho.mqtt.client as mqtt

from . import commands
from .state import PrinterState

log = logging.getLogger(__name__)


class ControlDisabled(RuntimeError):
    """Raised when a state-changing command is sent while the client is read-only."""


class MqttClient:
    def __init__(self, ip: str, serial: str, access_code: str, *, allow_control: bool = False):
        self.ip = ip
        self.serial = serial
        self.allow_control = allow_control
        self.state = PrinterState()
        self.on_update: Callable[[PrinterState], None] | None = None
        self.on_raw: Callable[[dict[str, Any]], None] | None = None
        self.on_connection: Callable[[bool, str], None] | None = None
        self._first_report = threading.Event()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"p1s-controller-{serial[-6:]}")
        self._client.username_pw_set("bblp", access_code)
        # The printer uses a self-signed certificate, so we can't verify a chain.
        # Traffic is still encrypted; the access code authenticates us to the printer.
        self._client.tls_set(cert_reqs=ssl.CERT_NONE)
        self._client.tls_insecure_set(True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        self.report_topic = f"device/{serial}/report"
        self.request_topic = f"device/{serial}/request"

    # --- lifecycle ---------------------------------------------------------
    def connect(self, timeout: float = 10.0) -> None:
        self._client.connect(self.ip, 8883, keepalive=30)
        self._client.loop_start()
        if not self._first_report.wait(timeout):
            log.warning("Connected but no status report within %.0fs", timeout)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # --- callbacks ---------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            log.error("MQTT connect failed: %s", reason_code)
            if self.on_connection:
                self.on_connection(False, f"Connection refused: {reason_code}")
            return
        if self.on_connection:
            self.on_connection(True, "Connected")
        client.subscribe(self.report_topic)
        self._publish(commands.pushall())

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        if self.on_connection:
            self.on_connection(False, f"Disconnected: {reason_code}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            log.debug("Ignoring non-JSON message on %s", msg.topic)
            return
        if self.on_raw:
            self.on_raw(payload)
        self.state.update(payload)
        if "print" in payload:
            self._first_report.set()
            if self.on_update:
                self.on_update(self.state)

    # --- sending -----------------------------------------------------------
    def _publish(self, payload: dict[str, Any]) -> None:
        self._client.publish(self.request_topic, json.dumps(payload))

    def request_status(self) -> None:
        self._publish(commands.pushall())

    def send(self, payload: dict[str, Any]) -> None:
        """Send a state-changing command. Refused unless allow_control is set."""
        if not self.allow_control:
            raise ControlDisabled("This connection is read-only; enable control to send commands.")
        self._publish(payload)
