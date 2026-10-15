import zipfile

import numpy as np

from p1s_controller import plate, threemf

MODEL = """<?xml version="1.0"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" unit="millimeter">
 <resources>
  <object id="2" type="model"><components>
    <component p:path="/3D/Objects/o.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 5 0 0"/>
  </components></object>
 </resources>
 <build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 100 50 2" printable="1"/></build>
</model>"""

OBJ = """<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources>
 <object id="1" type="model"><mesh>
  <vertices><vertex x="0" y="0" z="0"/><vertex x="10" y="0" z="0"/><vertex x="0" y="20" z="0"/><vertex x="0" y="0" z="30"/></vertices>
  <triangles><triangle v1="0" v2="1" v3="2"/><triangle v1="0" v2="1" v3="3"/></triangles>
 </mesh></object></resources></model>"""

SETTINGS = '{"printer_model": "Bambu Lab P1S", "nozzle_diameter": ["0.4"], "layer_height": "0.2", "wall_loops": "3", ' \
           '"sparse_infill_density": "15%", "printable_area": ["0x0", "256x0", "256x256", "0x256"], ' \
           '"filament_colour": ["#FF8800"]}'


def make(tmp_path):
    p = tmp_path / "p.3mf"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("3D/3dmodel.model", MODEL)
        z.writestr("3D/Objects/o.model", OBJ)
        z.writestr("Metadata/project_settings.config", SETTINGS)
    return p


def test_meshes_are_placed_with_component_and_item_transforms(tmp_path):
    (mesh,) = threemf.read_meshes(make(tmp_path))
    assert mesh.verts.min(axis=0).tolist() == [105, 50, 2]  # component +5 x, item (100, 50, 2)
    assert mesh.verts.max(axis=0).tolist() == [115, 70, 32]
    assert mesh.tris.shape == (2, 3)


def test_unsliced_project_reads_leniently_and_exposes_settings(tmp_path):
    p = make(tmp_path)
    info = threemf.read(p, require_gcode=False)
    assert not info.sliced and info.printer == "Bambu Lab P1S"
    assert (info.layer_height, info.walls, info.nozzle, info.bed) == (0.2, 3, "0.4", (256.0, 256.0))
    assert info.filament_colors == ["FF8800"]


def test_fit_report():
    ok = plate.fit_report(np.array([10, 20, 0]), np.array([60, 80, 30]))
    assert ok.fits and ok.margins == {"left": 10, "right": 196, "front": 20, "back": 176}
    assert ok.size == (50, 60, 30)
    bad = plate.fit_report(np.array([-5, 0, 0]), np.array([260, 10, 300]))
    assert not bad.fits and len(bad.issues) == 3  # left, right, too tall


def test_gcode_bambu_markers_and_arcs():
    from p1s_controller import gcode
    text = ("G90\nM83\n; CHANGE_LAYER\n; Z_HEIGHT: 0.2\nG1 Z2.0\nG1 X10 Y0\n"
            "G3 X0 Y10 I-10 J0 E1\n"  # quarter circle ccw round the origin
            "; CHANGE_LAYER\n; Z_HEIGHT: 0.4\nG1 Z0.4\nG1 X5 Y5 E1\n")
    g = gcode.parse(text)
    assert g.heights == [0.2, 0.4]  # the z-hop in layer 1 is not a layer
    assert len(g.layers[0]) > 3  # arc was broken into pieces
    x0, y0, x1, y1 = g.layers[0][-1]
    assert (round(x1, 6), round(y1, 6)) == (0, 10)
    assert all(abs(((s[0]) ** 2 + (s[1]) ** 2) ** 0.5 - 10) < 0.5 for s in g.layers[0])
