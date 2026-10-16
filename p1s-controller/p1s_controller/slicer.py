"""Slice for the P1S by driving the installed Bambu Studio (or OrcaSlicer) command line.

The slicing engine is the slicer's own, so G-code matches what Bambu Studio would produce. This module finds
the install, resolves the stock P1S machine/process/filament presets (the P1S uses the X1C process presets),
applies a few user choices, runs the CLI headless and returns a `.gcode.3mf` this app can preview and send.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

NOZZLES = ("0.2", "0.4", "0.6", "0.8")
BED_TYPES = ("Cool Plate", "Engineering Plate", "Textured PEI Plate", "High Temp Plate")
_CANDIDATES = [
    ("Bambu Studio", r"C:\Program Files\Bambu Studio\bambu-studio.exe"),
    ("OrcaSlicer", r"C:\Program Files\OrcaSlicer\orca-slicer.exe"),
    ("Bambu Studio", "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
    ("Bambu Studio", "/usr/bin/bambu-studio"),
]


class SliceError(RuntimeError):
    pass


class Cancelled(SliceError):
    pass


@dataclass
class Slicer:
    name: str
    exe: Path

    @property
    def profiles(self) -> Path:
        # Windows/Linux keep resources next to the exe, macOS inside the bundle.
        for base in (self.exe.parent / "resources", self.exe.parent.parent / "Resources"):
            if (base / "profiles" / "BBL").is_dir():
                return base / "profiles" / "BBL"
        return self.exe.parent / "resources" / "profiles" / "BBL"


def find_slicer() -> Slicer | None:
    env = os.environ.get("P1S_SLICER")
    if env and Path(env).is_file():
        return Slicer("Slicer", Path(env))
    for name, path in _CANDIDATES:
        if Path(path).is_file():
            return Slicer(name, Path(path))
    return None


# ---- presets ---------------------------------------------------------------------------------
_cache: dict[tuple[str, str], dict[str, dict]] = {}


def _load(root: Path, kind: str) -> dict[str, dict]:
    key = (str(root), kind)
    if key not in _cache:
        out: dict[str, dict] = {}
        for f in (root / kind).glob("*.json"):
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if "name" in j:
                out[j["name"]] = j
        _cache[key] = out
    return _cache[key]


def flatten(root: Path, kind: str, name: str) -> dict:
    """A preset with its whole `inherits` chain merged in, which is what the CLI needs."""
    db = _load(root, kind)
    chain, cur, seen = [], db[name], set()
    while cur and cur["name"] not in seen:
        seen.add(cur["name"])
        chain.append(cur)
        cur = db.get(cur.get("inherits", ""))
    out: dict = {}
    for c in reversed(chain):
        out.update(c)
    out.pop("inherits", None)
    return out


def machine_name(nozzle: str = "0.4") -> str:
    return f"Bambu Lab P1S {nozzle} nozzle"


def compatible(root: Path, kind: str, nozzle: str = "0.4") -> list[str]:
    target = machine_name(nozzle)
    return sorted(n for n, j in _load(root, kind).items()
                  if j.get("instantiation") == "true" and target in (j.get("compatible_printers") or []))


def process_presets(root: Path, nozzle: str = "0.4") -> list[str]:
    """Quality presets, finest layer first."""
    return sorted(compatible(root, "process", nozzle), key=lambda n: (float(n.split("mm")[0]), n))


def filament_presets(root: Path, nozzle: str = "0.4") -> list[str]:
    return compatible(root, "filament", nozzle)


def short_name(preset: str) -> str:
    return preset.split(" @")[0]


def suggest_filament(material: str, brand: str, presets: list[str]) -> str | None:
    """Preset for an AMS spool: the Bambu product when its name matches, else the generic material."""
    material, brand = material.strip(), brand.strip()
    for want in ([f"Bambu {brand}"] if brand else []) + [f"Generic {material}", f"Bambu {material} Basic",
                                                          f"Bambu {material}"]:
        hits = [p for p in presets if short_name(p) == want]
        if hits:
            return min(hits, key=lambda p: ("P1S" not in p, len(p)))
    return None


# ---- slicing ---------------------------------------------------------------------------------
@dataclass
class Settings:
    process: str = "0.20mm Standard @BBL X1C"
    filaments: list[str] = field(default_factory=lambda: ["Bambu PLA Basic @BBL P1S 0.4 nozzle"])
    colors: list[str] = field(default_factory=list)  # "RRGGBB" per filament, optional
    nozzle: str = "0.4"
    infill: str = ""  # "15%"
    walls: int = 0
    supports: bool | None = None  # None = leave the preset alone
    bed_type: str = ""  # one of BED_TYPES, or "" for the preset default
    brim: bool | None = None
    reduce_purge: bool = False


@dataclass
class SliceResult:
    path: Path
    seconds: int
    grams: float
    layers: int
    notes: list[str] = field(default_factory=list)


def apply_settings(root: Path, s: Settings, workdir: Path) -> tuple[str, list[str]]:
    """Write the flattened preset files, with the user's overrides, and return CLI --load-* values."""
    machine = flatten(root, "machine", machine_name(s.nozzle))
    if s.bed_type:
        machine["curr_bed_type"] = s.bed_type
    process = flatten(root, "process", s.process)
    if s.infill:
        process["sparse_infill_density"] = s.infill
    if s.walls:
        process["wall_loops"] = str(s.walls)
    if s.supports is not None:
        process["enable_support"] = "1" if s.supports else "0"
    if s.brim is not None:
        process["brim_type"] = "auto_brim" if s.brim else "no_brim"
    if s.reduce_purge:
        process["flush_multiplier"] = "0.6"
    files = []
    for n, d in (("machine", machine), ("process", process)):
        p = workdir / f"{n}.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        files.append(str(p))
    fils = []
    for i, name in enumerate(s.filaments):
        d = flatten(root, "filament", name)
        if i < len(s.colors) and s.colors[i]:
            d["filament_colour"] = ["#" + s.colors[i].lstrip("#")]
        p = workdir / f"filament{i}.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        fils.append(str(p))
    return ";".join(files), fils


