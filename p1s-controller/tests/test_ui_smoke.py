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
    lib.preview.wait()
    assert lib.preview.slider.maximum() == 29 and lib.preview.sliced_btn.isEnabled()
    assert lib.send_btn.isEnabled() and "Sliced and ready" in lib.status.text()
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


# ---- new tabs: control, health, camera, wizard ---------------------------------

class FakeClient:
    def __init__(self):
        self.sent = []
        self.allow_control = True

    def send(self, payload):
        self.sent.append(payload)

    def disconnect(self):
        pass


def connect_fake(window, allow=True):
    b = window.bridge
    b.client = FakeClient()
    b.connected = True
    b.set_allow_control(allow)
    return b.client


def test_control_tab_gating_and_jog(window, app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a[2])))
    c = window.control
    idle = {"print": {**REPORT["print"], "gcode_state": "IDLE", "nozzle_temper": 25}}
    window.bridge._ingest(idle)
    assert not c.home_btn.isEnabled()  # not connected, control off
    client = connect_fake(window)
    window.bridge._ingest(idle)
    assert c.home_btn.isEnabled() and all(b.isEnabled() for b in c.jog_buttons)

    c.jog_buttons[0].click()  # Y+ with default 1 mm step
    assert client.sent[-1]["print"]["param"] == "G91\nG1 Y1 F3000\nG90\n"
    c.home_btn.click()
    assert client.sent[-1]["print"]["param"] == "G28\n"
    c.fan_sliders["part"].setValue(50)
    c.fan_sliders["part"].sliderReleased.emit()
    assert client.sent[-1]["print"]["param"] == "M106 P1 S128\n"
    n = len(client.sent)
    c.extrude_btn.click()  # nozzle is 25 C: must be refused, with a warning box
    assert len(client.sent) == n and "too cold" in warnings[-1]

    load_buttons = [b for row in c._ams_rows for b in row.findChildren(type(c.home_btn)) if b.text() == "Load"]
    assert len(load_buttons) == 4 and load_buttons[0].isEnabled() and not load_buttons[3].isEnabled()  # slot 4 empty
    load_buttons[1].click()
    assert client.sent[-1]["print"]["command"] == "ams_change_filament" and client.sent[-1]["print"]["target"] == 1

    window.bridge._ingest(REPORT)  # RUNNING
    assert not c.home_btn.isEnabled() and not any(b.isEnabled() for b in c.jog_buttons)
    assert c.fan_sliders["part"].isEnabled()  # fans still allowed
    assert "disabled while a print" in c.note.text()
    window.tabs.setCurrentWidget(c)
    shot(window, "control")


def test_health_tab_shows_alerts_and_firmware(window, app):
    report = {"print": {**REPORT["print"], "hms": [{"attr": 0x03000100, "code": 0x00010001}],
                        "wifi_signal": "-82dBm"}}
    window.bridge._ingest(report)
    window.bridge._ingest({"info": {"command": "get_version", "module": [
        {"name": "ota", "sw_ver": "01.08.02.00"}, {"name": "ams/0", "sw_ver": "00.00.06.49"}]}})
    h = window.health
    titles = [h.alerts.item(r, 1).text() for r in range(h.alerts.rowCount())]
    assert any("0300_0100_0001_0001" in t for t in titles)
    assert any("Weak Wi-Fi" in t for t in titles)
    assert h.fw.rowCount() == 2 and h.fw.item(0, 0).text() == "ams/0"
    assert "error" in h.summary.text()
    assert "-82" in h.info.text()
    window.tabs.setCurrentWidget(h)
    shot(window, "health")


def test_camera_view_shows_frames_and_failures(window, app):
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage
    img = QImage(640, 360, QImage.Format_RGB32)
    img.fill(QColor("#3ea6ff"))
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "JPEG")
    cam = window.dashboard.camera
    assert not cam.button.isEnabled()  # not connected yet
    window.bridge.connected = True
    window.bridge.connectionChanged.emit(True, "Connected")
    assert cam.button.isEnabled()
    cam._show_frame(bytes(buf.data()))
    assert cam.snapshot.isEnabled() and not cam.image.pixmap().isNull()
    cam._failed("ConnectionRefusedError: refused")
    assert "Camera stopped" in cam.image.text() and cam.button.text() == "Start camera"
    cam._show_frame(b"garbage")  # undecodable frames are ignored, not fatal
    window.tabs.setCurrentWidget(window.dashboard)
    shot(window, "dashboard_camera")


def test_wizard_flow(window, app, monkeypatch):
    from p1s_controller.ui import wizard
    monkeypatch.setattr(wizard, "check_connection", lambda ip, serial, code: (False, "Can't reach 1.2.3.4 on port 8883"))
    monkeypatch.setattr(wizard.config, "load", lambda *a, **k: None)
    saved = []
    monkeypatch.setattr(wizard.config, "save", lambda cfg, *a, **k: saved.append(cfg))
    connected = []
    window.bridge.connect_to = lambda cfg: connected.append(cfg)
    w = wizard.SetupWizard(window.bridge, window)
    w.show()
    assert not w.details.isComplete()
    w.details.ip.setText("192.168.1.50"); w.details.serial.setText("01P00A000000000"); w.details.code.setText("12345678")
    assert w.details.isComplete()
    w.next(); w.next()
    assert not w.test.isComplete()
    w.test.run_test()
    w.test._thread.wait(3000)
    QApplication.processEvents()
    assert "✗" in w.test.result.text() and not w.test.isComplete()
    monkeypatch.setattr(wizard, "check_connection", lambda ip, serial, code: (True, "Connected. The printer is answering."))
    w.test.run_test()
    w.test._thread.wait(3000)
    QApplication.processEvents()
    assert w.test.isComplete()
    shot(w, "wizard")
    w.accept()
    assert saved[0].ip == "192.168.1.50" and connected[0].access_code == "12345678"
