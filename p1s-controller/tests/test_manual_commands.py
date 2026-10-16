import pytest

from p1s_controller import commands


def gcode(payload):
    return payload["print"]["param"]


def test_move_builds_relative_move_and_restores_absolute():
    assert gcode(commands.move("x", -10, 3000)) == "G91\nG1 X-10 F3000\nG90\n"
    assert gcode(commands.move("Z", 0.1, 600)) == "G91\nG1 Z0.1 F600\nG90\n"


@pytest.mark.parametrize("axis,mm,feed", [("E", 1, 3000), ("X", 0, 3000), ("X", 101, 3000),
                                          ("Z", 1, 3000), ("X", 1, 10)])
def test_move_rejects_unsafe(axis, mm, feed):
    with pytest.raises(ValueError):
        commands.move(axis, mm, feed)


def test_fans():
    assert gcode(commands.set_fan("part", 100)) == "M106 P1 S255\n"
    assert gcode(commands.set_fan("chamber", 50)) == "M106 P3 S128\n"
    with pytest.raises(ValueError):
        commands.set_fan("bogus", 10)
    with pytest.raises(ValueError):
        commands.set_fan("aux", 101)


def test_extrude_requires_hot_nozzle():
    with pytest.raises(ValueError, match="too cold"):
        commands.extrude(5, 25)
    assert gcode(commands.extrude(-5, 220)) == "M83\nG1 E-5 F300\n"
    with pytest.raises(ValueError):
        commands.extrude(80, 220)


def test_home_and_level():
    assert gcode(commands.home()) == "G28\n"
    assert gcode(commands.auto_bed_level()) == "G29\n"


def test_ams_load_unload():
    p = commands.ams_load(5)["print"]
    assert p["command"] == "ams_change_filament" and p["target"] == 5
    assert commands.ams_unload()["print"]["target"] == 255
    with pytest.raises(ValueError):
        commands.ams_load(16)
