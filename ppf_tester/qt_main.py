"""PPF Tester — aplicación de escritorio (Qt).

Ejecutar:  python qt_main.py [archivo.ppf]
Desarrollado por Angel Cm · https://angelcm.com
"""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import (QEasingCurve, QObject, QPropertyAnimation, QRect, QSettings, Qt, QTimer,  # noqa: E402
                            Signal)
from PySide6.QtGui import QIcon, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout,  # noqa: E402
                               QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

import analisis as A  # noqa: E402
import reporte as R  # noqa: E402
from ppf_format import load_pack  # noqa: E402
from ppf_tester import _safe, _write_wav, full_analysis  # noqa: E402
from qt_fx import FadeStack, Logo, Splash, StageBackground, Toast, caption, card, icon, paint_logo  # noqa: E402
from qt_pages import KeyboardPage, ReviewPage, SamplesPage, btn, hbox, vbox  # noqa: E402
from qt_pages2 import ImprovePage, ListenPage  # noqa: E402
from qt_theme import C, dark_titlebar, font, rgba, set_tema, stylesheet  # noqa: E402
import idioma  # noqa: E402
import registro  # noqa: E402
from idioma import tr, traducir_arbol  # noqa: E402
from version import AUTOR, REPO, WEB, __version__ as VERSION  # noqa: E402

APP = "PPF Tester"
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


# =============================================================== utilidades
def abrir_carpeta(path: str):
    """Abre una carpeta o archivo con la aplicación del sistema (Windows, macOS o Linux)."""
    import subprocess
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as e:
        registro.log.warning("No se pudo abrir %s: %s", path, e)


class Bridge(QObject):
    """Lleva resultados de hilos de fondo al hilo de la interfaz."""
    sig = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.sig.connect(lambda cb, res: cb(res))


class AudioHub:
    """Salida de audio, entrada en vivo y MIDI compartidos por todas las páginas."""

    def __init__(self):
        self._mixer = None
        self._live = None
        self._live_dev = None
        self._midi = None
        self._midi_port = None

    def mixer(self):
        if self._mixer is None:
            import motor
            self._mixer = motor.Mixer()
        return self._mixer

    def play(self, buf, group=0, note=-1):
        self.mixer().play(buf, group, note)

    def stop(self):
        if self._mixer is not None:
            self._mixer.stop()

    def live(self, dev, monitor=False):
        import motor
        if dev is None:
            raise RuntimeError("Elige la entrada de audio en «Prueba en el teclado».")
        if self._live is not None and self._live_dev != dev:
            self.close_live()
        if self._live is None:
            self._live = motor.LiveInput(dev, monitor=monitor)
            self._live_dev = dev
        self._live.monitor = monitor
        return self._live

    def close_live(self):
        if self._live is not None:
            self._live.close()
            self._live = None

    def input_level(self) -> float:
        return self._live.level if self._live is not None else 0.0

    def level(self) -> float:
        out = self._mixer.peak if self._mixer is not None else 0.0
        return min(1.0, max(out * 1.4, self.input_level() * 1.4))

    def midi(self, port):
        import midi_test
        if port is None:
            raise RuntimeError("Elige la salida MIDI del PSR en «Prueba en el teclado».")
        if self._midi is None or self._midi_port != port:
            if self._midi is not None:
                self._midi.close()
            self._midi = midi_test.MidiOut(port)
            self._midi_port = port
        return self._midi

    def close(self):
        for o in (self._mixer, self._live):
            if o is not None:
                try:
                    o.close()
                except Exception:  # noqa: BLE001
                    pass
        if self._midi is not None:
            try:
                self._midi.close()
            except Exception:  # noqa: BLE001
                pass


