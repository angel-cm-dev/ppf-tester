"""Panel de estilo (.sty): toca la batería de un estilo Yamaha con el kit, con los botones de un PSR-S."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QFrame, QLabel, QPushButton, QSpinBox

import estilos as E
from qt_fx import caption, icon
from qt_pages import btn, hbox, vbox
from qt_theme import C

FILTRO = "Estilos Yamaha (*.sty *.prs *.sst *.bcs *.pcs *.fps);;Todos los archivos (*)"
GRUPOS = [("INTRO", ["Intro A", "Intro B", "Intro C", "Intro D"]),
          ("MAIN", ["Main A", "Main B", "Main C", "Main D"]),
          ("", ["Fill In BA"]),
          ("ENDING", ["Ending A", "Ending B", "Ending C", "Ending D"])]
OPCIONALES = {"Intro D", "Ending D"}   # solo en algunos estilos

_paneles: list["PanelEstilo"] = []


class PanelEstilo(QFrame):
    """tocar_factory() -> (tocar(nota, vel, ganancia), notas disponibles). Puede lanzar excepción."""

    def __init__(self, ctx, tocar_factory, compacto: bool = False, al_iniciar=None):
        super().__init__()
        self.setObjectName("Card")
        self.ctx = ctx
        self.factory = tocar_factory
        self.al_iniciar = al_iniciar      # para parar otros ritmos de la página
        self.player: E.Reproductor | None = None
        self.disp: set[int] = set()
        self.intro_sel: str | None = None
        self.main_sel: str | None = None
        _paneles.append(self)
        root = vbox(self, 16, 8)
        root.setContentsMargins(16, 10, 16, 12)
        top = hbox(None, 0, 10)
        top.addWidget(caption("Estilo del teclado (.sty)"))
        self.lbl = QLabel("Carga un estilo de tu PSR para oír su batería con este kit.")
        self.lbl.setObjectName("Mut")
        top.addWidget(self.lbl)
        self.falta = QLabel("")
        self.falta.setStyleSheet(f"color:{C['coral']};")
        top.addWidget(self.falta, 1)
        b_load = btn("Cargar estilo…", "folder")
        b_load.setToolTip("Archivos .sty de tu PSR (USB o PC). Solo suena la batería del estilo, con tu kit.")
        b_load.clicked.connect(self.cargar)
        top.addWidget(b_load)
        root.addLayout(top)

        fila = hbox(None, 0, 6)
        self.botones: dict[str, QPushButton] = {}
        for titulo, secs in GRUPOS:
            if titulo:
                t = QLabel(titulo)
                t.setStyleSheet(f"color:{C['mut']}; font-size:10px; font-weight:700; letter-spacing:1px;")
                fila.addWidget(t)
            for s in secs:
                b = QPushButton(E.etiqueta(s).split()[-1] if titulo else "BREAK")
                b.setObjectName("Sty")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setFixedHeight(30)
                b.setMinimumWidth(34 if titulo else 64)
                b.setToolTip(self._tip(s))
                b.clicked.connect(lambda _=False, s=s: self.boton(s))
                self.botones[s] = b
                fila.addWidget(b)
            fila.addSpacing(8)
        fila.addStretch(1)
        root.addLayout(fila)
        abajo = fila
        self.chk_fill = QCheckBox("Auto Fill")
        self.chk_fill.setChecked(True)
        self.chk_fill.setToolTip("Como en el PSR: al pulsar un Main suena su Fill antes de cambiar.\n"
                                 "Pulsar el Main que ya suena toca su Fill.")
        self.chk_fill.toggled.connect(lambda v: self.player and setattr(self.player, "autofill", v))
        abajo.addWidget(self.chk_fill)
        abajo.addWidget(QLabel("Tempo"))
        self.sp_tempo = QSpinBox()
        self.sp_tempo.setRange(30, 300)
        self.sp_tempo.setValue(100)
        self.sp_tempo.setFixedWidth(72)
        self.sp_tempo.valueChanged.connect(lambda v: self.player and setattr(self.player, "bpm", float(v)))
        abajo.addWidget(self.sp_tempo)
        self.b_reset = btn("", "refresh", tip="Tempo original del estilo")
        self.b_reset.clicked.connect(lambda: self.estilo and self.sp_tempo.setValue(round(self.estilo.tempo)))
        abajo.addWidget(self.b_reset)
        self.now = QLabel("")
        self.now.setMinimumWidth(58)
        self.now.setStyleSheet(f"color:{C['gold']}; font-weight:700;")
        abajo.addWidget(self.now)
        self.b_start = btn("Start", "play", primary=True)
        self.b_start.setToolTip("START/STOP del estilo")
        self.b_start.clicked.connect(self.start_stop)
        abajo.addWidget(self.b_start)
        self.setStyleSheet(f"""
QPushButton#Sty {{ background: {C['card2']}; border: 1px solid {C['line2']}; border-radius: 6px; padding: 2px 8px;
                   color: {C['fg']}; font-weight: 700; }}
