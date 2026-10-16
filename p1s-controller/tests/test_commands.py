import json

import pytest

from p1s_controller import commands
from p1s_controller.mqtt_client import ControlDisabled, MqttClient


def test_payloads_are_json_serialisable():
    for payload in (
        commands.pushall(), commands.pause(), commands.resume(), commands.stop(),
        commands.light(True), commands.print_speed("sport"), commands.set_bed_temp(60),
        commands.project_file("a.gcode.3mf", ams_mapping=[0, 1]),
    ):
        json.dumps(payload)


def test_temperature_limits():
    with pytest.raises(ValueError):
        commands.set_nozzle_temp(400)
    with pytest.raises(ValueError):
        commands.set_bed_temp(-1)
    assert "M104 S210" in commands.set_nozzle_temp(210)["print"]["param"]


def test_project_file_fields():
    p = commands.project_file("benchy.gcode.3mf", plate=2, ams_mapping=[3])["print"]
    assert p["param"] == "Metadata/plate_2.gcode"
    assert p["subtask_name"] == "benchy"
    assert p["url"] == "file:///sdcard/benchy.gcode.3mf"
    assert p["ams_mapping"] == [3]


def test_bad_speed_and_light_node():
    with pytest.raises(ValueError):
        commands.print_speed(9)
    with pytest.raises(ValueError):
        commands.light(True, node="bogus")


def test_read_only_client_refuses_control(monkeypatch):
    c = MqttClient("127.0.0.1", "SERIAL123456", "code")
    published = []
    monkeypatch.setattr(c._client, "publish", lambda topic, payload: published.append((topic, payload)))
    with pytest.raises(ControlDisabled):
        c.send(commands.stop())
    assert published == []
    c.request_status()  # status requests are always allowed
    assert published and published[0][0] == "device/SERIAL123456/request"


def test_control_client_publishes(monkeypatch):
    c = MqttClient("127.0.0.1", "SERIAL123456", "code", allow_control=True)
    published = []
    monkeypatch.setattr(c._client, "publish", lambda topic, payload: published.append((topic, payload)))
    c.send(commands.pause())
    assert json.loads(published[0][1])["print"]["command"] == "pause"


def test_incoming_message_updates_state():
    c = MqttClient("127.0.0.1", "SERIAL123456", "code")
    seen = []
    c.on_update = seen.append

    class Msg:
        topic = "device/SERIAL123456/report"
        payload = json.dumps({"print": {"mc_percent": 42}}).encode()

    c._on_message(None, None, Msg())
    assert c.state.percent == 42 and seen
