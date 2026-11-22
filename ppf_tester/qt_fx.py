"""Componentes visuales: fondo animado de escenario, logo, iconos, piano con brillo,
forma de onda/espectro, medidores, avisos (toast) y transiciones."""
from __future__ import annotations

import math
import random
import time

import numpy as np
from PySide6.QtCore import (QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal,
                            QParallelAnimationGroup, Property)
from PySide6.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient, QConicalGradient)
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QLabel, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

from qt_theme import C, font, q


# ======================================================================= fondo
class StageBackground(QWidget):
    """Luces de escenario que se mueven y respiran, rayos de luz y partículas.
    `level_fn` devuelve 0..1 (nivel de audio) para que el fondo lata con la música."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.t0 = time.perf_counter()
        self.level_fn = lambda: 0.0
        self.level = 0.0
        self.animated = True
        rnd = random.Random(7)
        self.particles = [[rnd.random(), rnd.random(), 0.004 + rnd.random() * 0.012, 0.6 + rnd.random() * 2.2,
                           rnd.random() * math.tau] for _ in range(70)]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def set_animated(self, on: bool):
        self.animated = on
        if on:
            self.timer.start(50)
        else:
            self.timer.stop()
            self.update()

    def _tick(self):
        lv = max(0.0, min(1.0, float(self.level_fn() or 0.0)))
        self.level = max(lv, self.level * 0.9)
        # solo repintar los huecos: las tarjetas opacas tapan el fondo
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtGui import QRegion
        reg = QRegion(self.rect())
        for c in self.findChildren(QFrame):
            if c.objectName() in ("Card", "Card2") and c.isVisible() and c.width() > 40:
                tl = c.mapTo(self, QPoint(0, 0))
                reg -= QRegion(QRect(tl.x() + 6, tl.y() + 6, c.width() - 12, c.height() - 12))
        self._frame = None
        self.update(reg)

    def _render_lights(self, w, h, t, boost):
        """Luces y rayos a 1/3 de resolución (se escalan con suavizado)."""
        from PySide6.QtGui import QImage
        sw, sh = max(8, w // 5), max(8, h // 5)
        img = QImage(sw, sh, QImage.Format.Format_RGB32)
        img.fill(q("bg"))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(sw / w, sh / h)
        self._paint_lights(p, w, h, t, boost)
        p.end()
        return img

    def paintEvent(self, e):
        w, h = self.width(), self.height()
        t = (time.perf_counter() - self.t0) if self.animated else 8.0
        boost = 1 + self.level * 0.9
        if getattr(self, "_frame", None) is None or self._frame_size != (w, h):
            self._frame = self._render_lights(w, h, t, boost)
            self._frame_size = (w, h)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, w, h), self._frame)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        self._paint_particles(p, w, h, t, boost)
        p.end()

    def _paint_lights(self, p, w, h, t, boost):
        blobs = [  # (x, y, radio, color, alfa, velocidad, fase)
            (0.82, -0.05, 0.55, "gold", 70, 0.07, 0.0),
            (0.98, 0.95, 0.45, "coral", 55, 0.05, 1.7),
            (0.12, 0.15, 0.42, "violet", 38, 0.06, 3.1),
            (0.45, 1.10, 0.50, "gold", 28, 0.04, 4.4),
        ]
        p.setPen(Qt.PenStyle.NoPen)
        for bx, by, br, col, a, sp, ph in blobs:
            cx = (bx + 0.06 * math.sin(t * sp * 6 + ph)) * w
            cy = (by + 0.05 * math.cos(t * sp * 5 + ph)) * h
            r = br * max(w, h) * (0.92 + 0.08 * math.sin(t * 0.6 + ph)) * (0.95 + 0.1 * self.level)
            g = QRadialGradient(QPointF(cx, cy), r)
            c0 = q(col, int(min(255, a * boost)))
            c1 = q(col, 0)
            g.setColorAt(0, c0)
            g.setColorAt(0.45, q(col, int(min(255, a * boost * 0.35))))
            g.setColorAt(1, c1)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(cx, cy), r, r)
        # rayos de luz desde arriba
        for i, (x0, ang0, col) in enumerate(((0.70, -0.35, "gold"), (0.86, -0.12, "coral"), (0.30, 0.25, "violet"))):
            ang = ang0 + 0.12 * math.sin(t * 0.15 + i * 2)
            alpha = int((14 + 10 * math.sin(t * 0.35 + i * 1.3)) * boost)
            top = QPointF(x0 * w, -20)
            L = h * 1.4
            d = QPointF(math.sin(ang) * L, math.cos(ang) * L)
            n = QPointF(math.cos(ang), -math.sin(ang))
            wid = w * 0.09
            path = QPainterPath(top + n * 6)
            path.lineTo(top - n * 6)
            path.lineTo(top + d - n * wid)
            path.lineTo(top + d + n * wid)
            path.closeSubpath()
            g = QLinearGradient(top, top + d)
            g.setColorAt(0, q(col, max(0, alpha)))
            g.setColorAt(1, q(col, 0))
            p.setBrush(QBrush(g))
            p.drawPath(path)
        # viñeta
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(0, 0, 0, 110))
        p.fillRect(QRectF(0, 0, w, h), QBrush(g))

    def _paint_particles(self, p, w, h, t, boost):
        for pt in self.particles:
            x, y, v, s, ph = pt
            yy = (y - t * v) % 1.0
            xx = x + 0.01 * math.sin(t * 0.5 + ph)
            a = int(60 * (0.5 + 0.5 * math.sin(t * 0.8 + ph)) * (1 - abs(yy - 0.5)) * boost)
            p.setBrush(QColor(255, 236, 210, max(0, min(255, a))))
            p.drawEllipse(QPointF(xx * w, yy * h), s, s)


# ======================================================================= logo
def paint_logo(p: QPainter, cx: float, cy: float, r: float, pulse: float = 0.0, glow_r: float | None = None):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    gr = glow_r if glow_r is not None else r * 2.2
    glow = QRadialGradient(QPointF(cx, cy), gr)
    glow.setColorAt(0, q("gold", int(60 + 80 * pulse)))
    glow.setColorAt(1, q("gold", 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(glow))
    p.drawEllipse(QPointF(cx, cy), gr, gr)
    cg = QConicalGradient(QPointF(cx, cy), 90)
    cg.setColorAt(0, q("gold"))
    cg.setColorAt(0.5, q("coral"))
    cg.setColorAt(1, q("gold"))
    pen = QPen(QBrush(cg), max(2.0, r * 0.13))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r, r)
    pen = QPen(q("fg"), max(2.0, r * 0.11))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for i, hh in enumerate((0.35, 0.7, 1.0, 0.6, 0.3)):
        hh = hh * (1 + 0.25 * pulse * math.sin(i * 1.7 + time.perf_counter() * 8))
        bx = cx - r * 0.48 + i * r * 0.24
        p.drawLine(QPointF(bx, cy - hh * r * 0.45), QPointF(bx, cy + hh * r * 0.45))
    p.restore()


class Logo(QWidget):
    def __init__(self, size=40, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.pulse = 0.0

    def paintEvent(self, e):
        p = QPainter(self)
        paint_logo(p, self.width() / 2, self.height() / 2, self.width() * 0.33, self.pulse, glow_r=self.width() / 2)
        p.end()


# ====================================================================== iconos
def icon(name: str, color: str = "fg", size: int = 20) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size * 2 / 24, size * 2 / 24)
    pen = QPen(q(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if name == "wave":
        for i, hh in enumerate((4, 9, 14, 8, 5)):
            x = 5 + i * 3.5
            p.drawLine(QPointF(x, 12 - hh / 2), QPointF(x, 12 + hh / 2))
    elif name == "headphones":
        path = QPainterPath(QPointF(4, 15))
        path.cubicTo(4, 3, 20, 3, 20, 15)
        p.drawPath(path)
        p.drawRoundedRect(QRectF(3, 13, 4, 7), 1.5, 1.5)
        p.drawRoundedRect(QRectF(17, 13, 4, 7), 1.5, 1.5)
    elif name == "sparkle":
        for cx, cy, r in ((10, 12, 6.5), (18, 6, 3)):
            path = QPainterPath(QPointF(cx, cy - r))
            path.quadTo(cx, cy, cx + r, cy)
            path.quadTo(cx, cy, cx, cy + r)
            path.quadTo(cx, cy, cx - r, cy)
            path.quadTo(cx, cy, cx, cy - r)
            p.drawPath(path)
    elif name == "check":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 4, 4)
        p.drawPolyline([QPointF(8, 12.5), QPointF(11, 15.5), QPointF(16.5, 9)])
    elif name == "piano":
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        for x in (7.5, 12, 16.5):
            p.drawLine(QPointF(x, 5), QPointF(x, 19))
        p.setBrush(q(color))
        for x in (6.3, 10.8, 15.3):
            p.drawRect(QRectF(x, 5, 2.4, 7))
    elif name == "folder":
        path = QPainterPath(QPointF(3, 7))
        path.lineTo(9, 7); path.lineTo(11, 9); path.lineTo(21, 9); path.lineTo(21, 19); path.lineTo(3, 19)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "save":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        p.drawRect(QRectF(8, 4, 8, 5))
        p.drawRect(QRectF(7, 13, 10, 7))
    elif name == "doc":
        p.drawRoundedRect(QRectF(6, 3, 12, 18), 2, 2)
        for y in (8, 12, 16):
            p.drawLine(QPointF(9, y), QPointF(15, y))
    elif name == "export":
        p.drawLine(QPointF(12, 4), QPointF(12, 15))
        p.drawPolyline([QPointF(8, 11), QPointF(12, 15), QPointF(16, 11)])
        p.drawLine(QPointF(5, 19), QPointF(19, 19))
    elif name == "info":
        p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        p.drawLine(QPointF(12, 11), QPointF(12, 16))
        p.drawPoint(QPointF(12, 8))
    elif name == "gear":
        p.drawEllipse(QPointF(12, 12), 3, 3)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(12 + math.cos(a) * 6, 12 + math.sin(a) * 6), QPointF(12 + math.cos(a) * 8.5, 12 + math.sin(a) * 8.5))
        p.drawEllipse(QPointF(12, 12), 6, 6)
    elif name == "play":
        p.setBrush(q(color))
        p.drawPolygon([QPointF(8, 5), QPointF(19, 12), QPointF(8, 19)])
    elif name == "stop":
        p.setBrush(q(color))
        p.drawRoundedRect(QRectF(7, 7, 10, 10), 2, 2)
    elif name == "refresh":
        path = QPainterPath()
        path.arcMoveTo(QRectF(5, 5, 14, 14), 30)
        path.arcTo(QRectF(5, 5, 14, 14), 30, 300)
        p.drawPath(path)
        p.drawPolyline([QPointF(19, 4.5), QPointF(18.2, 8.8), QPointF(14, 8)])
    elif name == "github":
        p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        p.drawPolyline([QPointF(9, 19.5), QPointF(9, 16), QPointF(8, 14), QPointF(8, 11), QPointF(10, 9),
                        QPointF(14, 9), QPointF(16, 11), QPointF(16, 14), QPointF(15, 16), QPointF(15, 19.5)])
    elif name == "web":
        p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        p.drawEllipse(QRectF(8.5, 3.5, 7, 17))
        p.drawLine(QPointF(3.5, 12), QPointF(20.5, 12))
    p.end()
    return QIcon(pm)


# ======================================================================= tarjetas
def card(parent=None, name="Card") -> QFrame:
    f = QFrame(parent)
    f.setObjectName(name)
    f.setAutoFillBackground(True)          # opaco: no se repinta con el fondo animado
    return f


def caption(text: str) -> QLabel:
    l = QLabel(text.upper())
    l.setObjectName("Cap")
    return l


# ======================================================================== toast
class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet(f"background: rgba(24,24,30,235); border: 1px solid {C['line2']}; border-radius: 12px;"
                           f" padding: 12px 18px; font-size: 10pt;")
        self.setWordWrap(True)
        self.setMaximumWidth(420)
        self.eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.eff)
        self.hide()
        self.anim = QPropertyAnimation(self.eff, b"opacity", self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)

    def show_msg(self, text: str, kind: str = "OK", ms: int = 3200):
        dot = {"OK": C["OK"], "ERROR": C["ERROR"], "AVISO": C["AVISO"], "INFO": C["gold"]}.get(kind, C["gold"])
        self.setText(f"<span style='color:{dot}; font-size:13pt'>●</span>&nbsp;&nbsp;{text}")
        self.adjustSize()
        par = self.parentWidget()
        self.move(par.width() - self.width() - 24, par.height() - self.height() - 52)
        self.raise_()
        self.show()
        self.anim.stop()
        self.anim.setDuration(220)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self.timer.start(ms)

    def _fade_out(self):
        self.anim.stop()
        self.anim.setDuration(400)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self._hide_once)
        self.anim.start()

    def _hide_once(self):
        try:
            self.anim.finished.disconnect(self._hide_once)
        except (RuntimeError, TypeError):
            pass
        if self.eff.opacity() < 0.05:
            self.hide()


# =================================================================== transición
class FadeStack(QStackedWidget):
    """QStackedWidget con fundido y leve desplazamiento al cambiar de página."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.animated = True

    def fade_to(self, idx: int):
        if idx == self.currentIndex():
            return
        self.setCurrentIndex(idx)
        if not self.animated:
            return
        w = self.currentWidget()
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", w)
        a.setDuration(260)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(lambda: w.setGraphicsEffect(None))
        a.start()
        self._anim = a