QPushButton#Sty:hover {{ border-color: {C['gold']}; }}
QPushButton#Sty:disabled {{ color: {C['line2']}; border-color: {C['line']}; background: transparent; }}
QPushButton#Sty[estado="sel"] {{ border: 1px solid {C['gold']}; color: {C['gold']}; }}
QPushButton#Sty[estado="on"] {{ background: {C['gold']}; border-color: {C['gold']}; color: #1a1007; }}
""")
        self._refrescar()

    # ------------------------------------------------------------- datos
    @property
    def estilo(self) -> E.Estilo | None:
        return getattr(self.ctx, "estilo", None)

    @staticmethod
    def _tip(s: str) -> str:
        t = E.tipo(s)
        return {"intro": f"{s}: suena una vez al empezar y pasa al Main elegido",
                "main": f"{s}: patrón principal en bucle. Mientras suena, pulsarlo toca su Fill",
                "break": "Break (Fill In BA): un compás de corte y vuelve al Main",
                "ending": f"{s}: final; el estilo se detiene al terminar"}.get(t, s)

    def cargar(self):
        d = self.ctx.settings.value("dir_sty", "")
        path, _ = QFileDialog.getOpenFileName(self, "Elegir estilo", d, FILTRO)
        if not path:
            return
        try:
            est = E.leer(path)
        except (E.ErrorEstilo, OSError) as e:
            self.ctx.toast(str(e), "ERROR")
            return
        self.ctx.settings.setValue("dir_sty", os.path.dirname(path))
        for p in _paneles:
            p.stop()
        self.ctx.estilo = est
        for p in _paneles:
            p.intro_sel = None
            p.main_sel = next((s for s in est.ordenadas() if E.tipo(s) == "main"), None)
            p.sp_tempo.setValue(round(est.tempo))
            p._refrescar()
        self.ctx.toast(f"Estilo «{est.nombre}» cargado", "OK")

    def set_disponibles(self, notas: set[int]):
        self.disp = set(notas)
        self._refrescar()

    def _refrescar(self):
        est = self.estilo
        if est is None:
            for b in self.botones.values():
                b.setEnabled(False)
                b.setVisible(True)
            for s in OPCIONALES:
                self.botones[s].setVisible(False)
            self.b_start.setEnabled(False)
            self.falta.setText("")
            return
        if self.main_sel not in est.secciones:
            self.main_sel = next((s for s in est.ordenadas() if E.tipo(s) == "main"), None)
        num, den = est.compas
        self.lbl.setText(f"{est.nombre}  ·  {est.tempo:g} BPM  ·  {num}/{den}  ·  {len(est.secciones)} secciones")
        self.lbl.setToolTip(est.path)
        for s, b in self.botones.items():
            b.setEnabled(s in est.secciones)
            if s in OPCIONALES:
                b.setVisible(s in est.secciones)
            if s in est.secciones:
                b.setToolTip(self._tip(s) + f"  ({est.compases(s)} comp.)")
        self.b_start.setEnabled(bool(self.main_sel))
        f = E.faltantes(est, self.disp) if self.disp else []
        if f:
            total = sum(est.notas().values()) or 1
            pct = 100 * sum(c for _, c in f) / total
            self.falta.setText(f"⚠ Al kit le faltan {len(f)} sonidos del estilo ({pct:.0f} % de los golpes)")
            self.falta.setToolTip(E.resumen_faltantes(est, self.disp, 40))
        else:
            self.falta.setText("✓ El kit tiene todos los sonidos del estilo" if self.disp else "")
            self.falta.setToolTip("")
        self._pintar()

    def _pintar(self):
        actual = self.player.actual if self.player else None
        main = (self.player.main if self.player else None) or self.main_sel
        for s, b in self.botones.items():
            st = "on" if s == actual else "sel" if s in (main, self.intro_sel) else ""
            if b.property("estado") != st:
                b.setProperty("estado", st)
                b.style().unpolish(b)
                b.style().polish(b)
        self.now.setText(E.etiqueta(actual) if actual else "")

    # ------------------------------------------------------------- botones
    def boton(self, s: str):
        if self.estilo is None:
            return
        t = E.tipo(s)
        if self.player is not None and self.player.sonando:
            self.player.pedir(s)
        elif t == "intro":
            self.intro_sel = None if self.intro_sel == s else s
        elif t == "main":
            self.main_sel = s
        elif t in ("ending", "break"):
            # parado: escucharlo suelto
            self.start(s)
            return
        self._pintar()

    def start_stop(self):
        if self.player is not None and self.player.sonando:
            self.stop()
        else:
            self.start(self.intro_sel or self.main_sel)

    def start(self, seccion):
        est = self.estilo
        if est is None or not seccion:
            return
        self.stop()
        if self.al_iniciar:
            self.al_iniciar()
        try:
            tocar, disp = self.factory()
        except Exception as e:  # noqa: BLE001
            self.ctx.toast(str(e), "ERROR")
            return
        if not disp:
            self.ctx.toast("Abre un kit primero.", "AVISO")
            return
        bridge = self.ctx.bridge
        self.player = E.Reproductor(est, tocar, disp, lambda _s: bridge.sig.emit(lambda _: self._cambio(), None))
        self.player.autofill = self.chk_fill.isChecked()
        self.player.bpm = float(self.sp_tempo.value())
        if self.main_sel:
            self.player.main = self.main_sel
        if E.tipo(seccion) in ("ending", "break"):
            # suelto: que no siga con un Main al terminar
            self.player.main = None
        self.player.start(seccion)
        self.intro_sel = None
        self.b_start.setText("  Stop")
        self.b_start.setIcon(icon("stop", "#1a1007", 16))
        self._pintar()

    def _cambio(self):
        if self.player is not None and self.player.actual is None:
            if self.player.main:
                self.main_sel = self.player.main
            self.player = None
            self.b_start.setText("  Start")
            self.b_start.setIcon(icon("play", "#1a1007", 16))
        self._pintar()

    def stop(self):
        if self.player is not None:
            p = self.player
            self.player = None
            if p.main:
                self.main_sel = p.main
            p.al_cambiar = None
            p.stop()
        self.b_start.setText("  Start")
        self.b_start.setIcon(icon("play", "#1a1007", 16))
        self._pintar()

    def showEvent(self, e):
        self._refrescar()
        super().showEvent(e)
