from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QFrame, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget)

from .. import threemf
from ..db import Database
from . import theme
from .bridge import PrinterBridge
from .gcode_preview import PlatePreview
from .send_dialog import SendDialog
from .slice_panel import SlicePanel
from .util import fmt_seconds


class Library(QWidget):
    def __init__(self, bridge: PrinterBridge, db: Database, settings: QSettings | None = None, parent=None):
        super().__init__(parent)
        self.bridge, self.db = bridge, db
        self.settings = settings or QSettings("p1s-controller", "p1s-controller")
        self.infos: dict[str, threemf.PlateInfo] = {}

        top = QHBoxLayout()
        self.folder_label = QLabel("")
        self.folder_label.setObjectName("muted")
        choose = QPushButton("Choose folder…")
        refresh = QPushButton("Refresh")
        self.search = QLineEdit(placeholderText="Search name or tag")
        top.addWidget(self.search, 1)
        top.addWidget(self.folder_label)
        top.addWidget(choose)
        top.addWidget(refresh)

        self.list = QListWidget()
        self.list.setIconSize(QSize(64, 64))
        self.list.setSpacing(2)
        self.list.setMinimumWidth(240)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.ElideRight)

        self.preview = PlatePreview()

        inspector = QWidget()
        inspector.setObjectName("inspector")
        sl = QVBoxLayout(inspector)
        self.title = QLabel("Select a file")
        self.title.setObjectName("big")
        self.title.setWordWrap(True)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.details = QLabel("")
        self.details.setTextFormat(Qt.RichText)
        self.details.setWordWrap(True)
        self.process = QLabel("")
        self.process.setTextFormat(Qt.RichText)
        self.process.setWordWrap(True)
        self.tags = QLineEdit(placeholderText="Tags, comma separated")
        self.send_btn = QPushButton("Send / print…")
        self.send_btn.setObjectName("primary")
        self.slice_panel = SlicePanel(bridge)
        for text, w in (("", self.title), ("", self.status), ("PRINT", self.details), ("PROCESS", self.process),
                        ("SLICE", self.slice_panel), ("TAGS", self.tags)):
            if text:
                head = QLabel(text)
                head.setObjectName("section")
                sl.addWidget(head)
            sl.addWidget(w)
        sl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inspector)
        scroll.setFixedWidth(330)
        right = QWidget()
        right.setObjectName("inspector")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 10)
        rl.addWidget(scroll, 1)
        rl.addWidget(self.send_btn)

        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(self.preview)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([260, 700, 300])
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(split, 1)

        choose.clicked.connect(self._choose)
        refresh.clicked.connect(self.reload)
        self.search.textChanged.connect(self._apply_filter)
        self.list.currentItemChanged.connect(self._selected)
        self.tags.editingFinished.connect(self._save_tags)
        self.preview.fitUpdated.connect(self._fit_updated)
        self.slice_panel.sliced.connect(self._sliced)
        self.send_btn.clicked.connect(self._send)
        self.send_btn.setEnabled(False)
        self.tags.setEnabled(False)
        self.reload()

    # ---- folder / listing
    @property
    def folder(self) -> Path | None:
        value = self.settings.value("library/folder", "")
        return Path(value) if value else None

    def set_folder(self, folder: Path) -> None:
        self.settings.setValue("library/folder", str(folder))
        self.reload()

    def _choose(self) -> None:
        picked = QFileDialog.getExistingDirectory(self, "Folder with .gcode.3mf files", str(self.folder or Path.home()))
        if picked:
            self.set_folder(Path(picked))

    def reload(self) -> None:
        self.list.clear()
        self.infos.clear()
        folder = self.folder
        self.folder_label.setText(str(folder) if folder else "No folder chosen")
        if not folder or not folder.is_dir():
            return
        files = sorted([*folder.glob("*.3mf"), *folder.glob("*.stl")], key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files:
            try:
                info = threemf.read(path, require_gcode=False)
            except Exception:
                continue  # not a readable 3MF
            self.infos[str(path)] = info
            name = path.name.removesuffix(".gcode.3mf").removesuffix(".3mf").removesuffix(".stl")
            sub = f"{fmt_seconds(info.print_seconds)} · {info.weight_grams:.0f} g" if info.sliced else "Not sliced"
            item = QListWidgetItem(f"{name}" + chr(10) + sub)
            item.setData(Qt.UserRole, str(path))
            item.setData(Qt.UserRole + 1, name)
            if info.thumbnail_png:
                pm = QPixmap()
                pm.loadFromData(info.thumbnail_png)
                item.setIcon(QIcon(pm))
            self.list.addItem(item)
        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            path = item.data(Qt.UserRole)
            hay = (item.text() + " " + self.db.get_tags(path)).lower()
            item.setHidden(bool(needle) and needle not in hay)

    # ---- selection
    def current_path(self) -> Path | None:
        item = self.list.currentItem()
        return Path(item.data(Qt.UserRole)) if item else None

    def _selected(self, item, _prev=None) -> None:
        if item is None:
            self.title.setText("Select a file")
            self.details.setText("")
            self.process.setText("")
            self.status.setText("")
            self.send_btn.setEnabled(False)
            self.tags.setEnabled(False)
            self.preview.clear()
            return
        path = item.data(Qt.UserRole)
        info = self.infos[path]
        self.title.setText(item.data(Qt.UserRole + 1))
        if info.sliced:
            wrong = bool(info.printer) and "P1S" not in info.printer.upper()
            self.status.setText(
                f"<span style='color:{theme.OK}'>● Sliced and ready to print</span>" if not wrong else
                f"<span style='color:{theme.WARN}'>● Sliced for {info.printer}, not a P1S.</span> Re-slice for the "
                f"P1S before printing.")
            chips = "".join(f"<br><span style='color:#{f.color}'>●</span> {f.material} &nbsp;{f.used_grams:.1f} g"
                            for f in info.filaments)
            self.details.setText(f"<b>{fmt_seconds(info.print_seconds)}</b> &nbsp;·&nbsp; "
                                 f"<b>{info.weight_grams:.1f} g</b>{chips}")
        else:
            self.status.setText(f"<span style='color:{theme.WARN}'>● Not sliced yet</span> — open it in Bambu "
                                f"Studio, slice, and export the plate as .gcode.3mf to print it from here.")
            self.details.setText("Model preview only")
        rows = [("Printer", info.printer), ("Nozzle", f"{info.nozzle} mm" if info.nozzle else ""),
                ("Layer height", f"{info.layer_height:g} mm" if info.layer_height else ""),
                ("Walls", str(info.walls) if info.walls else ""), ("Infill", info.infill)]
        self.process.setText("<br>".join(f"<span style='color:{theme.MUTED}'>{k}</span> &nbsp;{v}"
                                         for k, v in rows if v) or "—")
        self.tags.setText(self.db.get_tags(path))
        self.send_btn.setEnabled(info.sliced)
        self.tags.setEnabled(True)
        self.preview.set_bed(info.bed, info.max_height)
        self.slice_panel.set_model(Path(path), info.extruders, None)
        self.preview.colors = ["#" + c for c in info.filament_colors]
        self.preview.load(Path(path), info.plate, info.sliced)

    def _fit_updated(self, fit) -> None:
        self.slice_panel.fit = fit
        self.slice_panel.refresh_advice()

    def _sliced(self, result) -> None:
        self.reload()
        for i in range(self.list.count()):
            if Path(self.list.item(i).data(Qt.UserRole)) == result.path:
                self.list.setCurrentRow(i)
                self.preview.wait()
                self.preview.sliced_btn.click()
                break

    def _save_tags(self) -> None:
        path = self.current_path()
        if path:
            self.db.set_tags(str(path), self.tags.text())
            self._apply_filter()

    def _send(self) -> None:
        path = self.current_path()
        if path:
            SendDialog(self.bridge, path, self).exec()
