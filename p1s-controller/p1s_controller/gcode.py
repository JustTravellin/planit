"""Minimal G-code reader that extracts extrusion moves per layer, for the layer preview."""
from __future__ import annotations

from dataclasses import dataclass, field

Segment = tuple[float, float, float, float]


@dataclass
class GcodeLayers:
    layers: list[list[Segment]] = field(default_factory=list)
    heights: list[float] = field(default_factory=list)
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 256.0, 256.0)


def _args(parts: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in parts:
        if len(p) > 1 and p[0] in "XYZE":
            try:
                out[p[0]] = float(p[1:])
            except ValueError:
                pass
    return out


def parse(text: str) -> GcodeLayers:
    x = y = z = e = 0.0
    abs_xyz = abs_e = True
    marker_mode = ";LAYER_CHANGE" in text
    layers: list[list[Segment]] = [[]]
    heights: list[float] = [0.0]

    for raw in text.splitlines():
        stripped = raw.strip()
        if marker_mode:
            if stripped == ";LAYER_CHANGE":
                if layers[-1]:
                    layers.append([])
                    heights.append(z)
                continue
            if stripped.startswith(";Z:"):
                try:
                    heights[-1] = float(stripped[3:])
                except ValueError:
                    pass
                continue
        line = stripped.split(";", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]
        if cmd in ("G0", "G1", "G2", "G3"):
            a = _args(parts[1:])
            nx = (a["X"] if abs_xyz else x + a["X"]) if "X" in a else x
            ny = (a["Y"] if abs_xyz else y + a["Y"]) if "Y" in a else y
            nz = (a["Z"] if abs_xyz else z + a["Z"]) if "Z" in a else z
            if "E" in a:
                de = (a["E"] - e) if abs_e else a["E"]
                if abs_e:
                    e = a["E"]
            else:
                de = 0.0
            if not marker_mode and nz > z + 1e-6 and layers[-1]:
                layers.append([])
                heights.append(nz)
            if not marker_mode and not layers[-1]:
                heights[-1] = nz
            if de > 0 and (nx != x or ny != y):
                layers[-1].append((x, y, nx, ny))
            x, y, z = nx, ny, nz
        elif cmd == "G90":
            abs_xyz = True
        elif cmd == "G91":
            abs_xyz = False
        elif cmd == "M82":
            abs_e = True
        elif cmd == "M83":
            abs_e = False
        elif cmd == "G92":
            a = _args(parts[1:])
            if "E" in a:
                e = a["E"]

    while layers and not layers[-1]:
        layers.pop()
        heights.pop()
    xs = [v for layer in layers for s in layer for v in (s[0], s[2])]
    ys = [v for layer in layers for s in layer for v in (s[1], s[3])]
    bounds = (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 256.0, 256.0)
    return GcodeLayers(layers, heights, bounds)
