"""Saved printer connection settings.

IP and serial live in a JSON file in the user's config directory. The LAN access
code is a credential, so it goes in the OS keyring when one is available and falls
back to a 0600 file otherwise.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

_KEYRING_SERVICE = "p1s-controller"


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "p1s-controller"


@dataclass
class PrinterConfig:
    ip: str
    serial: str
    access_code: str


def _keyring():
    try:
        import keyring
        from keyring.errors import KeyringError  # noqa: F401

        backend = keyring.get_keyring()
        if backend.priority <= 0:  # fail.Keyring / null backend
            return None
        return keyring
    except Exception:
        return None


def save(cfg: PrinterConfig, directory: Path | None = None) -> None:
    directory = directory or config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    meta = {"ip": cfg.ip, "serial": cfg.serial}
    kr = _keyring()
    stored_in_keyring = False
    if kr is not None:
        try:
            kr.set_password(_KEYRING_SERVICE, cfg.serial, cfg.access_code)
            stored_in_keyring = True
        except Exception:
            stored_in_keyring = False
    if not stored_in_keyring:
        meta["access_code"] = cfg.access_code
    path = directory / "config.json"
    path.write_text(json.dumps(meta, indent=2))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load(directory: Path | None = None) -> PrinterConfig | None:
    path = (directory or config_dir()) / "config.json"
    if not path.exists():
        return None
    meta = json.loads(path.read_text())
    code = meta.get("access_code")
    if code is None:
        kr = _keyring()
        if kr is not None:
            code = kr.get_password(_KEYRING_SERVICE, meta["serial"])
    if not code:
        return None
    return PrinterConfig(ip=meta["ip"], serial=meta["serial"], access_code=code)


def as_dict(cfg: PrinterConfig) -> dict:
    return asdict(cfg)