# ======================================================================== piano
class GlowPiano(QWidget):
    keyClicked = Signal(int, float)     # nota, posición vertical 0..1

    WHITE = (0, 2, 4, 5, 7, 9, 11)

    def __init__(self, parent=None, height=110):
        super().__init__(parent)
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(height)
        self.status: dict[int, str] = {}
        self.labels: dict[int, str] = {}
        self.selected = None
        self.glow: dict[int, float] = {}
        self.lo, self.hi = 36, 71
        self._rects = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._decay)
        self.timer.start(30)

    def set_keys(self, status: dict[int, str]):
        self.status = dict(status)
        if status:
            lo, hi = min(status), max(status)
            self.lo = max(0, (lo // 12) * 12)
            self.hi = min(127, ((hi // 12) + 1) * 12 - 1)
            if self.hi - self.lo < 35:
                self.hi = min(127, self.lo + 35)
        self.update()

    def flash(self, n: int, amount: float = 1.0):
        self.glow[n] = max(self.glow.get(n, 0), amount)
        self.update()

    def _decay(self):
        if not self.glow:
            return
        self.glow = {k: v * 0.86 for k, v in self.glow.items() if v > 0.03}
        self.update()

    def _color(self, n, black):
        st = self.status.get(n)
        if st is None:
            return QColor("#1b1b21") if black else QColor("#ece7df")
        base = {"OK": "gold", "INFO": "gold", "AVISO": "coral", "ERROR": "ERROR"}.get(st, "gold")
        c = q(base)
        if black:
            c = c.darker(190)
        return c

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        whites = [n for n in range(self.lo, self.hi + 1) if n % 12 in self.WHITE]
        if not whites:
            return
        kw = w / len(whites)
        pos = {}
        self._rects = []
        for i, n in enumerate(whites):
            r = QRectF(i * kw + 1, 0, kw - 2, h - 1)
            pos[n] = i * kw
            col = self._color(n, False)
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, col.darker(115))
            g.setColorAt(0.12, col)
            g.setColorAt(1, col.lighter(104))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 4, 4)
            if n == self.selected:
                p.setPen(QPen(q("coral"), 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), 4, 4)
            gl = self.glow.get(n, 0)
            if gl > 0:
                rg = QRadialGradient(r.center().x(), r.bottom() - 10, kw * 1.4)
                rg.setColorAt(0, QColor(255, 250, 235, int(230 * gl)))
                rg.setColorAt(1, QColor(255, 210, 140, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(rg))
                p.drawRoundedRect(r, 4, 4)
            p.setPen(QColor(60, 50, 40, 170))
            p.setFont(font(7.5, display=False))
            if n in self.labels:
                p.setFont(font(9, 700))
                p.setPen(QColor(30, 20, 10, 220))
                p.drawText(QRectF(r.left(), r.bottom() - 34, r.width(), 18), Qt.AlignmentFlag.AlignCenter, self.labels[n])
            if n % 12 == 0:
                p.setFont(font(7))
                p.setPen(QColor(80, 70, 60, 180))
                from ppf_format import note_name
                p.drawText(QRectF(r.left(), r.bottom() - 16, r.width(), 14), Qt.AlignmentFlag.AlignCenter, note_name(n))
            self._rects.append((r, n))
        blacks = []
        for n in range(self.lo, self.hi + 1):
            if n % 12 in self.WHITE or (n - 1) not in pos:
                continue
            r = QRectF(pos[n - 1] + kw * 0.66, 0, kw * 0.68, h * 0.6)
            col = self._color(n, True)
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, col.lighter(130))
            g.setColorAt(1, col)
            p.setPen(QPen(QColor(0, 0, 0, 160), 1))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 3, 3)
            if n == self.selected:
                p.setPen(QPen(q("coral"), 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), 3, 3)
            gl = self.glow.get(n, 0)
            if gl > 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 225, 170, int(200 * gl)))
                p.drawRoundedRect(r, 3, 3)
            if n in self.labels:
                p.setFont(font(8, 700))
                p.setPen(QColor(255, 245, 230, 230))
                p.drawText(QRectF(r.left(), r.bottom() - 20, r.width(), 16), Qt.AlignmentFlag.AlignCenter, self.labels[n])
            blacks.append((r, n))
        self._rects = blacks + self._rects
        p.end()

    def mousePressEvent(self, e):
        for r, n in self._rects:
            if r.contains(e.position()):
                self.keyClicked.emit(n, (e.position().y() - r.top()) / max(1, r.height()))
                return


