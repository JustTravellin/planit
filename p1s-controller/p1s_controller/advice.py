"""Plain-language slicing advice for the P1S, shown next to the slice settings.

Each rule is a short, conservative statement from Bambu's own guidance and the common community practice for an
enclosed, AMS-fed corexy printer. Returns (severity, text); severity is "error", "warn" or "info".
"""
from __future__ import annotations

import re

from .plate import FitReport

HIGH_TEMP = ("ABS", "ASA", "PC", "PA", "PPA")
SOFT_OPEN = ("PLA", "PETG", "TPU")


def material_of(preset: str) -> str:
    """'Bambu PLA-CF @BBL X1C' -> 'PLA'; 'Generic PETG HF' -> 'PETG'. Empty if unknown."""
    name = preset.split(" @")[0]
    for tok in ("PETG", "PET", "PLA", "ABS", "ASA", "PPA", "PA", "PC", "TPU", "PVA", "PP", "HIPS"):
        if re.search(rf"(?<![A-Z]){tok}(?![A-Z])", name):
            return tok
    return ""


def abrasive(preset: str) -> bool:
    return bool(re.search(r"(?<![A-Z])(CF|GF)(?![A-Z])", preset.split(" @")[0]))


def advise(presets: list[str], *, nozzle_type: str | None = None, bed_type: str = "", supports: bool | None = None,
           fit: FitReport | None = None, layer_height: float = 0.0, has_ams: bool = True) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    mats = {material_of(p) for p in presets} - {""}

    if fit is not None and not fit.fits:
        out.append(("error", "The model does not fit the plate: " + "; ".join(fit.issues) + "."))
    for p in presets:
        if abrasive(p) and nozzle_type and "hardened" not in nozzle_type and "tungsten" not in nozzle_type:
            out.append(("error", f"{p.split(' @')[0]} is abrasive and will wear the printer's {nozzle_type.replace('_', ' ')} "
                                 "nozzle quickly. Fit a hardened steel nozzle first."))
        elif abrasive(p) and not nozzle_type:
            out.append(("warn", f"{p.split(' @')[0]} is abrasive: use a hardened steel nozzle, not the stock one."))
        if has_ams and re.match(r"Bambu TPU \d+A", p.split(" @")[0]):
            out.append(("warn", "This TPU is too soft for the AMS. Feed it from the external spool "
                                "(only 'TPU for AMS' works in the AMS)."))
    hot = mats & set(HIGH_TEMP)
    if hot:
        out.append(("warn", f"{'/'.join(sorted(hot))} warps and gives off fumes: keep the front door and top glass "
                            "on, ventilate the room, and consider a brim and the Engineering or High Temp plate."))
    if mats & set(SOFT_OPEN) and not hot:
        out.append(("info", "If your room is warm (above about 30 °C), open the front door or lift the lid for "
                            "PLA, PETG and TPU so the hotend does not heat-soak and clog."))
    if "PETG" in mats and bed_type in ("", "Cool Plate", "Engineering Plate"):
        out.append(("info", "PETG can bond very hard to smooth plates. Use the textured plate, or a thin layer of glue "
                            "stick as a release agent."))
    if len(presets) > 1:
        out.append(("info", "Colour changes purge filament. 'Reduce purge' trims the waste; flushing into infill "
                            "or supports saves more."))
    if supports:
        out.append(("info", "For supports, tree supports use less material and remove cleaner on organic shapes; "
                            "use normal supports under large flat overhangs."))
    if 0 < layer_height <= 0.1:
        out.append(("info", f"{layer_height:g} mm layers take much longer; use them only where surface detail matters."))
    if "PLA" in mats and "Cool Plate" in bed_type:
        out.append(("info", "The smooth Cool plate gives the best bottom surface for PLA, but clean it with "
                            "isopropyl alcohol for good adhesion."))
    return out
