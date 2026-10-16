"""Step-by-step connection check used by the setup wizard."""
from __future__ import annotations

import json
import socket
import ssl
import threading

import paho.mqtt.client as mqtt

from . import commands


def explain_reason(reason_code) -> str:
    text = str(reason_code)
    if "not authorized" in text.lower() or "bad user name" in text.lower() or getattr(reason_code, "value", None) in (4, 5, 134, 135):
        return "The printer rejected the access code. Check it on the printer's screen (Settings, WLAN)."
    return f"The printer refused the connection ({text})."


def check_connection(ip: str, serial: str, access_code: str, timeout: float = 8.0) -> tuple[bool, str]:
    """Returns (ok, message). Read-only: only subscribes and asks for a status report."""
    try:
        socket.create_connection((ip, 8883), timeout=timeout).close()
    except OSError as exc:
        return False, (f"Can't reach {ip} on port 8883 ({exc}). Check the IP address, that the printer is on, "
                       "that this PC is on the same network, and that LAN Only Mode is enabled.")

    result: dict = {}
    connected = threading.Event()
    got_report = threading.Event()

    def on_connect(client, _u, _f, reason_code, _p=None):
        result["reason"] = reason_code
        if reason_code == 0:
            client.subscribe(f"device/{serial}/report")
            client.publish(f"device/{serial}/request", json.dumps(commands.pushall()))
        connected.set()

    def on_message(_c, _u, msg):
        try:
            if "print" in json.loads(msg.payload):
                got_report.set()
        except json.JSONDecodeError:
            pass

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="p1s-controller-test")
    client.username_pw_set("bblp", access_code)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_connect, client.on_message = on_connect, on_message
    try:
        client.connect(ip, 8883, keepalive=15)
        client.loop_start()
        if not connected.wait(timeout):
            return False, "The printer didn't answer the login. Try again in a few seconds."
        if result.get("reason") != 0:
            return False, explain_reason(result["reason"])
        if not got_report.wait(timeout):
            return False, ("Logged in, but no status arrived. The serial number is probably wrong "
                           "(Settings, Device on the printer).")
        return True, "Connected. The printer is answering."
    except OSError as exc:
        return False, f"Connection failed: {exc}"
    finally:
        client.loop_stop()
        client.disconnect()
