from p1s_controller.health import HealthMonitor
from p1s_controller.state import PrinterState


def st(**fields):
    s = PrinterState()
    s.update({"print": fields})
    return s


def test_hms_code_format_and_dedup():
    s = st(hms=[{"attr": 0x03000100, "code": 0x00010001}])
    assert s.hms_codes == ["0300_0100_0001_0001"]
    m = HealthMonitor()
    a = m.observe(s)
    assert len(a) == 1 and "0300_0100_0001_0001" in a[0].title and a[0].severity == "error"
    assert m.observe(s) == []  # same code: no repeat
    assert m.observe(st(hms=[])) == []
    assert len(m.observe(s)) == 1  # cleared then returned: alert again


def test_print_error_alert_once():
    m = HealthMonitor()
    assert m.observe(st(print_error=0)) == []
    a = m.observe(st(print_error=0x0500C011))
    assert len(a) == 1 and "0500C011" in a[0].title
    assert m.observe(st(print_error=0x0500C011)) == []


def test_low_filament_only_for_active_tray():
    ams = {"tray_now": "1", "ams": [{"id": "0", "tray": [
        {"id": "0", "tray_type": "PLA", "remain": 3},
        {"id": "1", "tray_type": "PETG", "remain": 4}]}]}
    m = HealthMonitor()
    a = m.observe(st(ams=ams))
    assert len(a) == 1 and "slot 2" in a[0].title
    assert m.observe(st(ams=ams)) == []


def test_temperature_deviation_only_while_printing():
    m = HealthMonitor()
    assert m.observe(st(gcode_state="RUNNING", layer_num=0, nozzle_temper=100, nozzle_target_temper=220)) == []
    a = m.observe(st(gcode_state="RUNNING", layer_num=5, nozzle_temper=150, nozzle_target_temper=220))
    assert len(a) == 1 and a[0].severity == "warning"
    assert m.observe(st(gcode_state="RUNNING", layer_num=5, nozzle_temper=150, nozzle_target_temper=220)) == []


def test_wifi():
    m = HealthMonitor()
    assert st(wifi_signal="-80dBm").wifi_dbm == -80
    assert len(m.observe(st(wifi_signal="-80dBm"))) == 1
    assert m.observe(st(wifi_signal="-80dBm")) == []
    assert m.observe(st(wifi_signal="garbage")) == []


def test_firmware_modules_from_info_reply():
    s = PrinterState()
    s.update({"info": {"command": "get_version", "module": [
        {"name": "ota", "sw_ver": "01.08.02.00"}, {"name": "ams/0", "sw_ver": "00.00.06.49"}]}})
    assert s.modules == {"ota": "01.08.02.00", "ams/0": "00.00.06.49"}
