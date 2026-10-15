from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = "#17181b"
PANEL = "#1c1f26"
PANEL2 = "#252936"
BORDER = "#2e3340"
TEXT = "#e6e8ee"
MUTED = "#8b92a3"
ACCENT = "#00ae42"
INFO = "#3ea6ff"
VIEW_BG = "#1f2125"
PLATE = "#2c2f36"
GRID = "#3a3e47"
OK = "#3ecf8e"
WARN = "#f5a524"
BAD = "#ef5350"

STATE_COLORS = {
    "RUNNING": ACCENT, "PREPARE": ACCENT, "PAUSE": WARN,
    "FINISH": OK, "FAILED": BAD, "IDLE": MUTED, "UNKNOWN": MUTED,
}

QSS = f"""
QWidget {{ color: {TEXT}; font-size: 13px; font-family: "Segoe UI", "Inter", "DejaVu Sans", sans-serif; }}
QMainWindow, QDialog, QTabWidget::pane {{ background: {BG}; border: 0; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 9px 18px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QFrame#card, QGroupBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
QGroupBox {{ margin-top: 14px; padding: 12px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; color: {MUTED}; padding: 0 4px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#big {{ font-size: 22px; font-weight: 600; }}
QPushButton {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover:enabled {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {MUTED}; background: {PANEL}; }}
QPushButton#primary {{ background: {ACCENT}; color: #06121f; border: 0; font-weight: 600; }}
QPushButton#primary:disabled {{ background: {PANEL2}; color: {MUTED}; }}
QPushButton#danger {{ border-color: {BAD}; color: {BAD}; }}
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QListWidget, QTableWidget {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 6px; selection-background-color: {ACCENT}; selection-color: #06121f; }}
QPlainTextEdit {{ font-family: Consolas, "DejaVu Sans Mono", monospace; }}
QHeaderView::section {{ background: {PANEL2}; color: {MUTED}; border: 0; padding: 6px; }}
QProgressBar {{ background: {PANEL2}; border: 0; border-radius: 6px; height: 12px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
QSlider::groove:horizontal {{ background: {PANEL2}; height: 6px; border-radius: 3px; }}
QSlider::groove:vertical {{ background: {PANEL2}; width: 6px; border-radius: 3px; }}
QSlider::handle:vertical {{ background: {ACCENT}; height: 16px; margin: 0 -5px; border-radius: 8px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 16px; margin: -5px 0; border-radius: 8px; }}
QListWidget#nav {{ background: {PANEL}; border: 0; border-right: 1px solid {BORDER}; border-radius: 0; padding: 10px 8px; outline: 0; }}
QListWidget#nav::item {{ padding: 10px 14px; border-radius: 6px; color: {MUTED}; margin-bottom: 2px; }}
QListWidget#nav::item:hover {{ background: {PANEL2}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {PANEL2}; color: {TEXT}; border-left: 3px solid {ACCENT}; }}
QToolBar#header {{ background: {PANEL}; border: 0; border-bottom: 1px solid {BORDER}; padding: 6px 10px; spacing: 8px; }}
QLabel#brand {{ font-weight: 600; font-size: 14px; padding: 0 12px 0 4px; }}
QLabel#chip {{ border-radius: 10px; padding: 2px 10px; font-weight: 600; }}
QLabel#section {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; margin-top: 10px; }}
QWidget#inspector {{ background: {PANEL}; border-left: 1px solid {BORDER}; }}
QPushButton#tool {{ padding: 4px 10px; background: transparent; border: 1px solid transparent; color: {MUTED}; }}
QPushButton#tool:hover {{ color: {TEXT}; background: {PANEL2}; }}
QPushButton#seg {{ padding: 4px 16px; border-radius: 0; background: {PANEL}; }}
QPushButton#seg:checked {{ background: {ACCENT}; color: #06121f; border-color: {ACCENT}; font-weight: 600; }}
QPushButton#seg:disabled {{ color: {MUTED}; }}
QListWidget::item {{ padding: 6px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {PANEL2}; border: 1px solid {ACCENT}; color: {TEXT}; }}
QListWidget::item:hover {{ background: {PANEL2}; }}
QSplitter::handle {{ background: {BORDER}; width: 1px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; }}
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(PANEL))
    pal.setColor(QPalette.AlternateBase, QColor(PANEL2))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(PANEL2))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#06121f"))
    pal.setColor(QPalette.ToolTipBase, QColor(PANEL2))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
