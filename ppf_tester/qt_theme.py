"""Tema visual de PPF Tester (Qt): negro profundo, blanco cálido y luces de escenario."""
from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase

C = dict(
    bg="#08080a", side="#0d0d10", card="#121216", card2="#18181e", line="#25252d", line2="#30303a",
    fg="#f5f1ea", mut="#8f8b98", dim="#5d5a66",
    gold="#f4b860", coral="#ec6f7f", violet="#8b6cff", blue="#5aa9ff",
    ERROR="#ff6b7d", AVISO="#f6cb6b", INFO="#8fb4ff", OK="#63d4a3",
)


OSCURO = dict(C)
CLARO = dict(
    bg="#f3efe8", side="#ebe5dc", card="#ffffff", card2="#f5f1eb", line="#e4ddd2", line2="#d3cabd",
    fg="#1f1c24", mut="#6d6774", dim="#aaa3ad",
    gold="#c98a2e", coral="#d65468", violet="#6c51de", blue="#2c7bd6",
    ERROR="#d23b52", AVISO="#b7841a", INFO="#3d6fd1", OK="#23996a",
)
TEMA = "oscuro"


def set_tema(nombre: str):
    """Cambia la paleta (antes de crear la ventana)."""
    global TEMA
    TEMA = "claro" if nombre == "claro" else "oscuro"
    C.update(CLARO if TEMA == "claro" else OSCURO)


def claro() -> bool:
    return TEMA == "claro"


def rgba(name: str, a: int) -> str:
    c = QColor(C.get(name, name))
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


def q(name: str, alpha: int | None = None) -> QColor:
    c = QColor(C.get(name, name))
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def fonts() -> tuple[str, str]:
    fams = set(QFontDatabase.families())
    if "Segoe UI Variable Text" in fams:
        return "Segoe UI Variable Text", "Segoe UI Variable Display"
    return "Segoe UI", "Segoe UI"


def font(size: float, weight=QFont.Weight.Normal, display=False) -> QFont:
    body, disp = fonts()
    f = QFont(disp if display else body)
    f.setPointSizeF(size)
    f.setWeight(weight if isinstance(weight, QFont.Weight) else QFont.Weight(int(weight)))
    return f


def _check_png() -> str:
    """Genera el ícono de check para las casillas (se referencia desde el QSS)."""
    import os
    import tempfile
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QPainter, QPen, QPixmap
    path = os.path.join(tempfile.gettempdir(), "ppf_tester_check.png")
    if not os.path.exists(path):
        pm = QPixmap(36, 36)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#1a1007"), 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline([QPointF(9, 19), QPointF(15, 25), QPointF(27, 11)])
        p.end()
        pm.save(path)
    return path.replace("\\", "/")


def stylesheet() -> str:
    body, _ = fonts()
    check = _check_png()
    return f"""
* {{ font-family: '{body}'; font-size: 10pt; color: {C['fg']}; }}
QMainWindow, QDialog {{ background: {C['bg']}; }}
QToolTip {{ background: {C['card2']}; color: {C['fg']}; border: 1px solid {C['line2']}; padding: 6px 8px; border-radius: 6px; }}

QFrame#Card {{ background: {C['card']}; border: 1px solid {C['line']}; border-radius: 14px; }}
QFrame#Card2 {{ background: {C['card2']}; border: 1px solid {C['line']}; border-radius: 10px; }}
QLabel#H1 {{ font-size: 20pt; font-weight: 300; }}
QLabel#H2 {{ font-size: 12pt; font-weight: 600; }}
QLabel#Cap {{ color: {C['mut']}; font-size: 7.5pt; font-weight: 700; letter-spacing: 1.2px; }}
QLabel#Mut {{ color: {C['mut']}; }}
QLabel#Big {{ font-size: 15pt; font-weight: 600; }}
QLabel#Link {{ color: {C['gold']}; }}

QPushButton {{ background: {C['card2']}; border: 1px solid {C['line2']}; border-radius: 9px; padding: 8px 16px; }}
QPushButton:hover {{ background: {C['line']}; border-color: {C['line2']}; }}
QPushButton:pressed {{ background: {C['card']}; }}
QPushButton:disabled {{ color: {C['dim']}; border-color: {C['line']}; background: {C['card']}; }}
QPushButton#Primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C['gold']}, stop:1 #f19a6c);
    color: #1a1007; border: none; font-weight: 700; }}
QPushButton#Primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ffcb80, stop:1 #f7a97e); }}
QPushButton#Primary:disabled {{ background: #3a2f22; color: #7a6a55; }}
QPushButton#Ghost {{ background: transparent; border: none; color: {C['mut']}; padding: 6px 10px; }}
QPushButton#Ghost:hover {{ color: {C['fg']}; }}
QPushButton#Seg {{ background: transparent; border: 1px solid {C['line2']}; border-radius: 0; padding: 8px 14px; color: {C['mut']}; }}
QPushButton#Seg:checked {{ background: {C['card2']}; color: {C['gold']}; border-color: {C['gold']}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {C['line2']}; background: {C['card2']}; }}
QCheckBox::indicator:checked {{ background: {C['gold']}; border-color: {C['gold']}; image: url({check}); }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px; border: 1px solid {C['line2']}; background: {C['card2']}; }}
QRadioButton::indicator:checked {{ background: qradialgradient(cx:.5,cy:.5,radius:.5, fx:.5,fy:.5, stop:0 {C['gold']}, stop:.45 {C['gold']}, stop:.55 {C['card2']}); border-color: {C['gold']}; }}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{ background: {C['card2']}; border: 1px solid {C['line2']}; border-radius: 8px; padding: 6px 10px; min-height: 18px; }}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {{ border-color: {C['dim']}; }}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{ border-color: {C['gold']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {C['card2']}; border: 1px solid {C['line2']}; selection-background-color: #3a2f22; outline: 0; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; border: none; }}

QSlider::groove:horizontal {{ height: 4px; background: {C['line2']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {C['gold']}, stop:1 {C['coral']}); border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {C['fg']}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QSlider::handle:horizontal:hover {{ background: {C['gold']}; }}

QTableWidget, QListWidget, QTextBrowser {{ background: transparent; border: none; gridline-color: transparent; selection-background-color: transparent; outline: 0; }}
QTableWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {C['line']}; }}
QTableWidget::item:selected {{ background: rgba(244,184,96,0.14); color: {C['fg']}; }}
QTableWidget::item:hover {{ background: rgba(255,255,255,0.03); }}
QHeaderView {{ background: transparent; border: none; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; color: {C['mut']}; border: none; border-bottom: 1px solid {C['line2']}; padding: 6px 8px; font-size: 8pt; font-weight: 700; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 8px; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.04); }}
QListWidget::item:selected {{ background: rgba(244,184,96,0.12); color: {C['fg']}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {C['line2']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['dim']}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QProgressBar {{ background: {C['line']}; border: none; border-radius: 3px; height: 6px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ border-radius: 3px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {C['gold']}, stop:.5 {C['coral']}, stop:1 {C['violet']}); }}
"""


def dark_titlebar(widget) -> None:
    """Barra de título oscura en Windows 10/11."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        val = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
        # color de la barra (Windows 11)
        col = ctypes.c_int(0x00E8EFF3 if TEMA == "claro" else 0x000A0808)
        if TEMA == "claro":
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(0)), 4)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(col), ctypes.sizeof(col))
    except Exception:  # noqa: BLE001
        pass
