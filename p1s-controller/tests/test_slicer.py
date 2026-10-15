import json
import zipfile
from pathlib import Path

import pytest

from p1s_controller import advice, plate, slicer


def tree(tmp_path) -> Path:
    root = tmp_path / "BBL"
    for kind in ("machine", "process", "filament"):
        (root / kind).mkdir(parents=True)

    def put(kind, **j):
        (root / kind / f"{j['name']}.json").write_text(json.dumps(j))

    put("machine", name="common", nozzle_diameter=["0.4"], curr_bed_type="Cool Plate")
    put("machine", name="Bambu Lab P1S 0.4 nozzle", inherits="common", instantiation="true")
    put("process", name="base", layer_height="0.2", wall_loops="2", sparse_infill_density="15%")
    for n in ("0.20mm Standard @BBL X1C", "0.08mm Extra Fine @BBL X1C"):
        put("process", name=n, inherits="base", instantiation="true", compatible_printers=["Bambu Lab P1S 0.4 nozzle"])
    put("process", name="0.20mm Standard @BBL A1", instantiation="true", compatible_printers=["Bambu Lab A1 0.4 nozzle"])
    for n in ("Bambu PLA Basic @BBL P1S 0.4 nozzle", "Bambu PLA Matte @BBL X1C", "Generic PLA", "Generic PETG"):
        put("filament", name=n, instantiation="true", compatible_printers=["Bambu Lab P1S 0.4 nozzle"])
    return root


def test_presets_are_p1s_only_and_sorted_by_layer_height(tmp_path):
    root = tree(tmp_path)
    assert slicer.process_presets(root) == ["0.08mm Extra Fine @BBL X1C", "0.20mm Standard @BBL X1C"]
    assert "Generic PETG" in slicer.filament_presets(root)


def test_flatten_merges_inherits_chain(tmp_path):
    flat = slicer.flatten(tree(tmp_path), "process", "0.20mm Standard @BBL X1C")
    assert flat["wall_loops"] == "2" and "inherits" not in flat


def test_suggest_filament_prefers_bambu_product_then_generic(tmp_path):
    fp = slicer.filament_presets(tree(tmp_path))
    assert slicer.suggest_filament("PLA", "PLA Basic", fp) == "Bambu PLA Basic @BBL P1S 0.4 nozzle"
    assert slicer.suggest_filament("PLA", "PLA Matte", fp) == "Bambu PLA Matte @BBL X1C"
    assert slicer.suggest_filament("PETG", "", fp) == "Generic PETG"
    assert slicer.suggest_filament("ABS", "", fp) is None


def test_apply_settings_writes_overrides(tmp_path):
    root = tree(tmp_path)
    work = tmp_path / "w"
    work.mkdir()
    s = slicer.Settings(filaments=["Generic PLA"], colors=["D3B7A7"], infill="25%", walls=4, supports=True,
                        bed_type="Textured PEI Plate", brim=True, reduce_purge=True)
    arg, fils = slicer.apply_settings(root, s, work)
    machine_file, process_file = arg.split(";")
    assert json.loads(Path(machine_file).read_text())["curr_bed_type"] == "Textured PEI Plate"
    p = json.loads(Path(process_file).read_text())
    assert (p["sparse_infill_density"], p["wall_loops"], p["enable_support"], p["brim_type"]) == ("25%", "4", "1", "auto_brim")
    assert p["flush_multiplier"] == "0.6"
    assert json.loads(Path(fils[0]).read_text())["filament_colour"] == ["#D3B7A7"]


def test_command_and_output_path(tmp_path):
    exe = slicer.Slicer("t", tmp_path / "bambu-studio.exe")
    cmd = slicer.build_command(exe, tmp_path / "a.stl", tmp_path / "o", "m.json;p.json", ["f.json"], True)
    assert cmd[1:5] == ["--slice", "0", "--arrange", "1"] and cmd[-1].endswith("a.stl")
    assert slicer.output_path(tmp_path / "Case.3mf").name == "Case.gcode.3mf"
    assert slicer.output_path(tmp_path / "x.stl").name == "x.gcode.3mf"
    assert slicer.output_path(tmp_path / "Case.gcode.3mf").name == "Case (P1S).gcode.3mf"


def test_arrange_only_without_bambu_placement(tmp_path):
    plain, project = tmp_path / "a.3mf", tmp_path / "b.3mf"
    zipfile.ZipFile(plain, "w").writestr("3D/3dmodel.model", "<model/>")
    zipfile.ZipFile(project, "w").writestr("Metadata/model_settings.config", "<config/>")
    assert slicer.needs_arrange(plain) and not slicer.needs_arrange(project) and slicer.needs_arrange(tmp_path / "x.stl")


def test_missing_slicer_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(slicer, "find_slicer", lambda: None)
    with pytest.raises(slicer.SliceError, match="not installed"):
        slicer.slice_model(tmp_path / "a.stl", tmp_path / "o.gcode.3mf", slicer.Settings())


def test_real_slice_when_bambu_studio_is_installed(tmp_path):
    sl = slicer.find_slicer()
    if sl is None:
        pytest.skip("Bambu Studio not installed")
    stl = tmp_path / "cube.stl"
    tris = []
    for x, y, z in ((0, 0, 0),):
        v = [(x + a, y + b, z + c) for a in (0, 10) for b in (0, 10) for c in (0, 10)]
        quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for a, b, c, d in quads:
            tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    stl.write_text("solid c\n" + "".join(
        "facet normal 0 0 0\nouter loop\n" + "".join(f"vertex {p[0]} {p[1]} {p[2]}\n" for p in t) + "endloop\nendfacet\n"
        for t in tris) + "endsolid c\n")
    fp = slicer.filament_presets(sl.profiles)
    r = slicer.slice_model(stl, tmp_path / "cube.gcode.3mf", slicer.Settings(filaments=[slicer.suggest_filament("PLA", "", fp)]), sl)
    assert r.layers == 50 and r.seconds > 0 and r.path.is_file()


def test_advice_rules():
    texts = lambda *a, **k: " ".join(t for _, t in advice.advise(*a, **k))
    assert advice.material_of("Bambu PLA-CF @BBL X1C") == "PLA" and advice.abrasive("Bambu PLA-CF @BBL X1C")
    assert not advice.abrasive("Bambu PLA Basic @BBL P1S 0.4 nozzle")
    assert "abrasive" in texts(["Bambu PA-CF @BBL X1C"], nozzle_type="stainless_steel")
    assert not any(s == "error" for s, _ in advice.advise(["Bambu PA-CF @BBL X1C"], nozzle_type="hardened_steel"))
    assert "fumes" in texts(["Generic ABS"]) and "too soft for the AMS" in texts(["Bambu TPU 95A @BBL X1C"])
    assert "textured" in texts(["Generic PETG"])
    bad = plate.fit_report([-5, 0, 0], [10, 10, 10])
    assert advice.advise(["Generic PLA"], fit=bad)[0][0] == "error"
