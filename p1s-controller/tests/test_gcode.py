from p1s_controller import gcode

SAMPLE = """; header
G90
M83
;LAYER_CHANGE
;Z:0.2
G1 Z0.2 F900
G1 X10 Y10 F3000
G1 X20 Y10 E0.5
G1 X20 Y20 E0.5
G1 X5 Y5
;LAYER_CHANGE
;Z:0.4
G1 Z0.4
G1 X30 Y30 E0.3 ; extrude
"""


def test_marker_layers():
    g = gcode.parse(SAMPLE)
    assert len(g.layers) == 2
    assert g.heights == [0.2, 0.4]
    assert g.layers[0] == [(10.0, 10.0, 20.0, 10.0), (20.0, 10.0, 20.0, 20.0)]  # travel excluded
    assert g.layers[1] == [(5.0, 5.0, 30.0, 30.0)]
    assert g.bounds == (5.0, 5.0, 30.0, 30.0)


def test_z_change_layers_absolute_extrusion():
    text = "G90\nM82\nG92 E0\nG1 Z0.2\nG1 X1 Y1 E1\nG1 X2 Y1 E2\nG1 Z0.4\nG1 X3 Y3 E3\nG92 E0\nG1 X4 Y4 E1\n"
    g = gcode.parse(text)
    assert len(g.layers) == 2 and g.heights == [0.2, 0.4]
    assert len(g.layers[0]) == 2 and len(g.layers[1]) == 2


def test_relative_xyz():
    g = gcode.parse("G91\nM83\nG1 X5 Y0 E1\nG1 X0 Y5 E1\n")
    assert g.layers[0] == [(0.0, 0.0, 5.0, 0.0), (5.0, 0.0, 5.0, 5.0)]


def test_empty_and_malformed():
    assert gcode.parse("").layers == []
    assert gcode.parse("G1 Xabc Y5 E1\n").layers[0] == [(0.0, 0.0, 0.0, 5.0)]
