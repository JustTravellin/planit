import zipfile

import pytest

from p1s_controller import threemf
from p1s_controller.state import AmsTray

SLICE_INFO = """<?xml version="1.0"?>
<config><plate>
  <metadata key="index" value="1"/>
  <metadata key="prediction" value="3600"/>
  <metadata key="weight" value="12.5"/>
  <filament id="1" type="PLA" color="#FF0000" used_g="8.0"/>
  <filament id="2" type="PETG" color="#00FF00" used_g="4.5"/>
</plate></config>"""


def make(tmp_path, with_gcode=True):
    p = tmp_path / "a.gcode.3mf"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("Metadata/slice_info.config", SLICE_INFO)
        zf.writestr("Metadata/plate_1.png", b"\x89PNG-fake")
        if with_gcode:
            zf.writestr("Metadata/plate_1.gcode", "G28\n")
    return p


def test_read(tmp_path):
    info = threemf.read(make(tmp_path))
    assert info.print_seconds == 3600 and info.weight_grams == 12.5
    assert [(f.material, f.color) for f in info.filaments] == [("PLA", "FF0000"), ("PETG", "00FF00")]
    assert info.thumbnail_png.startswith(b"\x89PNG")


def test_rejects_unsliced(tmp_path):
    with pytest.raises(ValueError, match="gcode.3mf"):
        threemf.read(make(tmp_path, with_gcode=False))


def test_mapping_matches_material_and_closest_colour():
    fils = [threemf.FileFilament(1, "PLA", "FF0000"), threemf.FileFilament(2, "PLA", "0000FF")]
    trays = [
        AmsTray(0, 0, "PLA", "0000FE"),
        AmsTray(0, 1, "PLA", "FE0000"),
        AmsTray(0, 2, "PETG", "FF0000"),
        AmsTray(0, 3),
    ]
    assert threemf.suggest_ams_mapping(fils, trays) == [1, 0]


def test_mapping_none_when_material_missing():
    fils = [threemf.FileFilament(1, "ABS", "FF0000")]
    assert threemf.suggest_ams_mapping(fils, [AmsTray(0, 0, "PLA", "FF0000")]) == [None]