# ====================================================================== onda
class WaveView(QWidget):
    """Forma de onda, espectro o comparación A/B (varias envolventes)."""

    def __init__(self, parent=None, height=180):
        super().__init__(parent)
        self.setMinimumHeight(height)
        self.mode = "onda"
        self.x = None
        self.sr = 44100
        self.title = ""
        self.lead = self.tail = 0.0
        self.series = []   # [(array, color, etiqueta)]

    def show_wave(self, x, sr, title="", lead_ms=0.0, tail_ms=0.0):
        self.x, self.sr, self.title = x, sr, title
        self.lead, self.tail = lead_ms, tail_ms
        self.series = []
        self.update()

    def show_series(self, series, title=""):
        self.series = series
        self.title = title
        self.x = None
        self.update()

    def toggle(self) -> str:
        self.mode = "espectro" if self.mode == "onda" else "onda"
        self.update()
        return self.mode

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(q("card2"))
        p.drawRoundedRect(QRectF(0, 0, w, h), 12, 12)
        mid = h / 2
        if self.series:
            self._paint_series(p, w, h)
        elif self.x is None:
            p.setPen(q("mut"))
            p.setFont(font(10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin muestra seleccionada")
        elif self.mode == "espectro":
            self._paint_spectrum(p, w, h)
        else:
            x = self.x
            mono = np.abs(x).max(axis=1) if x.ndim > 1 else np.abs(x)
            n = len(mono)
            if n:
                if self.lead > 1:
                    p.setBrush(QColor(244, 184, 96, 22))
                    p.drawRect(QRectF(0, 0, self.lead / 1000 * self.sr / n * w, h))
                if self.tail > 1:
                    tw = self.tail / 1000 * self.sr / n * w
                    p.setBrush(QColor(90, 169, 255, 22))
                    p.drawRect(QRectF(w - tw, 0, tw, h))
                cols = max(2, int(w))
                edges = np.linspace(0, n, cols + 1).astype(int)
                edges = np.minimum(edges, n - 1)
                pk = np.maximum.reduceat(mono, edges[:-1]) if n > cols else np.interp(np.linspace(0, n - 1, cols), np.arange(n), mono)
                sc = mid - 14
                path = QPainterPath(QPointF(0, mid))
                for i, v in enumerate(pk):
                    path.lineTo(i * w / cols, mid - v * sc)
                for i in range(len(pk) - 1, -1, -1):
                    path.lineTo(i * w / cols, mid + pk[i] * sc)
                path.closeSubpath()
                g = QLinearGradient(0, 0, w, 0)
                g.setColorAt(0, q("gold"))
                g.setColorAt(0.6, q("coral"))
                g.setColorAt(1, q("violet"))
                p.setBrush(QBrush(g))
                p.drawPath(path)
                p.setPen(QPen(QColor(255, 255, 255, 18), 1, Qt.PenStyle.DashLine))
                for lv in (1.0, 0.5):
                    for yy in (mid - lv * sc, mid + lv * sc):
                        p.drawLine(QPointF(0, yy), QPointF(w, yy))
                p.setPen(q("mut"))
                p.setFont(font(8))
                p.drawText(QRectF(10, h - 22, 200, 16), Qt.AlignmentFlag.AlignLeft, f"{n / self.sr:.2f} s")
        if self.title:
            p.setPen(q("fg"))
            p.setFont(font(10, 600))
            p.drawText(QRectF(14, 8, w - 28, 20), Qt.AlignmentFlag.AlignLeft, self.title)
        p.end()

    def _paint_spectrum(self, p, w, h):
        import dsp
        db, f = dsp.spectrum_db(self.x, self.sr, 160)
        lo, hi = math.log10(20), math.log10(20000)
        xs = (np.log10(f) - lo) / (hi - lo) * w
        ys = 30 + (np.clip(-db, 0, 72) / 72) * (h - 52)
        path = QPainterPath(QPointF(0, h - 22))
        for x, y in zip(xs, ys):
            path.lineTo(x, y)
        path.lineTo(w, h - 22)
        path.closeSubpath()
        g = QLinearGradient(0, 30, 0, h)
        g.setColorAt(0, q("gold", 170))
        g.setColorAt(1, q("coral", 10))
        p.setPen(QPen(q("gold"), 2))
        p.setBrush(QBrush(g))
        p.drawPath(path)
        p.setFont(font(8))
        for fr, lab in ((50, "50"), (100, "100"), (300, "300"), (1000, "1k"), (3000, "3k"), (7000, "7k"), (12000, "12k")):
            x = (math.log10(fr) - lo) / (hi - lo) * w
            p.setPen(QPen(QColor(255, 255, 255, 18), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, 30), QPointF(x, h - 22))
            p.setPen(q("mut"))
            p.drawText(QRectF(x - 20, h - 20, 40, 16), Qt.AlignmentFlag.AlignCenter, lab)

    def _paint_series(self, p, w, h):
        mid = h / 2
        n = max(len(s[0]) for s in self.series if s[0] is not None)
        x0 = 14
        for arr, col, lab in self.series:
            if arr is None or not len(arr):
                continue
            m = np.abs(arr).max(axis=1) if arr.ndim > 1 else np.abs(arr)
            m = m / max(m.max(), 1e-9)
            cols = max(2, int(w * len(m) / n))
            edges = np.minimum(np.linspace(0, len(m), cols + 1).astype(int), len(m) - 1)
            pk = np.maximum.reduceat(m, edges[:-1]) if len(m) > cols else m
            sc = mid - 26
            for sign in (-1, 1):
                path = QPainterPath(QPointF(0, mid))
                for i, v in enumerate(pk):
                    path.lineTo(i * w * len(m) / n / len(pk), mid + sign * v * sc)
                p.setPen(QPen(q(col), 1.6))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(q(col))
            p.drawEllipse(QPointF(x0 + 4, h - 14), 4, 4)
            p.setPen(q("fg"))
            p.setFont(font(8))
            p.drawText(QPointF(x0 + 12, h - 10), lab)
            x0 += 120


# ===================================================================== medidor
class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self.level_fn = lambda: 0.0
        self.v = 0.0
        self.peak = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def _tick(self):
        lv = float(self.level_fn() or 0.0)
        db = 20 * math.log10(max(lv, 1e-6))
        v = max(0.0, min(1.0, (db + 60) / 60))
        self.v = max(v, self.v * 0.85)
        self.peak = max(self.v, self.peak - 0.01)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(q("line"))
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0, q("OK"))
        g.setColorAt(0.75, q("gold"))
        g.setColorAt(1, q("ERROR"))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(0, 0, w * self.v, h), h / 2, h / 2)
        p.setBrush(q("fg"))
        p.drawRect(QRectF(w * self.peak - 1, 0, 2, h))
        p.end()


