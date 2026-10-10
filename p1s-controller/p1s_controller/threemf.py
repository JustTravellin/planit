"""Read a sliced .gcode.3mf: thumbnail, filaments, time and weight, and AMS slot mapping."""
from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

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


def read(path: str | Path) -> PlateInfo:
    info = PlateInfo()
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "Metadata/slice_info.config" in names:
            _parse_slice_info(zf.read("Metadata/slice_info.config"), info)
        for name in ("Metadata/plate_1.png", "Metadata/plate_no_light_1.png"):
            if name in names:
                info.thumbnail_png = zf.read(name)
                break
        if not any(n.startswith("Metadata/plate_") and n.endswith(".gcode") for n in names):
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
