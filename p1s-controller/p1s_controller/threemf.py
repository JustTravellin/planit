"""Read a sliced .gcode.3mf: thumbnail, filaments, time and weight, and AMS slot mapping."""
from __future__ import annotations

import json
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .state import AmsTray


@dataclass
class FileFilament:
    index: int  # 1-based filament id in the file
    material: str
    color: str  # "RRGGBB"
    used_grams: float = 0.0


@dataclass
class PlateInfo:
    plate: int = 1
    print_seconds: int = 0
    weight_grams: float = 0.0
    filaments: list[FileFilament] = field(default_factory=list)
    thumbnail_png: bytes | None = None
    sliced: bool = True
    # from Metadata/project_settings.config (blank/0 when the file has none)
    printer: str = ""
    nozzle: str = ""
    layer_height: float = 0.0
    walls: int = 0
    infill: str = ""
    bed: tuple[float, float] = (256.0, 256.0)
    max_height: float = 256.0
    filament_colors: list[str] = field(default_factory=list)  # "RRGGBB" per extruder


@dataclass
class Mesh:
    """One object placed on the plate, vertices already in bed coordinates (mm)."""
    name: str
    verts: np.ndarray  # (n, 3) float32
    tris: np.ndarray  # (m, 3) int32
    extruder: int = 1


def read(path: str | Path, require_gcode: bool = True) -> PlateInfo:
    info = PlateInfo()
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "Metadata/slice_info.config" in names:
            _parse_slice_info(zf.read("Metadata/slice_info.config"), info)
        for name in ("Metadata/plate_1.png", "Metadata/plate_no_light_1.png"):
            if name in names:
                info.thumbnail_png = zf.read(name)
                break
        if "Metadata/project_settings.config" in names:
            _parse_settings(zf.read("Metadata/project_settings.config"), info)
        info.sliced = any(n.startswith("Metadata/plate_") and n.endswith(".gcode") for n in names)
        if require_gcode and not info.sliced:
            raise ValueError("No sliced G-code found. Export the plate as .gcode.3mf from your slicer, not a plain .3mf.")
    return info


def read_gcode(path: str | Path, plate: int = 1) -> str:
    """Return the sliced G-code text for a plate."""
    with zipfile.ZipFile(path) as zf:
        return zf.read(f"Metadata/plate_{plate}.gcode").decode("utf-8", errors="replace")


def _parse_slice_info(xml_bytes: bytes, info: PlateInfo) -> None:
    root = ET.fromstring(xml_bytes)
    plate = root.find("plate")
    if plate is None:
        return
    for meta in plate.findall("metadata"):
        key, value = meta.get("key"), meta.get("value", "")
        if key == "index":
            info.plate = int(value or 1)
        elif key == "prediction":
            info.print_seconds = int(float(value or 0))
        elif key == "weight":
            info.weight_grams = float(value or 0)
    for fil in plate.findall("filament"):
        info.filaments.append(
            FileFilament(
                index=int(fil.get("id", "0")),
                material=fil.get("type", ""),
                color=(fil.get("color", "") or "").lstrip("#")[:6].upper(),
                used_grams=float(fil.get("used_g", "0") or 0),
            )
        )


