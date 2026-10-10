from p1s_controller.state import PrinterState

FULL = {
    "print": {
        "gcode_state": "RUNNING",
        "mc_percent": 12,
        "layer_num": 5,
        "total_layer_num": 100,
        "mc_remaining_time": 90,
        "subtask_name": "benchy",
        "nozzle_temper": 219.6,
        "nozzle_target_temper": 220,
        "bed_temper": 59.8,
        "bed_target_temper": 60,
        "cooling_fan_speed": "15",
        "lights_report": [{"node": "chamber_light", "mode": "on"}],
        "ams": {
            "tray_now": "1",
            "ams": [
                {
                    "id": "0",
                    "tray": [
                        {"id": "0", "tray_type": "PLA", "tray_color": "FF0000FF", "remain": 80},
                        {"id": "1", "tray_type": "PETG", "tray_color": "00FF00FF", "remain": 50},
                        {"id": "2"},
                        {"id": "3"},
                    ],
                }
            ],
        },
    }
}


def test_full_report():
    s = PrinterState()
    s.update(FULL)
    assert s.gcode_state == "RUNNING"
    assert s.percent == 12 and s.layer == 5 and s.total_layers == 100
    assert s.remaining_minutes == 90
    assert s.nozzle_temp == 219.6 and s.bed_target == 60
    assert s.fans["part"] == 15
    assert s.chamber_light_on is True
    trays = s.ams_trays
    assert [t.material for t in trays] == ["PLA", "PETG", "", ""]
    assert trays[0].color == "FF0000" and trays[2].empty
    assert s.active_tray == 1


def test_partial_report_merges():
    s = PrinterState()
    s.update(FULL)
    s.update({"print": {"mc_percent": 13, "ams": {"ams": [{"id": "0", "tray": [{"id": "0", "remain": 79}]}]}}})
    assert s.percent == 13
    assert s.layer == 5  # untouched fields survive
    t0 = s.ams_trays[0]
    assert t0.remain == 79 and t0.material == "PLA"  # tray merged by id
    assert len(s.ams_trays) == 4


def test_ignores_non_print_messages():
    s = PrinterState()
    s.update({"info": {"command": "get_version"}})
    assert s.gcode_state == "UNKNOWN"


def test_tray_now_unloaded():
    s = PrinterState()
    s.update({"print": {"ams": {"tray_now": "255"}}})
    assert s.active_tray is None