class MemoryBars(QWidget):
    """Uso de memoria del kit en cada modelo de la serie S."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setMinimumHeight(150)

    def set_rows(self, rows):   # [(nombre, mb_kit, mb_modelo, estado)]
        self.rows = rows
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        y = 4
        for name, mb, cap, st in self.rows:
            p.setPen(q("fg"))
            p.setFont(font(9, 600))
            p.drawText(QRectF(0, y, 90, 18), Qt.AlignmentFlag.AlignVCenter, name.replace("PSR-", ""))
            p.setPen(q("mut"))
            p.setFont(font(8.5))
            pct = mb / cap * 100
            p.drawText(QRectF(w - 150, y, 150, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{pct:.1f} % de {cap:.0f} MB")
            bx, bw = 70, w - 230
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(q("line"))
            p.drawRoundedRect(QRectF(bx, y + 6, bw, 6), 3, 3)
            col = {"OK": "OK", "AVISO": "AVISO", "ERROR": "ERROR"}[st]
            p.setBrush(q(col))
            p.drawRoundedRect(QRectF(bx, y + 6, max(4, bw * min(1, pct / 100)), 6), 3, 3)
            y += 28
        p.end()


# ====================================================================== splash
class Splash(QWidget):
    """Pantalla de bienvenida con fondo de luces y logo animado."""

    def __init__(self, version: str, autor: str):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(560, 320)
        self.bg = StageBackground(self)
        self.bg.setGeometry(self.rect())
        self.version, self.autor = version, autor
        self.t0 = time.perf_counter()
        self.overlay = _SplashOverlay(self)
        self.overlay.setGeometry(self.rect())

    def showEvent(self, e):
        scr = self.screen().availableGeometry()
        self.move(scr.center().x() - self.width() // 2, scr.center().y() - self.height() // 2)


class _SplashOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

    def paintEvent(self, e):
        sp = self.parentWidget()
        t = time.perf_counter() - sp.t0
        a = min(1.0, t / 0.6)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(a)
        paint_logo(p, self.width() / 2, 110, 40, 0.5 + 0.5 * math.sin(t * 4))
        p.setPen(q("fg"))
        p.setFont(font(26, 300, display=True))
        p.drawText(QRectF(0, 170, self.width(), 44), Qt.AlignmentFlag.AlignCenter, "PPF TESTER")
        p.setPen(QColor("#cfc6d6"))
        p.setFont(font(8.5, 700))
        p.drawText(QRectF(0, 214, self.width(), 20), Qt.AlignmentFlag.AlignCenter, "SAMPLE LAB  ·  YAMAHA PSR-S")
        p.setPen(q("mut"))
        p.setFont(font(9))
        p.drawText(QRectF(0, 270, self.width(), 20), Qt.AlignmentFlag.AlignCenter,
                   f"v{sp.version}  ·  Desarrollado por {sp.autor}")
        # barra de carga
        w = self.width() * 0.4
        x0 = (self.width() - w) / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(q("line"))
        p.drawRoundedRect(QRectF(x0, 250, w, 3), 1.5, 1.5)
        g = QLinearGradient(x0, 0, x0 + w, 0)
        g.setColorAt(0, q("gold"))
        g.setColorAt(1, q("coral"))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(x0, 250, w * min(1, t / 1.3), 3), 1.5, 1.5)
        p.end()
