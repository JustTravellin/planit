from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .. import config
from ..db import Database
from . import theme
from .bridge import PrinterBridge
from .main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    theme.apply(app)
    cfg_dir = config.config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    db = Database(cfg_dir / "p1s.db")
    bridge = PrinterBridge(db)
    window = MainWindow(bridge, db)
    window.show()
    saved = config.load()
    if saved:  # reconnect read-only; control stays off until the user ticks it
        window.settings.status.setText("Connecting…")
        bridge.connect_to(saved)
    else:
        window.tabs.setCurrentWidget(window.settings)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
