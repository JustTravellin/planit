from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from .. import threemf
from ..db import Database
from .bridge import PrinterBridge
from .gcode_preview import GcodePreview
from .send_dialog import SendDialog
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
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(120, 120))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setGridSize(QSize(150, 170))
        self.list.setWordWrap(True)

        side = QWidget()
        sl = QVBoxLayout(side)
        self.title = QLabel("Select a file")
        self.title.setObjectName("big")
        self.title.setWordWrap(True)
        self.details = QLabel("")
        self.details.setTextFormat(Qt.RichText)
        self.tags = QLineEdit(placeholderText="Tags, comma separated")
        self.preview = GcodePreview()
        btns = QHBoxLayout()
        self.preview_btn = QPushButton("Preview layers")
        self.send_btn = QPushButton("Send / print…")
        self.send_btn.setObjectName("primary")
        btns.addWidget(self.preview_btn)
        btns.addWidget(self.send_btn)
        for w in (self.title, self.details, self.tags):
            sl.addWidget(w)
        sl.addLayout(btns)
        sl.addWidget(self.preview, 1)

        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(split, 1)

        choose.clicked.connect(self._choose)
        refresh.clicked.connect(self.reload)
        self.search.textChanged.connect(self._apply_filter)
        self.list.currentItemChanged.connect(self._selected)
        self.tags.editingFinished.connect(self._save_tags)
        self.preview_btn.clicked.connect(self._preview)
        self.send_btn.clicked.connect(self._send)
        self._set_buttons(False)
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
        for path in sorted(folder.glob("*.gcode.3mf"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                info = threemf.read(path)
            except Exception:
                continue  # not a sliced file
            self.infos[str(path)] = info
            item = QListWidgetItem(path.name.removesuffix(".gcode.3mf"))
            item.setData(Qt.UserRole, str(path))
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

    def _set_buttons(self, on: bool) -> None:
        self.preview_btn.setEnabled(on)
        self.send_btn.setEnabled(on)
        self.tags.setEnabled(on)

    def _selected(self, item, _prev=None) -> None:
        if item is None:
            self.title.setText("Select a file")
            self.details.setText("")
            self._set_buttons(False)
            return
        path = item.data(Qt.UserRole)
        info = self.infos[path]
        self.title.setText(item.text())
        chips = "".join(
            f"<span style='color:#{f.color}'>●</span> {f.material} {f.used_grams:.1f} g &nbsp; " for f in info.filaments)
        self.details.setText(f"{fmt_seconds(info.print_seconds)} · {info.weight_grams:.1f} g<br>{chips}")
        self.tags.setText(self.db.get_tags(path))
        self._set_buttons(True)

    def _save_tags(self) -> None:
        path = self.current_path()
        if path:
            self.db.set_tags(str(path), self.tags.text())
            self._apply_filter()

    def _preview(self) -> None:
        path = self.current_path()
        if path:
            self.preview.load(path, self.infos[str(path)].plate)

    def _send(self) -> None:
        path = self.current_path()
        if path:
            SendDialog(self.bridge, path, self).exec()
