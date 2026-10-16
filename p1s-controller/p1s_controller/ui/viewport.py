"""OpenGL 3D viewport: the plate, the model on it, and the sliced toolpath."""
from __future__ import annotations

import numpy as np

try:
    import pyqtgraph.opengl as gl
    from pyqtgraph import Vector
    AVAILABLE = True
except Exception:  # PyOpenGL missing
    gl = None
    AVAILABLE = False

from . import theme

FILAMENT_FALLBACK = ["#00ae42", "#3ea6ff", "#f5a524", "#ef5350", "#b388ff", "#26c6da"]


def _rgba(color: str, a: float = 1.0) -> tuple[float, float, float, float]:
    c = color.lstrip("#")
    return int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255, a


def layer_colors(z: np.ndarray, zmax: float) -> np.ndarray:
    """Blue -> green -> yellow -> red by height, like a slicer's layer view."""
    t = np.clip(z / max(zmax, 1e-6), 0, 1)[:, None]
    stops = np.array([[0.2, 0.4, 1.0], [0.1, 0.8, 0.5], [0.95, 0.85, 0.2], [0.95, 0.3, 0.2]])
    x = t * 3
    i = np.minimum(x.astype(int), 2)
    f = x - i
    rgb = stops[i[:, 0]] * (1 - f) + stops[i[:, 0] + 1] * f
    return np.hstack([rgb, np.ones((len(z), 1))]).astype(np.float32)


if AVAILABLE:
    class Viewport3D(gl.GLViewWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setBackgroundColor(theme.VIEW_BG)
            self.setMinimumSize(360, 300)
            self.bed = (256.0, 256.0, 256.0)
            self._static: list = []
            self._models: list = []
            self._path = self._top = None
            self._segs = np.zeros((0, 6), np.float32)
            self._cols = np.zeros((0, 4), np.float32)
            self._offsets = [0]
            self.set_bed(*self.bed)
            self.view("iso")

        # ---- plate
        def set_bed(self, w: float, d: float, h: float) -> None:
            for it in self._static:
                self.removeItem(it)
            self.bed = (w, d, h)
            plate = gl.GLMeshItem(
                vertexes=np.array([[0, 0, -0.2], [w, 0, -0.2], [w, d, -0.2], [0, d, -0.2]], np.float32),
                faces=np.array([[0, 1, 2], [0, 2, 3]]), color=_rgba(theme.PLATE), smooth=False, shader=None,
                glOptions="opaque")
            lines = []
            for v in np.arange(0, w + 0.1, 10):
                lines += [(v, 0, 0), (v, d, 0)]
            for v in np.arange(0, d + 0.1, 10):
                lines += [(0, v, 0), (w, v, 0)]
            grid = gl.GLLinePlotItem(pos=np.array(lines, np.float32), color=_rgba(theme.GRID), mode="lines",
                                     width=1, antialias=False)
            edge = gl.GLLinePlotItem(pos=np.array([(0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0), (0, 0, 0)], np.float32),
                                     color=_rgba(theme.ACCENT, 0.9), width=2, antialias=True)
            box = []
            for x, y in ((0, 0), (w, 0), (w, d), (0, d)):
                box += [(x, y, 0), (x, y, h)]
            for a, b in (((0, 0), (w, 0)), ((w, 0), (w, d)), ((w, d), (0, d)), ((0, d), (0, 0))):
                box += [(*a, h), (*b, h)]
            vol = gl.GLLinePlotItem(pos=np.array(box, np.float32), color=_rgba(theme.GRID, 0.6), mode="lines",
                                    width=1, antialias=False)
            axes = gl.GLLinePlotItem(
                pos=np.array([(0, 0, 0), (30, 0, 0), (0, 0, 0), (0, 30, 0), (0, 0, 0), (0, 0, 30)], np.float32),
                color=np.array([_rgba("#ef5350")] * 2 + [_rgba("#3ecf8e")] * 2 + [_rgba("#3ea6ff")] * 2),
                mode="lines", width=3, antialias=True)
            self._static = [plate, grid, vol, edge, axes]
            for it in self._static:
                self.addItem(it)

        # ---- model
        def clear_model(self) -> None:
            for it in self._models:
                self.removeItem(it)
            self._models = []
            self._clear_path()

        def set_meshes(self, meshes, colors: list[str] | None = None) -> None:
            self.clear_model()
            for i, m in enumerate(meshes):
                hexcol = (colors[m.extruder - 1] if colors and 0 < m.extruder <= len(colors)
                          else FILAMENT_FALLBACK[i % len(FILAMENT_FALLBACK)])
                data = gl.MeshData(vertexes=m.verts, faces=m.tris)
                item = gl.GLMeshItem(meshdata=data, smooth=False, shader="shaded", color=_rgba(hexcol),
                                     glOptions="opaque")
                self._models.append(item)
                self.addItem(item)

        # ---- toolpath
        def _clear_path(self) -> None:
            for it in (self._path, self._top):
                if it is not None:
                    self.removeItem(it)
            self._path = self._top = None

        def set_toolpath(self, layers) -> None:
            """layers: gcode.GcodeLayers."""
            self._clear_path()
            segs, offs = [], [0]
            for layer, z in zip(layers.layers, layers.heights):
                if layer:
                    a = np.asarray(layer, np.float32)
                    segs.append(np.column_stack([a[:, 0], a[:, 1], np.full(len(a), z, np.float32),
                                                 a[:, 2], a[:, 3], np.full(len(a), z, np.float32)]))
                offs.append(offs[-1] + len(layer))
            self._segs = np.vstack(segs) if segs else np.zeros((0, 6), np.float32)
            self._offsets = offs
            zmax = float(self._segs[:, 2].max()) if len(self._segs) else 1.0
            self._cols = np.repeat(layer_colors(self._segs[:, 2], zmax), 2, axis=0)
            self._path = gl.GLLinePlotItem(mode="lines", width=1.5, antialias=False, glOptions="opaque")
            self._top = gl.GLLinePlotItem(mode="lines", width=3, antialias=True, glOptions="opaque")
            self.addItem(self._path)
            self.addItem(self._top)
            self.set_layer(len(offs) - 2)

        def set_layer(self, idx: int) -> None:
            if self._path is None or len(self._offsets) < 2:
                return
            idx = max(0, min(idx, len(self._offsets) - 2))
            end = self._offsets[idx + 1]
            self._path.setData(pos=self._segs[:end].reshape(-1, 3), color=self._cols[: 2 * end])
            s = self._offsets[idx]
            self._top.setData(pos=self._segs[s:end].reshape(-1, 3), color=_rgba("#ffffff"))

        def show_model(self, on: bool) -> None:
            for it in self._models:
                it.setVisible(on)
            for it in (self._path, self._top):
                if it is not None:
                    it.setVisible(not on)

        # ---- camera
        def view(self, name: str) -> None:
            w, d, _ = self.bed
            self.opts["center"] = Vector(w / 2, d / 2, 0)
            elev, azim = {"iso": (35, -50), "top": (90, -90), "front": (0, -90), "back": (0, 90),
                          "left": (0, 180), "right": (0, 0)}[name]
            self.setCameraPosition(distance=max(w, d) * 1.6, elevation=elev, azimuth=azim)

        def frame(self, lo, hi) -> None:
            lo, hi = np.asarray(lo, float), np.asarray(hi, float)
            self.opts["center"] = Vector(*((lo + hi) / 2))
            self.setCameraPosition(distance=max(float(np.linalg.norm(hi - lo)) * 2.0, 60))
else:
    Viewport3D = None
