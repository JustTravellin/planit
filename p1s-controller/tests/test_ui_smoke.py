import os
import time
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from p1s_controller.db import Database
from p1s_controller.state import AmsTray
from p1s_controller.ui import theme
from p1s_controller.ui.bridge import PrinterBridge
from p1s_controller.ui.main_window import MainWindow
from p1s_controller.ui.send_dialog import preflight_problems
from p1s_controller import threemf

SHOTS = os.environ.get("P1S_SCREENSHOT_DIR")

REPORT = {
    "print": {
        "gcode_state": "RUNNING", "mc_percent": 42, "layer_num": 21, "total_layer_num": 50,
        "mc_remaining_time": 75, "subtask_name": "Benchy", "nozzle_temper": 219.5, "nozzle_target_temper": 220,
        "bed_temper": 59.9, "bed_target_temper": 60, "chamber_temper": 31, "spd_lvl": 2,
        "lights_report": [{"node": "chamber_light", "mode": "on"}],
        "ams": {"tray_now": "0", "ams": [{"id": "0", "tray": [
            {"id": "0", "tray_type": "PLA", "tray_color": "E53935FF", "remain": 80},
            {"id": "1", "tray_type": "PETG", "tray_color": "1E88E5FF", "remain": 12},
            {"id": "2", "tray_type": "PLA", "tray_color": "FFFFFFFF", "remain": 55},
            {"id": "3"}]}]},
    }
}

SLICE_INFO = """<config><plate><metadata key="index" value="1"/><metadata key="prediction" value="4500"/>
<metadata key="weight" value="14.2"/><filament id="1" type="PLA" color="#E53935" used_g="9.1"/>
<filament id="2" type="PETG" color="#1E88E5" used_g="5.1"/></plate></config>"""

GCODE = "G90\nM83\n" + "".join(
    f";LAYER_CHANGE\n;Z:{0.2 * (i + 1):.1f}\nG1 X{40 + i} Y40\nG1 X{200 - i} Y40 E1\nG1 X{200 - i} Y{200 - i} E1\nG1 X40 Y{200 - i} E1\nG1 X40 Y40 E1\n"
    for i in range(30))


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    folder = tmp_path / "files"
    folder.mkdir()
    with zipfile.ZipFile(folder / "benchy.gcode.3mf", "w") as z:
        z.writestr("Metadata/slice_info.config", SLICE_INFO)
        z.writestr("Metadata/plate_1.gcode", GCODE)
    (folder / "plain.3mf").write_bytes(b"not a zip")
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    settings.setValue("library/folder", str(folder))
    monkeypatch.setattr("p1s_controller.ui.library.QSettings", lambda *a, **k: settings)
    monkeypatch.setattr("p1s_controller.config.load", lambda *a, **k: None)
    db = Database()
    bridge = PrinterBridge(db)
    w = MainWindow(bridge, db)
    w.resize(1200, 780)
    w.show()
    return w


def shot(window, name):
    if SHOTS:
        QApplication.processEvents()
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        window.grab().save(str(Path(SHOTS) / f"{name}.png"))


def test_dashboard_shows_live_state(window, app):
    d = window.dashboard
    t0 = time.time() - 125
    for i in range(120):  # fake two minutes of history so the graph has a line
        d.graph.add_sample(25 + min(i, 100) * 1.95, 22 + min(i, 80) * 0.48, 24 + i * 0.06, 220, 60, now=t0 + i)
    window.bridge._ingest(REPORT)
    assert d.state_badge.text() == "RUNNING"
    assert d.job_name.text() == "Benchy"
    assert d.progress.value() == 42
    assert "Layer 21/50" in d.detail.text() and "1h 15m" in d.detail.text()
    assert "220" in d.temp_label.text()
    assert d.light_btn.text() == "Light off"
    assert not d.pause_btn.isEnabled()  # control is off by default
    shot(window, "dashboard")


def test_control_gating(window, app):
    b = window.bridge
    b.connected = True
    b._ingest(REPORT)
    assert not window.dashboard.stop_btn.isEnabled()
    b.set_allow_control(True)
    assert window.dashboard.stop_btn.isEnabled() and window.dashboard.pause_btn.isEnabled()
    with pytest.raises(RuntimeError):  # no client connected
        b.send({"print": {"command": "pause"}})


def test_event_and_history(window, app):
    events = []
    window.bridge.event.connect(lambda e, j: events.append(e))
    window.bridge._ingest({"print": {"gcode_state": "IDLE"}})
    window.bridge._ingest(REPORT)
    done = {"print": {"gcode_state": "FINISH"}}
    window.bridge._ingest(done)
    assert events == ["started", "finished"]
    assert window.history.table.rowCount() == 1
    assert "1 prints" in window.history.stats.text()
    shot(window, "history")


def test_library_and_preview(window, app):
    lib = window.library
    assert lib.list.count() == 1  # plain.3mf is skipped
    lib.list.setCurrentRow(0)
    assert "Benchy".lower() in lib.title.text().lower() or "benchy" in lib.title.text()
    assert "PETG" in lib.details.text()
    lib.tags.setText("test, gift")
    lib.tags.editingFinished.emit()
    lib.search.setText("gift")
    assert not lib.list.item(0).isHidden()
    lib.search.setText("nomatch")
    assert lib.list.item(0).isHidden()
    lib.search.setText("")
    from p1s_controller import gcode
    lib.preview.set_layers(gcode.parse(threemf.read_gcode(Path(lib.current_path()))))
    assert lib.preview.slider.maximum() == 29
    lib.preview.slider.setValue(10)
    assert "Layer 11/30" in lib.preview.label.text()
    window.tabs.setCurrentWidget(lib)
    shot(window, "library")


def test_filament_tab_assign_and_refresh(window, app):
    window.db.add_spool("Red PLA", "PLA", "E53935", initial_g=800)
    window.bridge._ingest(REPORT)
    window.filament.refresh()
    assert window.filament.table.rowCount() == 1
    combo = window.filament.table.cellWidget(0, 4)
    assert combo.count() == 5  # none + 4 slots
    window.tabs.setCurrentWidget(window.filament)
    shot(window, "filament")


def test_preflight_problems():
    fils = [threemf.FileFilament(1, "PLA", "FF0000"), threemf.FileFilament(2, "PETG", "00FF00")]
    trays = [AmsTray(0, 0, "PLA", "FF0000", 80), AmsTray(0, 1, "PLA", "00FF00", 10), AmsTray(0, 2)]
    assert preflight_problems(fils, [0, 1], trays) == [
        "Slot 2 holds PLA, file wants PETG.", "Slot 2 is low (10% left)."]
    assert preflight_problems(fils, [0, 2], trays) == ["Slot 3 is empty."]
    assert preflight_problems(fils, [0, None], trays) == ["Filament 2 (PETG) has no slot chosen."]
    assert preflight_problems(fils, [0, 0], trays)[-1].startswith("The same slot")


def test_terminal_requires_control(window, app):
    t = window.terminal
    assert not t.input.isEnabled()
    window.bridge.connected = True
    window.bridge.set_allow_control(True)
    assert t.input.isEnabled()