def needs_arrange(path: Path) -> bool:
    """Plain meshes and non-Bambu 3MFs have no placement; Bambu projects keep the user's layout."""
    if path.suffix.lower() != ".3mf":
        return True
    with zipfile.ZipFile(path) as zf:
        return "Metadata/model_settings.config" not in zf.namelist()


def build_command(slicer: Slicer, model: Path, outdir: Path, settings_arg: str, filaments: list[str],
                  arrange: bool) -> list[str]:
    cmd = [str(slicer.exe), "--slice", "0"]
    if arrange:
        cmd += ["--arrange", "1"]
    cmd += ["--load-settings", settings_arg, "--load-filaments", ";".join(filaments),
            "--outputdir", str(outdir), "--export-3mf", "sliced.gcode.3mf", str(model)]
    return cmd


def slice_model(model: str | Path, dest: str | Path, settings: Settings, slicer: Slicer | None = None,
                cancel: threading.Event | None = None, timeout: float = 3600) -> SliceResult:
    """Slice `model` (3MF/STL/OBJ/STEP) and write the sliced project to `dest` (.gcode.3mf)."""
    slicer = slicer or find_slicer()
    if slicer is None:
        raise SliceError("Bambu Studio is not installed (set P1S_SLICER to its .exe to use another location).")
    model, dest = Path(model).resolve(), Path(dest)
    root = slicer.profiles
    with tempfile.TemporaryDirectory(prefix="p1s-slice-") as tmp:
        work = Path(tmp)
        settings_arg, fils = apply_settings(root, settings, work)
        out = work / "out"
        cmd = build_command(slicer, model, out, settings_arg, fils, needs_arrange(model))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        waited = 0.0
        while True:
            try:
                proc.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                waited += 0.25
                if cancel is not None and cancel.is_set():
                    proc.kill()
                    raise Cancelled("Slicing cancelled")
                if waited > timeout:
                    proc.kill()
                    raise SliceError("Slicing took too long and was stopped")
        result = _read_result(out)
        produced = out / "sliced.gcode.3mf"
        if proc.returncode != 0 or not produced.is_file() or result.get("return_code", 0) != 0:
            raise SliceError(result.get("error_string") or f"Slicer exited with code {proc.returncode}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(produced, dest)
    return _summarise(dest, result)


def _read_result(out: Path) -> dict:
    try:
        return json.loads((out / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _summarise(dest: Path, result: dict) -> SliceResult:
    plates = result.get("sliced_plates") or [{}]
    first = plates[0]
    grams = sum(f.get("total_used_g", 0) for f in first.get("filaments", []))
    layers = 0
    try:
        with zipfile.ZipFile(dest) as zf:
            head = zf.read("Metadata/plate_1.gcode")[:4000].decode("utf-8", "replace")
        for line in head.splitlines():
            if line.startswith("; total layer number:"):
                layers = int(line.split(":")[1])
    except (OSError, KeyError, ValueError):
        pass
    return SliceResult(dest, int(first.get("main_predication", 0)), round(float(grams), 2), layers)


def output_path(model: Path) -> Path:
    """Where the sliced file goes: next to the model, never over it."""
    name = model.name
    for ext in (".gcode.3mf", ".3mf", ".stl", ".obj", ".step", ".stp"):
        if name.lower().endswith(ext):
            stem = name[: -len(ext)]
            break
    else:
        stem = model.stem
    out = model.with_name(f"{stem}.gcode.3mf")
    if out == model:
        out = model.with_name(f"{stem} (P1S).gcode.3mf")
    return out