# ================================================================ inicio vacío
class EmptyPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        c = QFrame()
        c.setObjectName("Drop")
        c.setStyleSheet(f"QFrame#Drop {{ background: {rgba('card', 215)}; border: 1.5px dashed {C['line2']}; border-radius: 22px; }}")
        c.setFixedWidth(620)
        l = QVBoxLayout(c)
        l.setContentsMargins(48, 40, 48, 36)
        l.setSpacing(12)
        lg = Logo(84)
        l.addWidget(lg, 0, Qt.AlignmentFlag.AlignHCenter)
        t = QLabel("Arrastra aquí tu kit .ppf o una carpeta de WAV")
        t.setStyleSheet("font-size: 20pt; font-weight: 300; background: transparent;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(t)
        s = QLabel("Yamaha Expansion Manager · PSR-S670 · S770 · S775 · S970 · S975")
        s.setObjectName("Mut")
        s.setStyleSheet("background: transparent;")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(s)
        b = btn("Abrir archivo .ppf", "folder", primary=True)
        b.setFixedWidth(240)
        b.clicked.connect(lambda: ctx.open_file())
        b2 = btn("Crear kit desde mis WAV", "sparkle")
        b2.setFixedWidth(240)
        b2.clicked.connect(lambda: ctx.go("import"))
        l.addSpacing(8)
        rowb = QHBoxLayout()
        rowb.addStretch(1)
        rowb.addWidget(b)
        rowb.addWidget(b2)
        rowb.addStretch(1)
        l.addLayout(rowb)
        l.addSpacing(10)
        self.rec_cap = caption("Recientes")
        self.rec_cap.setStyleSheet("background: transparent;")
        l.addWidget(self.rec_cap)
        self.recent = QListWidget()
        self.recent.setFixedHeight(150)
        self.recent.setStyleSheet("background: transparent;")
        self.recent.itemActivated.connect(lambda it: ctx.open_file(it.data(Qt.ItemDataRole.UserRole)))
        self.recent.itemClicked.connect(lambda it: ctx.open_file(it.data(Qt.ItemDataRole.UserRole)))
        l.addWidget(self.recent)
        row.addWidget(c)
        row.addStretch(1)
        root.addLayout(row)
        root.addStretch(2)

    def refresh(self, files):
        self.recent.clear()
        for f in files:
            it = QListWidgetItem(icon("doc", "gold", 16), f"  {os.path.basename(f)}   —   {os.path.dirname(f)}")
            it.setData(Qt.ItemDataRole.UserRole, f)
            self.recent.addItem(it)
        self.recent.setVisible(bool(files))
        self.rec_cap.setVisible(bool(files))


# ================================================================== diálogos
class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {APP}")
        self.setFixedSize(520, 360)
        bg = StageBackground(self)
        bg.setGeometry(self.rect())
        bg.level_fn = parent.audio.level
        ov = QWidget(self)
        ov.setGeometry(self.rect())
        l = QVBoxLayout(ov)
        l.setContentsMargins(30, 26, 30, 24)
        l.setSpacing(6)
        lg = Logo(96)
        l.addWidget(lg, 0, Qt.AlignmentFlag.AlignHCenter)
        t = QLabel("PPF TESTER")
        t.setStyleSheet("font-size: 24pt; font-weight: 300; letter-spacing: 3px; background: transparent;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(t)
        v = QLabel(f"Versión {VERSION} · Sample Lab para Yamaha PSR-S")
        v.setStyleSheet(f"color: {C['mut']}; background: transparent;")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(v)
        l.addSpacing(12)
        a = QLabel(f"{tr('Desarrollado por')} <b>{AUTOR}</b>")
        a.setStyleSheet("font-size: 11pt; background: transparent;")
        a.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(a)
        row = QHBoxLayout()
        row.addStretch(1)
        for txt, ic, url in (("angelcm.com", "web", WEB), ("GitHub", "github", REPO)):
            b = btn(txt, ic)
            b.clicked.connect(lambda _=False, u=url: webbrowser.open(u))
            row.addWidget(b)
        row.addStretch(1)
        l.addSpacing(6)
        l.addLayout(row)
        l.addStretch(1)
        lic = QLabel("Licencia MIT · No afiliado a Yamaha Corporation")
        lic.setObjectName("Mut")
        lic.setStyleSheet("background: transparent; font-size: 8pt;")
        lic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(lic)
        traducir_arbol(self)
        dark_titlebar(self)


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(420)
        l = vbox(self, 24, 12)
        t = QLabel("Ajustes")
        t.setObjectName("H1")
        l.addWidget(t)
        s = parent.settings
        self.anim = QCheckBox("Animaciones de fondo (luces de escenario)")
        self.anim.setChecked(s.value("anim", True, type=bool))
        self.upd = QCheckBox("Buscar actualizaciones al iniciar")
        self.upd.setChecked(s.value("updates", True, type=bool))
        l.addWidget(self.anim)
        l.addWidget(self.upd)
        h = QLabel("Desactiva las animaciones si tu PC es lento o prefieres la app quieta.")
        h.setObjectName("Mut")
        h.setWordWrap(True)
        l.addWidget(h)
        from PySide6.QtWidgets import QComboBox, QGridLayout
        g = QGridLayout()
        g.addWidget(QLabel("Idioma"), 0, 0)
        self.cb_lang = QComboBox()
        for code, name in idioma.IDIOMAS.items():
            self.cb_lang.addItem(name, code)
        self.cb_lang.setCurrentIndex(list(idioma.IDIOMAS).index(s.value("idioma", "es")))
        g.addWidget(self.cb_lang, 0, 1)
        g.addWidget(QLabel("Tema"), 1, 0)
        self.cb_theme = QComboBox()
        self.cb_theme.addItem("Oscuro", "oscuro")
        self.cb_theme.addItem("Claro", "claro")
        self.cb_theme.setCurrentIndex(1 if s.value("tema", "oscuro") == "claro" else 0)
        g.addWidget(self.cb_theme, 1, 1)
        l.addLayout(g)
        n = QLabel("El idioma y el tema se aplican al reiniciar la app.")
        n.setObjectName("Mut")
        l.addWidget(n)
        tools = hbox(None, 0, 8)
        for txt, ic, fn in (("Buscar actualizaciones", "refresh", lambda: parent.check_updates(manual=True)),
                            ("Reportar un problema", "github", lambda: webbrowser.open(registro.url_reporte(REPO, VERSION))),
                            ("Abrir registros", "folder", lambda: abrir_carpeta(registro.CARPETA))):
            b = btn(txt, ic)
            b.clicked.connect(fn)
            tools.addWidget(b)
        l.addLayout(tools)
        row = hbox(None, 0, 8)
        row.addStretch(1)
        ok = btn("Guardar", primary=True)
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        l.addLayout(row)
        traducir_arbol(self)
        dark_titlebar(self)


# ================================================================ ventana
NAV = [("import", "Importar WAV", "folder"), ("library", "Biblioteca", "library"), ("voices", "Voces y pads", "music"),
       ("samples", "Muestras", "wave"), ("listen", "Escuchar", "headphones"), ("live", "En vivo", "pads"),
       ("improve", "Mejorar kit", "sparkle"), ("review", "Revisión", "check"), ("keyboard", "Teclado", "piano"),
       ("set", "Set del teclado", "stack")]
SIN_PACK = {"import", "library", "voices", "set"}     # páginas que no necesitan un kit abierto


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP)
        ico = os.path.join(BASE, "ppf_tester.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))
        self.settings = QSettings("AngelCm", "PPFTester")
        self.audio = AudioHub()
        self.bridge = Bridge()
        self.pack = None
        self.kits, self.waves, self.rep_by_uid = [], [], {}
        self.modified = False
        self.undo_stack, self.redo_stack = [], []
        self.setAcceptDrops(True)
        # La recolección de basura de Python solo en el hilo de la interfaz: si un hilo de fondo
        # libera objetos de Qt (widgets ya descartados) la app puede cerrarse de golpe.
        import gc
        gc.disable()
        self._gc_n = 0

        def _gc():
            self._gc_n += 1
            gc.collect(2 if self._gc_n % 20 == 0 else 0)
        self._gc_timer = QTimer(self)
        self._gc_timer.timeout.connect(_gc)
        self._gc_timer.start(500)
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self._build()
        dark_titlebar(self)
        self.bg.set_animated(self.settings.value("anim", True, type=bool))
        self.stack.animated = self.settings.value("anim", True, type=bool)
        self._refresh_recent()
        if self.settings.value("updates", True, type=bool):
            QTimer.singleShot(2500, self.check_updates)

    # ---------------------------------------------------------------- layout
    def _build(self):
        self.bg = StageBackground()
        self.bg.level_fn = self.audio.level
        self.setCentralWidget(self.bg)
        outer = QHBoxLayout(self.bg)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # barra lateral (translúcida: deja ver las luces)
        side = QFrame()
        side.setFixedWidth(232)
        side.setStyleSheet(f"QFrame#Side {{ background: {rgba('side', 170)}; border-right: 1px solid {rgba('line2', 120)}; }}")
        side.setObjectName("Side")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(18, 22, 18, 16)
        sl.setSpacing(4)
        brand = QHBoxLayout()
        self.logo = Logo(44)
        brand.addWidget(self.logo)
        bt = QVBoxLayout()
        bt.setSpacing(0)
        n = QLabel("PPF TESTER")
        n.setStyleSheet("font-size: 14pt; font-weight: 300; letter-spacing: 2px; background: transparent;")
        bt.addWidget(n)
        s = QLabel("SAMPLE LAB")
        s.setStyleSheet(f"color: {C['mut']}; font-size: 7pt; font-weight: 700; letter-spacing: 2px; background: transparent;")
        bt.addWidget(s)
        brand.addLayout(bt)
        brand.addStretch(1)
        sl.addLayout(brand)
        sl.addSpacing(28)
        self.nav_area = QWidget()
        na = QVBoxLayout(self.nav_area)
        na.setContentsMargins(0, 0, 0, 0)
        na.setSpacing(4)
        self.indicator = QFrame(self.nav_area)
        self.indicator.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(244,184,96,60), stop:1 rgba(244,184,96,0));"
                                     f" border-left: 3px solid {C['gold']}; border-radius: 8px;")
        self.nav = {}
        for i, (key, label, ic) in enumerate(NAV):
            b = QPushButton(f"   {label}")
            b.setIcon(icon(ic, "fg", 18))
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("QPushButton { text-align: left; background: transparent; border: none; padding: 9px 14px;"
                            f" color: {C['mut']}; font-size: 10.5pt; border-radius: 8px; }}"
                            "QPushButton:hover { color: #ffffff; background: rgba(255,255,255,10); }"
                            f"QPushButton:checked {{ color: {C['fg']}; font-weight: 600; }}"
                            f"QPushButton:disabled {{ color: {C['dim']}; }}")
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            na.addWidget(b)
            self.nav[key] = b
        self.indicator.lower()
        sl.addWidget(self.nav_area)
        sl.addStretch(1)
        self.upd_btn = btn("Nueva versión disponible", "export")
        self.upd_btn.setVisible(False)
        sl.addWidget(self.upd_btn)
        cr = QLabel(f"<span style='color:{C['mut']}'>{tr('Desarrollado por')}</span><br>"
                    f"<a href='{WEB}' style='color:{C['gold']}; text-decoration:none; font-weight:700'>{AUTOR}</a>"
                    f"<span style='color:{C['mut']}'> · </span><a href='{WEB}' style='color:{C['fg']}'>angelcm.com</a>")
        cr.setOpenExternalLinks(True)
        cr.setStyleSheet("background: transparent; font-size: 9pt;")
        sl.addWidget(cr)
        row = QHBoxLayout()
        for ic, tip, fn in (("gear", "Ajustes", self.open_settings), ("info", "Acerca de", self.about),
                            ("github", "Código en GitHub", lambda: webbrowser.open(REPO))):
            b = QPushButton()
            b.setIcon(icon(ic, "mut", 18))
            b.setToolTip(tip)
            b.setObjectName("Ghost")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v = QLabel(f"v{VERSION}")
        v.setStyleSheet(f"color:{C['dim']}; background: transparent; font-size: 8pt;")
        row.addWidget(v)
        sl.addLayout(row)
        outer.addWidget(side)

        # contenido
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(28, 22, 28, 18)
        ml.setSpacing(16)
        head = QHBoxLayout()
        ht = QVBoxLayout()
        ht.setSpacing(2)
        self.h_title = QLabel("Bienvenido")
        self.h_title.setStyleSheet("font-size: 22pt; font-weight: 300; background: transparent;")
        ht.addWidget(self.h_title)
        self.h_sub = QLabel("Abre un kit para empezar.")
        self.h_sub.setStyleSheet(f"color: {C['mut']}; background: transparent;")
        ht.addWidget(self.h_sub)
        head.addLayout(ht)
        head.addStretch(1)
        self.b_open = btn("Abrir", "folder", primary=True, tip="Abrir .ppf (Ctrl+O)")
        self.b_open.clicked.connect(lambda: self.open_file())
        self.b_save = btn("Guardar como", "save", tip="Guardar .ppf (Ctrl+S)")
        self.b_save.clicked.connect(self.save_as)
        self.b_rep = btn("Informe", "doc", tip="Informe HTML")
        self.b_rep.clicked.connect(self.open_report)
        self.b_wav = btn("WAV", "export", tip="Exportar todas las muestras a WAV")
        self.b_wav.clicked.connect(self.export_wav)
        for b in (self.b_open, self.b_save, self.b_rep, self.b_wav):
            head.addWidget(b)
        ml.addLayout(head)

        self.stats = card()
        st = QHBoxLayout(self.stats)
        st.setContentsMargins(20, 12, 20, 12)
        st.setSpacing(34)
        self.stat = {}
        for key, lab in (("title", "Pack"), ("voices", "Voces"), ("waves", "Muestras"), ("mem", "Audio"),
                         ("ERROR", "Errores"), ("AVISO", "Avisos")):
            b = QVBoxLayout()
            b.setSpacing(0)
            b.addWidget(caption(lab))
            v = QLabel("—")
            col = C.get(key, C["fg"])
            v.setStyleSheet(f"font-size: {'15pt; font-weight: 300' if key == 'title' else '14pt; font-weight: 700'}; color: {col};")
            b.addWidget(v)
            self.stat[key] = v
            st.addLayout(b, 3 if key == "title" else 1)
        ml.addWidget(self.stats)

        self.stack = FadeStack()
        self.empty = EmptyPage(self)
        self.stack.addWidget(self.empty)
        self.samples = SamplesPage(self)
        self.keyboard = KeyboardPage(self)
        self.listen = ListenPage(self)
        self.improve = ImprovePage(self)
        self.review = ReviewPage(self)
        from qt_import import ImportPage
        from qt_pages3 import LibraryPage, LivePage, SetPage, VoicesPage
        self.importer = ImportPage(self)
        self.library = LibraryPage(self)
        self.voices = VoicesPage(self)
        self.live = LivePage(self)
        self.set_page = SetPage(self)
        self.pages = {"import": self.importer, "library": self.library, "voices": self.voices, "samples": self.samples,
                      "listen": self.listen, "live": self.live, "improve": self.improve, "review": self.review,
                      "keyboard": self.keyboard, "set": self.set_page}
        for p in self.pages.values():
            self.stack.addWidget(p)
        ml.addWidget(self.stack, 1)
        outer.addWidget(main, 1)

        self.toast_w = Toast(self.bg)
        self.drop_hint = QLabel("Suelta el archivo .ppf para abrirlo", self.bg)
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet(f"background: {rgba('bg', 200)}; border: 2px dashed {C['gold']}; border-radius: 24px;"
                                     " font-size: 20pt; font-weight: 300;")
        self.drop_hint.hide()

        QShortcut(QKeySequence.StandardKey.Open, self, activated=lambda: self.open_file())
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save_as)
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self.redo)
        for i, (key, _, _) in enumerate(NAV[:9]):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda k=key: self.go(k))
        traducir_arbol(self)
        self.logo_timer = QTimer(self)
        self.logo_timer.timeout.connect(self._pulse_logo)
        self.logo_timer.start(40)
        self._set_loaded(False)

    def _pulse_logo(self):
        self.logo.pulse = self.audio.level()
        self.logo.update()

    def _set_loaded(self, on):
        for k, b in self.nav.items():
            b.setEnabled(on or k in SIN_PACK)
        for b in (self.b_save, self.b_rep, self.b_wav):
            b.setEnabled(on)
        self.stats.setVisible(on and self.current_key() not in SIN_PACK)
        if not on and self.current_key() not in SIN_PACK:
            self.stack.fade_to(0)
            self.indicator.hide()

    def go(self, key):
        if self.pack is None and key not in SIN_PACK:
            return
        page = self.pages[key]
        self.stack.fade_to(self.stack.indexOf(page))
        for k, b in self.nav.items():
            b.setChecked(k == key)
        self.stats.setVisible(self.pack is not None and key not in SIN_PACK)
        self.h_title.setText(tr(page.title))
        self.h_sub.setText(tr(page.subtitle))
        traducir_arbol(page)
        target = self.nav[key].geometry()
        self.indicator.show()
        if self.indicator.width() == 0 or not self.settings.value("anim", True, type=bool):
            self.indicator.setGeometry(target)
        else:
            a = QPropertyAnimation(self.indicator, b"geometry", self)
            a.setDuration(280)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.setStartValue(self.indicator.geometry())
            a.setEndValue(target)
            a.start()
            self._ind_anim = a
        if key != "listen":
            self.listen.stop_groove()
        if key != "live":
            self.live.stop()

    def current_key(self):
        w = self.stack.currentWidget()
        return next((k for k, p in self.pages.items() if p is w), None)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.drop_hint.setGeometry(self.bg.rect().adjusted(40, 40, -40, -40))
        k = self.current_key()
        if k:
            QTimer.singleShot(0, lambda: self.indicator.setGeometry(self.nav[k].geometry()))

    # ---------------------------------------------------------------- hilos
    def run_bg(self, fn, done, err=None):
        def work():
            try:
                res = fn()
                self.bridge.sig.emit(done, res)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                registro.log.exception("Error en tarea de fondo")
                msg = str(e)

                def fail(_):
                    if err:
                        err()
                    self.toast(f"Error: {msg}", "ERROR", 6000)
                self.bridge.sig.emit(fail, None)
        threading.Thread(target=work, daemon=True).start()

    def toast(self, msg, kind="OK", ms=3200):
        if kind == "ERROR":
            registro.log.warning("Aviso de error mostrado: %s", msg)
        self.toast_w.show_msg(tr(msg), kind, ms)

    # ---------------------------------------------------------------- archivos
    def open_file(self, path=None):
        if not path:
            start = os.path.dirname(self.pack.path) if self.pack else ""
            path, _ = QFileDialog.getOpenFileName(self, "Abrir pack de Yamaha", start, "Yamaha Expansion Manager (*.ppf);;Todos (*.*)")
        if not path:
            return
        if not os.path.exists(path):
            self.toast("No encuentro ese archivo.", "ERROR")
            self._refresh_recent()
            return
        self.h_sub.setText(f"Analizando {os.path.basename(path)}…")
        self.run_bg(lambda: self._load(path), self._loaded)

    def _load(self, path):
        pack = load_pack(path)
        kits, waves = full_analysis(pack)
        return pack, kits, waves

    def _loaded(self, res, keep_page=False):
        self.pack, self.kits, self.waves = res
        self.rep_by_uid = {w.uid: w for w in self.waves}
        p = self.pack
        cnt = lambda lv: sum(x.level == lv for w in self.waves for x in w.problems) + sum(x.level == lv for k in self.kits for x in k.problems)
        self.stat["title"].setText(p.title)
        self.stat["voices"].setText(str(len(p.voices)))
        self.stat["waves"].setText(str(len(p.waves)))
        self.stat["mem"].setText(f"{A.memory_bytes(p) / 1e6:.2f} MB")
        self.stat["ERROR"].setText(str(cnt("ERROR") + len(p.errors)))
        self.stat["AVISO"].setText(str(cnt("AVISO")))
        for page in self.pages.values():
            page.load(p)
        self._set_loaded(True)
        if not keep_page:
            self.modified = False
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.add_recent(p.path)
            self.go("samples")
            self.toast(f"{os.path.basename(p.path)} listo", "OK")
        else:
            self.go(self.current_key() or "samples")
        self.setWindowTitle(f"{APP} — {os.path.basename(p.path)}{' *' if self.modified else ''}")

    # ---------------------------------------------------------------- deshacer
    def snapshot(self):
        """Guarda el estado actual del kit antes de un cambio (para Ctrl+Z)."""
        if self.pack is None:
            return
        self.undo_stack.append((self.pack.to_bytes(), self.pack.path, self.modified))
        del self.undo_stack[:-25]
        self.redo_stack.clear()

    def _restore(self, state):
        from ppf_format import load_pack_bytes
        data, path, modified = state
        pack = load_pack_bytes(data, path)
        kits, waves = full_analysis(pack)
        self.modified = modified
        row = self.samples.tbl.currentRow()
        self._loaded((pack, kits, waves), keep_page=True)
        if row >= 0:
            self.samples.tbl.selectRow(min(row, self.samples.tbl.rowCount() - 1))

    def undo(self):
        if self.current_key() == "import":
            self.importer.undo()
            return
        if not self.undo_stack:
            self.toast("No hay nada que deshacer.", "INFO", 1800)
            return
        self.redo_stack.append((self.pack.to_bytes(), self.pack.path, self.modified))
        self._restore(self.undo_stack.pop())
        self.toast("Deshecho", "INFO", 1500)

    def redo(self):
        if self.current_key() == "import":
            self.importer.redo()
            return
        if not self.redo_stack:
            self.toast("No hay nada que rehacer.", "INFO", 1800)
            return
        self.undo_stack.append((self.pack.to_bytes(), self.pack.path, self.modified))
        self._restore(self.redo_stack.pop())
        self.toast("Rehecho", "INFO", 1500)

    def mark_modified(self, msg):
        self.modified = True
        row = self.samples.tbl.currentRow()
        kits, waves = full_analysis(self.pack)
        self._loaded((self.pack, kits, waves), keep_page=True)
        if row >= 0:
            self.samples.tbl.selectRow(min(row, self.samples.tbl.rowCount() - 1))
        self.toast(msg + " · sin guardar", "INFO")

    def save_as(self):
        if not self.pack:
            return
        src = self.pack.path
        out, _ = QFileDialog.getSaveFileName(self, "Guardar pack", os.path.join(os.path.dirname(src), os.path.splitext(os.path.basename(src))[0] + "_editado.ppf"),
                                             "Yamaha Expansion Manager (*.ppf)")
        if not out:
            return
        self.pack.save(out)
        chk = load_pack(out)
        if chk.errors:
            QMessageBox.warning(self, APP, "El archivo guardado no pasó la verificación:\n" + "\n".join(chk.errors))
            return
        self.pack.path = out
        self.modified = False
        self.add_recent(out)
        self.setWindowTitle(f"{APP} — {os.path.basename(out)}")
        self.toast(f"Guardado: {os.path.basename(out)}", "OK")

    def open_report(self):
        if not self.pack:
            return
        out = os.path.splitext(self.pack.path)[0] + "_informe.html"
        R.write_report(out, self.pack, self.kits, self.waves)
        webbrowser.open("file:///" + os.path.abspath(out).replace("\\", "/"))
        self.toast("Informe abierto en el navegador", "OK")

    def export_wav(self):
        if not self.pack:
            return
        folder = QFileDialog.getExistingDirectory(self, "Carpeta para los WAV")
        if not folder:
            return
        pack = self.pack

        def job():
            for w in pack.waves.values():
                _write_wav(os.path.join(folder, _safe(w.name) + ".wav"), w.samples, w.rate)
            return folder

        def done(f):
            self.toast(f"{len(pack.waves)} WAV exportados", "OK")
            abrir_carpeta(f)
        self.run_bg(job, done)

    def add_recent(self, path):
        files = [f for f in (self.settings.value("recent", [], type=list) or []) if f != path]
        files.insert(0, path)
        self.settings.setValue("recent", files[:8])
        self._refresh_recent()

    def _refresh_recent(self):
        files = [f for f in (self.settings.value("recent", [], type=list) or []) if os.path.exists(f)]
        self.empty.refresh(files)

    # ---------------------------------------------------------------- arrastrar
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith((".ppf", ".wav")) or os.path.isdir(u.toLocalFile())
                                          for u in e.mimeData().urls()):
            es_ppf = any(u.toLocalFile().lower().endswith(".ppf") for u in e.mimeData().urls())
            self.drop_hint.setText("Suelta para abrir el kit" if es_ppf else "Suelta la carpeta para crear un kit con tus WAV")
            e.acceptProposedAction()
            self.drop_hint.setGeometry(self.bg.rect().adjusted(40, 40, -40, -40))
            self.drop_hint.raise_()
            self.drop_hint.show()

    def dragLeaveEvent(self, e):
        self.drop_hint.hide()

    def dropEvent(self, e):
        self.drop_hint.hide()
        for u in e.mimeData().urls():
            f = u.toLocalFile()
            if f.lower().endswith(".ppf"):
                self.open_file(f)
                break
            if os.path.isdir(f) or f.lower().endswith(".wav"):
                self.go("import")
                self.importer.load_folder(f if os.path.isdir(f) else os.path.dirname(f))
                break

    # ---------------------------------------------------------------- teclado
    def keyPressEvent(self, e):
        if self.current_key() == "listen" and self.listen.key_press(e):
            e.accept()
            return
        if self.current_key() == "live" and self.live.key_press(e):
            e.accept()
            return
        if e.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
            return
        super().keyPressEvent(e)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ---------------------------------------------------------------- extras
    def about(self):
        AboutDialog(self).exec()

    def open_settings(self):
        d = SettingsDialog(self)
        if d.exec():
            self.settings.setValue("anim", d.anim.isChecked())
            self.settings.setValue("updates", d.upd.isChecked())
            cambio = (d.cb_lang.currentData() != self.settings.value("idioma", "es")
                      or d.cb_theme.currentData() != self.settings.value("tema", "oscuro"))
            self.settings.setValue("idioma", d.cb_lang.currentData())
            self.settings.setValue("tema", d.cb_theme.currentData())
            if cambio and QMessageBox.question(self, APP, tr("El idioma y el tema se aplican al reiniciar la app.") + "\n\n"
                                               + tr("Reiniciar ahora") + "?") == QMessageBox.StandardButton.Yes:
                self.restart()
                return
            self.bg.set_animated(d.anim.isChecked())
            self.stack.animated = d.anim.isChecked()
            self.toast("Ajustes guardados", "OK")

    def check_updates(self, manual=False):
        def job():
            req = urllib.request.Request("https://api.github.com/repos/angel-cm-dev/ppf-tester/releases/latest",
                                         headers={"User-Agent": "PPF-Tester", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode("utf-8"))

        def done(data):
            tag = data.get("tag_name", "")
            try:
                new = tuple(int(x) for x in tag.lstrip("v").split("."))
                cur = tuple(int(x) for x in VERSION.split("."))
            except ValueError:
                return
            if new > cur:
                self._update_data = data
                self.upd_btn.setText(f"  {tr('Actualizar a')} {tag}")
                self.upd_btn.setVisible(True)
                try:
                    self.upd_btn.clicked.disconnect()
                except (RuntimeError, TypeError):
                    pass
                self.upd_btn.clicked.connect(self.update_app)
                self.toast(f"Hay una versión nueva: {tag}", "INFO", 6000)
            elif manual:
                self.toast("Tienes la última versión.", "OK")

        def work():
            try:
                res = job()
                self.bridge.sig.emit(done, res)
            except Exception as e:  # noqa: BLE001
                registro.log.info("No se pudo buscar actualizaciones: %s", e)
                if manual:
                    self.bridge.sig.emit(lambda _: self.toast("Sin conexión con GitHub.", "AVISO"), None)
        threading.Thread(target=work, daemon=True).start()

    def update_app(self):
        """Descarga la versión nueva y reemplaza el ejecutable al cerrar."""
        data = getattr(self, "_update_data", None) or {}
        tag = data.get("tag_name", "")
        url = data.get("html_url", REPO + "/releases/latest")
        asset = next((a for a in data.get("assets", []) if a.get("name") == "PPF-Tester.exe"), None)
        if not getattr(sys, "frozen", False) or asset is None or sys.platform != "win32":
            webbrowser.open(url)        # versión de código: abrir la página de descargas
            return
        if QMessageBox.question(self, APP, f"¿Descargar e instalar PPF Tester {tag}?\n\nLa app se cerrará y se abrirá la versión nueva.") != QMessageBox.StandardButton.Yes:
            return
        import tempfile
        destino = os.path.join(tempfile.gettempdir(), f"PPF-Tester-{tag}.exe")
        self.upd_btn.setEnabled(False)
        self.toast(f"Descargando {tag}…", "INFO", 8000)

        def job():
            req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "PPF-Tester"})
            with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    f.write(b)
            if os.path.getsize(destino) != asset.get("size", os.path.getsize(destino)):
                raise RuntimeError("La descarga está incompleta.")
            return destino

        def done(nuevo):
            import subprocess
            exe = sys.executable
            bat = os.path.join(os.path.dirname(nuevo), "ppf_tester_update.bat")
            with open(bat, "w", encoding="utf-8") as f:
                f.write("@echo off\r\n:wait\r\n"
                        f'tasklist /FI "PID eq {os.getpid()}" | find "{os.getpid()}" >nul && (timeout /t 1 >nul & goto wait)\r\n'
                        f'copy /Y "{nuevo}" "{exe}" >nul\r\nstart "" "{exe}"\r\ndel "%~f0"\r\n')
            subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000 | 0x00000008)   # sin ventana, desacoplado
            registro.log.info("Actualizando a %s", tag)
            self.modified = False
            self.close()

        self.run_bg(job, done, lambda: self.upd_btn.setEnabled(True))

    def restart(self):
        from PySide6.QtCore import QProcess
        args = sys.argv[1:] if getattr(sys, "frozen", False) else [os.path.abspath(__file__)] + sys.argv[1:]
        QProcess.startDetached(sys.executable, args)
        self.close()

    def closeEvent(self, e):
        if self.modified and QMessageBox.question(self, APP, "Hay cambios sin guardar. ¿Salir de todas formas?") != QMessageBox.StandardButton.Yes:
            e.ignore()
            return
        self.listen.stop_groove()
        self.audio.close()
        super().closeEvent(e)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AngelCm.PPFTester")
        except Exception:  # noqa: BLE001
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    registro.iniciar(VERSION)
    pre = QSettings("AngelCm", "PPFTester")
    set_tema(pre.value("tema", "oscuro"))
    idioma.set_idioma(pre.value("idioma", "es"))
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setOrganizationName("AngelCm")
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    ico = os.path.join(BASE, "ppf_tester.ico")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    settings = QSettings("AngelCm", "PPFTester")
    splash = None
    if settings.value("anim", True, type=bool):
        splash = Splash(VERSION, AUTOR)
        splash.show()
        app.processEvents()
    win = MainWindow()
    arg = next((a for a in sys.argv[1:] if a.lower().endswith(".ppf") and os.path.exists(a)), None)

    def start():
        if splash:
            splash.close()
        win.showMaximized()
        if arg:
            win.open_file(arg)
    QTimer.singleShot(1400 if splash else 0, start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