def _color_distance(a: str, b: str) -> float:
    try:
        ar, ag, ab = (int(a[i : i + 2], 16) for i in (0, 2, 4))
        br, bg, bb = (int(b[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return 1e9
    return ((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2) ** 0.5


def suggest_ams_mapping(filaments: list[FileFilament], trays: list[AmsTray]) -> list[int | None]:
    """Pick a tray for each file filament: same material, closest color, each tray used once.

    Returns one global tray index per filament (in file order); None where nothing
    suitable is loaded, so the UI can ask the user instead of guessing.
    """
    available = [t for t in trays if not t.empty]
    result: list[int | None] = []
    for fil in filaments:
        candidates = [t for t in available if t.material.upper() == fil.material.upper()]
        if not candidates:
            result.append(None)
            continue
        best = min(candidates, key=lambda t: _color_distance(fil.color, t.color.upper()))
        available.remove(best)
        result.append(best.global_index)
    return result


def _first(value):
    return value[0] if isinstance(value, list) and value else value


def _parse_settings(raw: bytes, info: PlateInfo) -> None:
    try:
        j = json.loads(raw)
    except ValueError:
        return
    info.printer = str(j.get("printer_model") or "")
    info.nozzle = str(_first(j.get("nozzle_diameter")) or "")
    info.infill = str(j.get("sparse_infill_density") or "")
    info.filament_colors = [str(c).lstrip("#")[:6] for c in j.get("filament_colour") or []]
    try:
        info.layer_height = float(j.get("layer_height") or 0)
        info.walls = int(j.get("wall_loops") or 0)
        info.max_height = float(j.get("printable_height") or info.max_height)
        pts = [tuple(float(v) for v in str(p).split("x")) for p in j.get("printable_area") or []]
        if pts:
            info.bed = (max(p[0] for p in pts), max(p[1] for p in pts))
    except (ValueError, TypeError):
        pass


def _transform(text: str | None) -> tuple[np.ndarray, np.ndarray]:
    """3MF transform: 12 numbers, row-vector convention (v' = v @ R + t)."""
    if not text:
        return np.eye(3), np.zeros(3)
    m = [float(v) for v in text.split()]
    return np.array(m[:9]).reshape(3, 3), np.array(m[9:12])


def _mesh_of(obj) -> tuple[np.ndarray, np.ndarray] | None:
    mesh = obj.find("{*}mesh")
    if mesh is None:
        return None
    v = np.array([(float(e.get("x")), float(e.get("y")), float(e.get("z"))) for e in mesh.iterfind(".//{*}vertex")])
    t = np.array([(int(e.get("v1")), int(e.get("v2")), int(e.get("v3"))) for e in mesh.iterfind(".//{*}triangle")])
    return v, t


def read_meshes(path: str | Path, plate: int = 1) -> list[Mesh]:
    """Objects of a plate, placed as the slicer placed them. Works for sliced and unsliced 3MF."""
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        root = ET.fromstring(zf.read("3D/3dmodel.model"))
        cache: dict[str, ET.Element] = {}

        def objects(file: str | None) -> dict[str, ET.Element]:
            key = (file or "3D/3dmodel.model").lstrip("/")
            if key not in cache:
                cache[key] = root if key == "3D/3dmodel.model" else ET.fromstring(zf.read(key))
            return {o.get("id"): o for o in cache[key].iterfind(".//{*}object")}

        extruders: dict[str, int] = {}
        wanted: set[str] | None = None
        if "Metadata/model_settings.config" in names:
            cfg = ET.fromstring(zf.read("Metadata/model_settings.config"))
            for o in cfg.findall("object"):
                for m in o.findall("metadata"):
                    if m.get("key") == "extruder":
                        extruders[o.get("id")] = int(m.get("value") or 1)
            for pl in cfg.findall("plate"):
                ids = {m.get("value") for m in pl.findall("metadata") if m.get("key") == "plater_id"}
                if str(plate) in ids:
                    wanted = {m.get("value") for inst in pl.findall("model_instance")
                              for m in inst.findall("metadata") if m.get("key") == "object_id"}

        def collect(file, oid, R, t):
            obj = objects(file)[oid]
            parts = []
            got = _mesh_of(obj)
            if got:
                v, tri = got
                parts.append((v @ R + t, tri))
            for c in obj.findall("{*}components/{*}component"):
                R2, t2 = _transform(c.get("transform"))
                cfile = next((v for k, v in c.attrib.items() if k.endswith("path")), file)
                parts += collect(cfile, c.get("objectid"), R2 @ R, t2 @ R + t)
            return parts

        out: list[Mesh] = []
        for item in root.iterfind(".//{*}build/{*}item"):
            oid = item.get("objectid")
            if (wanted is not None and oid not in wanted) or item.get("printable") == "0":
                continue
            R, t = _transform(item.get("transform"))
            parts = collect(None, oid, R, t)
            if not parts:
                continue
            verts = np.vstack([v for v, _ in parts]).astype(np.float32)
            offs = np.cumsum([0] + [len(v) for v, _ in parts[:-1]])
            tris = np.vstack([tri + o for (_, tri), o in zip(parts, offs)]).astype(np.int32)
            out.append(Mesh(f"Object {oid}", verts, tris, extruders.get(oid, 1)))
        return out
