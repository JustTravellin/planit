"""Does it fit? Size and edge margins of what's on the plate, against the printer's build volume."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class FitReport:
    size: tuple[float, float, float]
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]
    margins: dict[str, float]  # left/right/front/back, mm to the bed edge (negative = over the edge)
    issues: list[str] = field(default_factory=list)

    @property
    def fits(self) -> bool:
        return not self.issues


def fit_report(lo, hi, bed=(256.0, 256.0), height=256.0, tol=0.5) -> FitReport:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    m = {"left": lo[0], "right": bed[0] - hi[0], "front": lo[1], "back": bed[1] - hi[1]}
    issues = [f"{side} edge is {-v:.1f} mm outside the plate" for side, v in m.items() if v < -tol]
    if hi[2] > height + tol:
        issues.append(f"{hi[2]:.1f} mm tall, printer maximum is {height:.0f} mm")
    f = lambda a: tuple(float(v) for v in a)
    return FitReport(f(hi - lo), f(lo), f(hi), {k: float(v) for k, v in m.items()}, issues)


def bounds_of(arrays) -> tuple[np.ndarray, np.ndarray] | None:
    """Min/max corner over a list of (n, 3) arrays."""
    arrays = [a for a in arrays if len(a)]
    if not arrays:
        return None
    return np.min([a.min(axis=0) for a in arrays], axis=0), np.max([a.max(axis=0) for a in arrays], axis=0)
