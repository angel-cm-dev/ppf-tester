"""Páginas Qt de la versión 5: Biblioteca, Voces y pads, Set del teclado, En vivo,
asistente de prueba en el PSR y exportación de demos."""
from __future__ import annotations

import os

import numpy as np
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

import modelos
from ppf_format import load_pack, note_name
from qt_fx import GlowPiano, LevelMeter, MemoryBars, caption, card, icon
from qt_pages import Page, btn, cell, hbox, problems_html, table, text_view, vbox
from qt_pages2 import slider
from qt_theme import C, dark_titlebar, font, q


def _sel_rows(tbl) -> list[int]:
    return sorted({i.row() for i in tbl.selectedIndexes()})


# ==================================================================== biblioteca
class LibraryPage(Page):
    title = "Biblioteca de muestras"
    subtitle = "Tus golpes favoritos guardados para reutilizarlos. Busca, etiqueta y arma kits nuevos desde aquí."

    def __init__(self, ctx):
        super().__init__(ctx)
        import biblioteca
        import importar_wav as I
        self.I = I
        self.lib = biblioteca.Biblioteca()
        self.items = []
        root = vbox(self, 0, 12)

        top = card()
        tl = hbox(top, 16, 10)
        tl.setContentsMargins(16, 12, 16, 12)
        self.e_buscar = QLineEdit()
        self.e_buscar.setPlaceholderText("Buscar: caja seca, worship, room…")
        self.e_buscar.textChanged.connect(self.refresh)
        tl.addWidget(self.e_buscar, 2)
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItem("Todas las piezas", None)
        for t in I.TIPOS:
            self.cb_tipo.addItem(I.PIEZAS[t][0], t)
        self.cb_tipo.currentIndexChanged.connect(self.refresh)
        tl.addWidget(self.cb_tipo)
        self.cb_tag = QComboBox()
        self.cb_tag.currentIndexChanged.connect(self.refresh)
        tl.addWidget(self.cb_tag)
        self.chk_fav = QCheckBox("Solo favoritos")
        self.chk_fav.toggled.connect(self.refresh)
        tl.addWidget(self.chk_fav)
        b_dir = btn("Añadir carpeta", "folder", primary=True)
        b_dir.clicked.connect(self.add_folder)
        tl.addWidget(b_dir)
        self.b_pack = btn("Añadir el kit abierto", "export")
        self.b_pack.clicked.connect(self.add_pack)
        tl.addWidget(self.b_pack)
        root.addWidget(top)

        body = hbox(None, 0, 12)
        root.addLayout(body, 1)
        c = card()
        cl = vbox(c, 12, 6)
        row = hbox(None, 0, 8)
        row.addWidget(caption("Muestras"))
        row.addStretch(1)
        self.lbl_n = QLabel("")
        self.lbl_n.setObjectName("Mut")
        row.addWidget(self.lbl_n)
        cl.addLayout(row)
        self.tbl = table(["★", "Nombre", "Pieza", "Duración", "Origen", "Etiquetas"], [34, None, 130, 112, 170, 170])
        from PySide6.QtWidgets import QAbstractItemView
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl.cellDoubleClicked.connect(lambda r, _c: self.play(r))
        self.tbl.cellClicked.connect(self._clicked)
        cl.addWidget(self.tbl, 1)
        body.addWidget(c, 3)

        side = card()
        sl = vbox(side, 16, 10)
        sl.addWidget(caption("Con lo seleccionado"))
        for txt, ic, fn, tip in (
                ("Escuchar", "play", lambda: self.play(self.tbl.currentRow()), "Doble clic en la fila también la reproduce"),
                ("Favorito ★", "star", self.toggle_fav, ""),
                ("Etiquetas…", "doc", self.edit_tags, "Separa las etiquetas con comas"),
                ("Renombrar…", "doc", self.rename, ""),
                ("Kit nuevo con estas muestras", "sparkle", lambda: self.to_import(nuevo=True), "Abre «Importar WAV» con un kit vacío y estas muestras"),
                ("Añadir al kit de «Importar WAV»", "piano", lambda: self.to_import(nuevo=False), "Las pone en teclas libres del kit que estás armando"),
                ("Quitar de la biblioteca", "stop", self.remove, "")):
            b = btn(txt, ic, tip=tip or None)
            b.clicked.connect(fn)
            sl.addWidget(b)
        sl.addSpacing(10)
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("Mut")
        self.lbl_info.setWordWrap(True)
        sl.addWidget(self.lbl_info)
        sl.addStretch(1)
        body.addWidget(side, 1)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self._fill_tags()
        self.refresh()

    def load(self, pack):
        self.b_pack.setEnabled(pack is not None)

    def showEvent(self, e):
        super().showEvent(e)
        self.b_pack.setEnabled(self.ctx.pack is not None)

    def _fill_tags(self):
        cur = self.cb_tag.currentData()
        self.cb_tag.blockSignals(True)
        self.cb_tag.clear()
        self.cb_tag.addItem("Todas las etiquetas", None)
        for t in self.lib.etiquetas():
            self.cb_tag.addItem(t, t)
        i = self.cb_tag.findData(cur)
        self.cb_tag.setCurrentIndex(max(0, i))
        self.cb_tag.blockSignals(False)

    def refresh(self, *_):
        self.items = self.lib.buscar(self.e_buscar.text(), self.cb_tipo.currentData(), self.chk_fav.isChecked(), self.cb_tag.currentData())
        self.tbl.setRowCount(0)
        for m in self.items:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            st = cell("★" if m.fav else "☆", "gold" if m.fav else "dim", Qt.AlignmentFlag.AlignCenter)
            st.setToolTip("Clic para marcar como favorito")
            self.tbl.setItem(r, 0, st)
            self.tbl.setItem(r, 1, cell(m.nombre, bold=True))
            self.tbl.setItem(r, 2, cell(self.I.PIEZAS.get(m.tipo, ("?",))[0], "gold"))
            self.tbl.setItem(r, 3, cell(f"{m.dur:.2f} s · {'est.' if m.canales == 2 else 'mono'}", "mut"))
            self.tbl.setItem(r, 4, cell(m.origen, "mut"))
            self.tbl.setItem(r, 5, cell(", ".join(m.etiquetas), "mut"))
        total = len(self.lib.muestras)
        mb = sum(m.dur * 44100 * m.canales * 2 for m in self.lib.muestras.values()) / 1e6
        self.lbl_n.setText(f"{len(self.items)} de {total}")
        self.lbl_info.setText(f"La biblioteca tiene {total} muestras (≈ {mb:.0f} MB en 16 bits).\n"
                              f"Se guarda en tu carpeta de datos de PPF Tester.") if total else \
            self.lbl_info.setText("Tu biblioteca está vacía. Añade una carpeta de WAV o el kit abierto.")

    def _sel(self):
        return [self.items[r] for r in _sel_rows(self.tbl) if r < len(self.items)]

    def _clicked(self, r, c):
        if c == 0 and r < len(self.items):
            m = self.items[r]
            self.lib.editar(m.id, fav=not m.fav)
            self.refresh()

    def play(self, r):
        if not (0 <= r < len(self.items)):
            return
        x = self.lib.audio(self.items[r])
        x = x if x.shape[1] == 2 else np.repeat(x, 2, axis=1)
        self.ctx.audio.play(x.astype(np.float32))

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta con WAV para la biblioteca")
        if not d:
            return
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)

        def done(n):
            self.progress.setVisible(False)
            self.refresh()
            self.ctx.toast(f"{n} muestras nuevas en la biblioteca", "OK")
        self.ctx.run_bg(lambda: self.lib.agregar_carpeta(d), done, lambda: self.progress.setVisible(False))

    def add_pack(self):
        if self.ctx.pack is None:
            return
        pack = self.ctx.pack

        def done(n):
            self.refresh()
            self.ctx.toast(f"{n} muestras de «{pack.title}» guardadas en la biblioteca", "OK")
        self.ctx.run_bg(lambda: self.lib.agregar_pack(pack), done)

    def add_archivos(self, archivos, origen=""):
        """Desde «Importar WAV»."""
        n = self.lib.agregar_archivos(archivos, origen)
        self.refresh()
        return n

    def toggle_fav(self):
        sel = self._sel()
        if not sel:
            return
        nuevo = not all(m.fav for m in sel)
        for m in sel:
            self.lib.editar(m.id, fav=nuevo)
        self.refresh()

    def edit_tags(self):
        sel = self._sel()
        if not sel:
            self.ctx.toast("Selecciona una o más muestras.", "AVISO")
            return
        actual = ", ".join(sorted(set(sel[0].etiquetas)))
        txt, ok = QInputDialog.getText(self, "Etiquetas", "Etiquetas (separadas por comas):", text=actual)
        if not ok:
            return
        tags = [t for t in txt.split(",") if t.strip()]
        for m in sel:
            self.lib.editar(m.id, etiquetas=tags)
        self._fill_tags()
        self.refresh()

    def rename(self):
        sel = self._sel()
        if len(sel) != 1:
            self.ctx.toast("Selecciona una muestra.", "AVISO")
            return
        txt, ok = QInputDialog.getText(self, "Renombrar", "Nombre:", text=sel[0].nombre)
        if ok and txt.strip():
            self.lib.editar(sel[0].id, nombre=txt.strip()[:40])
            self.refresh()

    def remove(self):
        sel = self._sel()
        if not sel:
            return
        if QMessageBox.question(self, "PPF Tester", f"¿Quitar {len(sel)} muestra(s) de la biblioteca?\n\n"
                                "Se borran las copias guardadas en la biblioteca (tus WAV originales no se tocan).") \
                != QMessageBox.StandardButton.Yes:
            return
        n = self.lib.borrar([m.id for m in sel])
        self._fill_tags()
        self.refresh()
        self.ctx.toast(f"{n} muestra(s) quitadas", "INFO")

    def to_import(self, nuevo: bool):
        sel = self._sel()
        if not sel:
            self.ctx.toast("Selecciona las muestras que quieres usar.", "AVISO")
            return
        paths = [self.lib.ruta(m) for m in sel]
        tipos = {self.lib.ruta(m): m.tipo for m in sel}
        nombres = {self.lib.ruta(m): m.nombre for m in sel}
        imp = self.ctx.importer
        if nuevo:
            imp.nuevo_vacio()
        self.ctx.go("import")
        imp.agregar_archivos(paths, tipos=tipos, nombres=nombres)


# ==================================================================== voces y pads
class VoicesPage(Page):
    title = "Voces y pads"
    subtitle = "Voces melódicas (piano, cuerdas, pads) desde tus WAV: detecta la nota y hace loops sin clics."

    def __init__(self, ctx):
        super().__init__(ctx)
        import melodico
        self.Mel = melodico
        self.muestras = []
        root = vbox(self, 0, 12)

        tpl = card()
        tpl_l = hbox(tpl, 16, 10)
        tpl_l.setContentsMargins(16, 12, 16, 12)
        tpl_l.addWidget(caption("Plantilla de voz"))
        self.lbl_tpl = QLabel("")
        self.lbl_tpl.setWordWrap(True)
        tpl_l.addWidget(self.lbl_tpl, 1)
        b_tpl = btn("Elegir plantilla…", "folder")
        b_tpl.setToolTip("Un .ppf con una voz normal (no drum kit) creada en Expansion Manager.\n"
                         "Se usa solo su estructura; su audio se reemplaza por el tuyo.")
        b_tpl.clicked.connect(self.choose_template)
        tpl_l.addWidget(b_tpl)
        b_help = btn("¿Cómo la creo?", "info")
        b_help.clicked.connect(self.help_template)
        tpl_l.addWidget(b_help)
        root.addWidget(tpl)

        top = card()
        tl = hbox(top, 16, 10)
        tl.setContentsMargins(16, 12, 16, 12)
        self.cb_modo = QComboBox()
        self.cb_modo.addItems(["Multisample (piano, guitarra…)", "Sostenido con loop (cuerdas, órgano)", "Pad / ambiente (un WAV)"])
        self.cb_modo.currentIndexChanged.connect(self._modo)
        tl.addWidget(self.cb_modo)
        b_dir = btn("Elegir WAV…", "folder", primary=True)
        b_dir.clicked.connect(self.choose)
        tl.addWidget(b_dir)
        tl.addWidget(caption("Nombre"))
        self.e_name = QLineEdit("Mi Voz")
        self.e_name.setMaxLength(20)
        self.e_name.setFixedWidth(160)
        tl.addWidget(self.e_name)
        self.chk_st = QCheckBox("Estéreo")
        self.chk_st.setToolTip("Usa estéreo si el WAV lo es (ocupa el doble)")
        tl.addWidget(self.chk_st)
        self.lbl_atk = QLabel("Ataque")
        tl.addWidget(self.lbl_atk)
        self.sl_atk = slider(0, 200, 30)
        self.sl_atk.setFixedWidth(90)
        self.sl_atk.setToolTip("Entrada suave del pad (0–2 s)")
        tl.addWidget(self.sl_atk)
        tl.addStretch(1)
        self.b_build = btn("Crear .ppf", "sparkle", primary=True)
        self.b_build.clicked.connect(self.build)
        self.b_build.setEnabled(False)
        tl.addWidget(self.b_build)
        root.addWidget(top)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        pc = card()
        pl = vbox(pc, 12, 6)
        h = QLabel("Cada color es una zona del teclado: la muestra se estira a las teclas vecinas. Clic en una tecla para escucharla.")
        h.setObjectName("Mut")
        pl.addWidget(h)
        self.piano = GlowPiano(height=96)
        self.piano.lo, self.piano.hi = 21, 108
        self.piano.keyClicked.connect(self._piano)
        pl.addWidget(self.piano)
        root.addWidget(pc)

        c = card()
        cl = vbox(c, 12, 6)
        row = hbox(None, 0, 8)
        row.addWidget(caption("Muestras"))
        row.addStretch(1)
        self.lbl_mb = QLabel("")
        self.lbl_mb.setStyleSheet("font-weight:700")
        row.addWidget(self.lbl_mb)
        cl.addLayout(row)
        self.tbl = table(["Usar", "Archivo", "Nota raíz", "Afinación", "Detectada por", "Duración", "Loop", ""],
                         [46, None, 120, 90, 120, 80, 110, 34])
        cl.addWidget(self.tbl, 1)
        root.addWidget(c, 1)
        self._modo()
        self._tpl_status()

    def load(self, pack):
        pass

    # ---------------------------------------------------------------- plantilla
    def _tpl_status(self):
        p = self.Mel.ruta_plantilla()
        if os.path.exists(p):
            try:
                v = load_pack(p).voices[0]
                self.lbl_tpl.setText(f"<span style='color:{C['OK']}'>✔ Lista:</span> «{v.name}». Se usa solo su estructura.")
                return True
            except Exception:  # noqa: BLE001
                pass
        self.lbl_tpl.setText(f"<span style='color:{C['AVISO']}'>Falta una plantilla.</span> Elige una vez un .ppf con una voz normal "
                             "hecha en Expansion Manager (con cualquier WAV). La app la recuerda.")
        return False

    def choose_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Plantilla de voz normal", "", "Yamaha Expansion Manager (*.ppf)")
        if not path:
            return
        try:
            nombre = self.Mel.guardar_plantilla(path)
            self.ctx.toast(f"Plantilla guardada: {nombre}", "OK")
        except Exception as e:  # noqa: BLE001
            self.ctx.toast(f"No sirve como plantilla: {e}", "ERROR", 6000)
        self._tpl_status()

    def help_template(self):
        QMessageBox.information(self, "Plantilla de voz", (
            "Para crear voces melódicas la app necesita una vez una voz normal hecha en Expansion Manager:\n\n"
            "1. Abre Expansion Manager y crea un pack nuevo.\n"
            "2. Crea una voz nueva (Normal, no Drum) y arrastra cualquier WAV.\n"
            "3. Guarda el pack como .ppf (Pack Edit → Save / Export Pack).\n"
            "4. Aquí, pulsa «Elegir plantilla…» y elige ese .ppf.\n\n"
            "La app copia su estructura (la forma en que Yamaha describe una voz) y pone tus muestras."))

    # ---------------------------------------------------------------- muestras
    def _modo(self):
        pad = self.cb_modo.currentIndex() == 2
        self.lbl_atk.setVisible(pad)
        self.sl_atk.setVisible(pad)

    def choose(self):
        if self.cb_modo.currentIndex() == 2:
            f, _ = QFileDialog.getOpenFileName(self, "WAV del pad o ambiente", "", "WAV (*.wav *.wave)")
            entrada = [f] if f else None
        else:
            entrada = QFileDialog.getExistingDirectory(self, "Carpeta con las muestras (una por nota)") or None
        if not entrada:
            return
        self.load_entrada(entrada)

    def load_entrada(self, entrada):
        modo = self.cb_modo.currentIndex()
        base = os.path.basename((entrada[0] if isinstance(entrada, list) else entrada).rstrip("\\/"))
        self.e_name.setText(os.path.splitext(base)[0][:20] or "Mi Voz")
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        atk = self.sl_atk.value() / 100

        def job():
            ms = self.Mel.escanear(entrada, sostenido=modo == 1)
            if modo == 2:
                for m in ms:
                    m.x, m.loop = self.Mel.crear_pad(m.x, ataque_s=atk)
            return ms

        def done(ms):
            self.progress.setVisible(False)
            self.muestras = ms
            if not ms:
                self.ctx.toast("No encontré WAV válidos.", "AVISO")
            self.refresh()
        self.ctx.run_bg(job, done, lambda: self.progress.setVisible(False))

    def refresh(self):
        self.tbl.setRowCount(0)
        for r, m in enumerate(self.muestras):
            self.tbl.insertRow(r)
            chk = QCheckBox()
            chk.setChecked(m.usar)
            chk.toggled.connect(lambda v, m=m: (setattr(m, "usar", v), self._zones()))
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(10, 0, 0, 0)
            lay.addWidget(chk)
            self.tbl.setCellWidget(r, 0, w)
            self.tbl.setItem(r, 1, cell(m.nombre, bold=True))
            cb = QComboBox()
            for n in range(21, 109):
                cb.addItem(note_name(n), n)
            cb.setCurrentIndex(max(0, min(87, m.nota - 21)))
            cb.currentIndexChanged.connect(lambda i, m=m: (setattr(m, "nota", 21 + i), self._zones()))
            self.tbl.setCellWidget(r, 2, cb)
            self.tbl.setItem(r, 3, cell(f"{m.cents:+.0f} cents" if abs(m.cents) >= 1 else "afinada", "mut"))
            self.tbl.setItem(r, 4, cell(m.como, "mut"))
            self.tbl.setItem(r, 5, cell(f"{m.dur:.2f} s", "mut"))
            lp = m.loop
            self.tbl.setItem(r, 6, cell(f"{(lp.fin - lp.inicio) / 44100:.2f} s · {lp.calidad * 100:.0f} %" if lp else "—",
                                        "OK" if lp and lp.calidad > 0.9 else ("AVISO" if lp else "mut")))
            b = QPushButton()
            b.setIcon(icon("play", "gold", 14))
            b.setObjectName("Ghost")
            b.clicked.connect(lambda _=False, m=m: self._play(m.x))
            self.tbl.setCellWidget(r, 7, b)
        self._zones()

    def _zones(self):
        zs = self.Mel.zonas(self.muestras) if self.muestras else []
        raices = sorted({z[4].nota for z in zs})
        st = {}
        for lo, hi, vlo, vhi, m in zs:
            for n in range(lo, hi + 1):
                st.setdefault(n, "Z1" if raices.index(m.nota) % 2 == 0 else "Z2")
        for n in raices:
            st[n] = "OK"
        self.piano.set_keys(st)
        self.piano.labels = {m.nota: "●" for m in self.muestras if m.usar}
        self.piano.update()
        usadas = {id(z[4]): z[4] for z in zs}.values()
        mb = sum(len(m.x) * (2 if self.chk_st.isChecked() and m.x.shape[1] == 2 else 1) * 2 for m in usadas) / 1e6
        self.lbl_mb.setText(f"{mb:.2f} MB" if zs else "")
        self.b_build.setEnabled(bool(zs))

    def _play(self, x, semis=0.0):
        import dsp
        if semis:
            x = dsp.to_rate(x, 44100 * 2 ** (semis / 12), 44100)
        x = x[: 44100 * 6]
        x = x if x.shape[1] == 2 else np.repeat(x, 2, axis=1)
        self.ctx.audio.play(x.astype(np.float32))

    def _piano(self, n, _y):
        zs = self.Mel.zonas(self.muestras) if self.muestras else []
        for lo, hi, vlo, vhi, m in zs:
            if lo <= n <= hi and vhi == 127:
                self.piano.flash(n)
                self._play(m.x, n - m.nota)
                return

    def build(self):
        if not self._tpl_status():
            self.help_template()
            return
        nombre = self.e_name.text().strip() or "Mi Voz"
        out, _ = QFileDialog.getSaveFileName(self, "Guardar voz", f"{nombre}.ppf", "Yamaha Expansion Manager (*.ppf)")
        if not out:
            return
        op = self.Mel.OpcionesVoz(nombre=nombre, estereo=self.chk_st.isChecked(),
                                  sostenido=self.cb_modo.currentIndex() in (1, 2))
        muestras = list(self.muestras)
        tpl = self.Mel.ruta_plantilla()
        self.b_build.setEnabled(False)

        def done(pack):
            self.b_build.setEnabled(True)
            if pack.errors:
                self.ctx.toast("El archivo creado no pasó la verificación: " + "; ".join(pack.errors), "ERROR", 8000)
                return
            self.ctx.toast(f"Voz creada: {os.path.basename(out)}", "OK", 5000)
            self.ctx.open_file(out)
        self.ctx.run_bg(lambda: self.Mel.construir(load_pack(tpl), muestras, op, out), done, lambda: self.b_build.setEnabled(True))


# ==================================================================== set del teclado
class SetPage(Page):
    title = "Set del teclado"
    subtitle = "Junta los packs que quieres instalar y mira si caben en la memoria de tu PSR. Compara dos versiones de un kit."

    def __init__(self, ctx):
        super().__init__(ctx)
        import conjunto
        self.K = conjunto
        self.packs = []
        self.a = self.b = None
        root = vbox(self, 0, 12)
        body = hbox(None, 0, 12)
        root.addLayout(body, 1)

        c = card()
        cl = vbox(c, 14, 8)
        row = hbox(None, 0, 8)
        row.addWidget(caption("Packs del set"))
        row.addStretch(1)
        self.cb_model = QComboBox()
        self.cb_model.addItems(list(modelos.MODELOS))
        self.cb_model.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.cb_model)
        b_add = btn("Añadir .ppf…", "folder", primary=True)
        b_add.clicked.connect(self.add)
        row.addWidget(b_add)
        b_cur = btn("Añadir el abierto", "export")
        b_cur.clicked.connect(lambda: self.ctx.pack and self._add_paths([self.ctx.pack.path]))
        row.addWidget(b_cur)
        b_del = btn("Quitar", "stop")
        b_del.clicked.connect(self.remove)
        row.addWidget(b_del)
        cl.addLayout(row)
        self.tbl = table(["Pack", "Voces", "Tipo", "Audio", "% memoria"], [None, 200, 110, 90, 100])
        cl.addWidget(self.tbl, 1)
        self.bar = MemoryBars()
        cl.addWidget(self.bar)
        self.lbl = QLabel("Añade los .ppf que quieres tener instalados a la vez.")
        self.lbl.setWordWrap(True)
        cl.addWidget(self.lbl)
        body.addWidget(c, 3)

        c2 = card()
        l2 = vbox(c2, 14, 8)
        l2.addWidget(caption("Comparar dos versiones de un kit"))
        ra = hbox(None, 0, 8)
        self.b_a = btn("A: elegir…", "folder")
        self.b_a.clicked.connect(lambda: self.pick("a"))
        self.b_b = btn("B: elegir…", "folder")
        self.b_b.clicked.connect(lambda: self.pick("b"))
        ra.addWidget(self.b_a, 1)
        ra.addWidget(self.b_b, 1)
        l2.addLayout(ra)
        rb = hbox(None, 0, 8)
        self.cb_nota = QComboBox()
        self.cb_nota.setMinimumWidth(140)
        rb.addWidget(self.cb_nota, 1)
        for lab, k in (("A", "a"), ("B", "b")):
            b = btn(f"Escuchar {lab}", "play")
            b.clicked.connect(lambda _=False, k=k: self.play(k))
            rb.addWidget(b)
        l2.addLayout(rb)
        self.rep = text_view(120)
        self.rep.setHtml(f"<p style='color:{C['mut']}'>Elige la versión anterior (A) y la nueva (B): te digo qué cambió en cada tecla "
                         "y puedes escucharlas una tras otra.</p>")
        l2.addWidget(self.rep, 1)
        body.addWidget(c2, 2)

    def load(self, pack):
        pass

    def add(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Packs del set", "", "Yamaha Expansion Manager (*.ppf)")
        self._add_paths(paths)

    def _add_paths(self, paths):
        paths = [p for p in paths if p and p not in {x.path for x in self.packs}]
        if not paths:
            return
        self.ctx.run_bg(lambda: [self.K.info(p) for p in paths], lambda infos: (self.packs.extend(infos), self.refresh()))

    def remove(self):
        for r in reversed(_sel_rows(self.tbl)):
            if r < len(self.packs):
                del self.packs[r]
        self.refresh()

    def refresh(self, *_):
        modelo = self.cb_model.currentText()
        m = modelos.MODELOS[modelo]
        self.tbl.setRowCount(0)
        for p in self.packs:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, cell(p.titulo, "ERROR" if p.error else None, bold=True))
            self.tbl.setItem(r, 1, cell(", ".join(p.voces) or p.error, "mut"))
            self.tbl.setItem(r, 2, cell(", ".join(sorted({"Batería" if t == "DRUM_KIT" else "Voz" for t in p.tipos})), "gold"))
            self.tbl.setItem(r, 3, cell(f"{p.mb:.2f} MB", None, Qt.AlignmentFlag.AlignRight))
            self.tbl.setItem(r, 4, cell(f"{p.mb / m.memoria_mb * 100:.1f} %", "mut", Qt.AlignmentFlag.AlignRight))
        if not self.packs:
            self.bar.set_rows([])
            self.lbl.setText("Añade los .ppf que quieres tener instalados a la vez.")
            return
        st = self.K.estado_set(self.packs, modelo)
        self.bar.set_rows([(n, st.total_mb, modelos.MODELOS[n].memoria_mb, e) for n, e, _ in modelos.compatibilidad(st.total_mb)])
        txt = f"<b style='color:{C[st.estado]}'>{st.total_mb:.1f} MB de {st.memoria_mb:.0f} MB</b> en el {st.modelo}. {st.texto}"
        fuera = self.K.que_quitar(self.packs, modelo)
        if fuera:
            txt += "<br>Para que entre, quita: " + ", ".join(f"«{p.titulo}» ({p.mb:.1f} MB)" for p in fuera) + "."
        self.lbl.setText(txt)

    def pick(self, which):
        path, _ = QFileDialog.getOpenFileName(self, f"Versión {which.upper()}", "", "Yamaha Expansion Manager (*.ppf)")
        if not path:
            return

        def done(pack):
            setattr(self, which, pack)
            (self.b_a if which == "a" else self.b_b).setText(f"{which.upper()}: {os.path.basename(path)[:28]}")
            self.compare()
        self.ctx.run_bg(lambda: load_pack(path), done)

    def compare(self):
        if not (self.a and self.b):
            return
        difs, tot = self.K.comparar(self.a, self.b)
        self.rep.setHtml(self.K.informe_html(difs, tot, os.path.basename(self.a.path), os.path.basename(self.b.path), C))
        self.cb_nota.clear()
        for d in difs:
            self.cb_nota.addItem(f"{note_name(d.nota)} · {d.estado}", d.nota)
        i = next((k for k, d in enumerate(difs) if d.estado == "cambiada"), 0)
        self.cb_nota.setCurrentIndex(i)
        import motor
        self.eng = {k: motor.Engine(p, p.voices[0]) for k, p in (("a", self.a), ("b", self.b)) if p.voices}

    def play(self, which):
        n = self.cb_nota.currentData()
        e = getattr(self, "eng", {}).get(which)
        if n is None or e is None:
            return
        buf, g = e.render(int(n), 110)
        self.ctx.audio.play(buf, g, int(n))


# ==================================================================== en vivo
class Pad(QWidget):
    hit = Signal(int, float)

    def __init__(self, nota, nombre, tecla=""):
        super().__init__()
        self.nota, self.nombre, self.tecla = nota, nombre, tecla
        self.glow = 0.0
        self.setMinimumSize(120, 92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def flash(self, v=1.0):
        self.glow = max(self.glow, v)
        self.update()

    def mousePressEvent(self, e):
        frac = e.position().y() / max(1, self.height())
        self.hit.emit(self.nota, float(np.clip(frac, 0, 1)))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        p.setPen(QPen(q("line2"), 1))
        p.setBrush(q("card2"))
        p.drawRoundedRect(r, 14, 14)
        if self.glow > 0.01:
            c = q("gold", int(40 + 170 * self.glow))
            p.setBrush(c)
            p.setPen(QPen(q("gold", int(255 * self.glow)), 2))
            p.drawRoundedRect(r, 14, 14)
        p.setPen(q("fg"))
        p.setFont(font(12, 600))
        p.drawText(r.adjusted(14, 10, -14, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.nombre)
        p.setPen(q("mut"))
        p.setFont(font(9))
        p.drawText(r.adjusted(14, 10, -14, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, note_name(self.nota))
        if self.tecla:
            p.setPen(q("gold"))
            p.setFont(font(10, 700))
            p.drawText(r.adjusted(14, 10, -14, -10), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, self.tecla.upper())
        p.end()


class LivePage(Page):
    title = "En vivo"
    subtitle = "Pads grandes para tocar el kit en el ensayo: ratón, teclado del PC o MIDI. F11 = pantalla completa."

    def __init__(self, ctx):
        super().__init__(ctx)
        import grooves as G
        self.G = G
        self.engine = None
        self.pads: dict[int, Pad] = {}
        self.keymap: dict[str, int] = {}
        self.player = None
        self.midi_in = None
        root = vbox(self, 0, 12)
        bar = card()
        bv = QVBoxLayout(bar)
        bv.setContentsMargins(16, 10, 16, 10)
        bv.setSpacing(8)
        bl = hbox(None, 0, 10)
        bl2 = hbox(None, 0, 10)
        bv.addLayout(bl)
        bv.addLayout(bl2)
        self.groove = QComboBox()
        self.groove.addItems(list(G.PATRONES))
        bl.addWidget(self.groove, 1)
        bl.addWidget(QLabel("BPM"))
        self.bpm = QSpinBox()
        self.bpm.setRange(40, 220)
        self.bpm.setValue(72)
        bl.addWidget(self.bpm)
        self.b_groove = btn("Ritmo", "play", primary=True)
        self.b_groove.clicked.connect(self.toggle_groove)
        bl.addWidget(self.b_groove)
        bl.addSpacing(10)
        bl.addWidget(QLabel("Volumen"))
        self.vol = slider(-24, 6, 0)
        self.vol.setFixedWidth(110)
        self.vol.valueChanged.connect(self._vol)
        bl.addWidget(self.vol)
        self.chk_h = QCheckBox("Variación humana")
        self.chk_h.setChecked(True)
        self.chk_h.toggled.connect(lambda v: self.engine and setattr(self.engine.settings, "humanizar", v))
        bl.addWidget(self.chk_h)
        bl2.addWidget(caption("Entrada MIDI"))
        self.cb_midi = QComboBox()
        self.cb_midi.setMinimumWidth(200)
        bl2.addWidget(self.cb_midi, 1)
        self.b_midi = btn("Tocar desde MIDI", "piano")
        self.b_midi.setCheckable(True)
        self.b_midi.toggled.connect(self.toggle_midi)
        bl2.addWidget(self.b_midi)
        h = QLabel("Abajo en el pad = más fuerte · Mayús = acento")
        h.setObjectName("Mut")
        bl2.addWidget(h, 2)
        b_fs = btn("Pantalla completa", "export", tip="F11 · Esc para salir")
        b_fs.clicked.connect(self.ctx.toggle_fullscreen)
        bl2.addWidget(b_fs)
        b_demo = btn("Demo MP3", "share")
        b_demo.setToolTip("Graba una demo del kit (cada pieza + ritmos) para compartir")
        b_demo.clicked.connect(lambda: export_demo(self.ctx))
        bl2.addWidget(b_demo)
        root.addWidget(bar)
        self.grid_w = QWidget()
        self.grid = QGridLayout(self.grid_w)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        root.addWidget(self.grid_w, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._decay)
        self.timer.start(30)
        QTimer.singleShot(600, self._refresh_midi)

    def load(self, pack):
        import importar_wav as I
        import motor
        from qt_pages2 import KEYS
        self.stop()
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.pads.clear()
        self.engine = motor.Engine(pack, pack.voices[0]) if pack.voices else None
        if not self.engine:
            return
        self.engine.settings.humanizar = self.chk_h.isChecked()
        self._vol(self.vol.value())
        notas = sorted({lo for _, _, lo, hi, _, _ in pack.voices[0].zones()})[:32]
        nombres = {}
        for el, kb, lo, hi, vlo, vhi in pack.voices[0].zones():
            w = pack.waves.get(kb.samples[0].wave_uid)
            if w is not None and vhi == 127:
                nombres[lo] = w.name
        self.keymap = dict(zip(KEYS, notas))
        inv = {n: k for k, n in self.keymap.items()}
        cols = 8 if len(notas) > 24 else 6 if len(notas) > 12 else 4
        for i, n in enumerate(notas):
            titulo = I.GM.get(n) or nombres.get(n, note_name(n))
            pad = Pad(n, titulo[:18], inv.get(n, ""))
            pad.setToolTip(nombres.get(n, ""))
            pad.hit.connect(self._pad_hit)
            self.grid.addWidget(pad, i // cols, i % cols)
            self.pads[n] = pad

    def _vol(self, v):
        if self.engine:
            self.engine.settings.master_db = float(v)
            self.engine.invalidate()

    def _pad_hit(self, n, frac):
        self.hit(n, int(np.clip(35 + frac * 92, 1, 127)))

    def hit(self, n, vel):
        if not self.engine:
            return
        buf, g = self.engine.render_play(n, vel)
        self.ctx.audio.play(buf, g, n)
        if n in self.pads:
            self.pads[n].flash(0.4 + 0.6 * vel / 127)

    def key_press(self, e) -> bool:
        ch = (e.text() or "").lower()
        if ch not in self.keymap or e.isAutoRepeat():
            return False
        self.hit(self.keymap[ch], 127 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 100)
        return True

    def _decay(self):
        for p in self.pads.values():
            if p.glow > 0.01:
                p.glow *= 0.86
                p.update()

    def toggle_groove(self):
        if self.player is not None:
            self.stop()
            return
        if not self.engine:
            return
        audio = self.ctx.audio
        audio.mixer()
        bridge = self.ctx.bridge

        def tocar(n, v):
            buf, g = self.engine.render_play(n, v)
            audio.play(buf, g, n)
            bridge.sig.emit(lambda _: n in self.pads and self.pads[n].flash(0.5 + 0.5 * v / 127), None)
        self.player = self.G.Reproductor(tocar, set(self.pads))
        self.player.start(self.groove.currentText(), float(self.bpm.value()))
        from idioma import tr
        self.b_groove.setText("  " + tr("Parar"))
        self.b_groove.setIcon(icon("stop", "bg", 16))

    def stop(self):
        if self.player is not None:
            self.player.stop()
            self.player = None
        from idioma import tr
        self.b_groove.setText("  " + tr("Ritmo"))
        self.b_groove.setIcon(icon("play", "bg", 16))

    def _refresh_midi(self):
        try:
            import midi_test
            ins = midi_test.midi_inputs()
        except Exception:  # noqa: BLE001
            ins = []
        self.cb_midi.clear()
        self.cb_midi.addItems([f"[{i}] {n}" for i, n in enumerate(ins)] or ["(sin entradas MIDI)"])
        self.b_midi.setEnabled(bool(ins))

    def toggle_midi(self, on):
        import midi_test
        if self.midi_in is not None:
            self.midi_in.close()
            self.midi_in = None
        if not on:
            return
        s = self.cb_midi.currentText()
        if not s.startswith("["):
            self.b_midi.setChecked(False)
            return
        bridge = self.ctx.bridge
        try:
            self.midi_in = midi_test.MidiIn(int(s.split("]")[0].strip("[")), lambda n, v: bridge.sig.emit(lambda _: self.hit(n, v), None))
            self.ctx.toast("Toca tu teclado MIDI", "OK")
        except Exception as e:  # noqa: BLE001
            self.b_midi.setChecked(False)
            self.ctx.toast(str(e), "ERROR")

    def hideEvent(self, e):
        self.stop()
        super().hideEvent(e)


# ==================================================================== demo MP3
def export_demo(ctx):
    import demo
    import motor
    pack = ctx.pack
    if pack is None or not pack.voices:
        return
    dlg = QDialog(ctx)
    dlg.setWindowTitle("Demo del kit")
    l = vbox(dlg, 22, 12)
    l.addWidget(caption("Qué incluir"))
    chk_rec = QCheckBox("Recorrido: cada pieza suave y fuerte")
    chk_rec.setChecked(pack.voices[0].voice_type == "DRUM_KIT")
    l.addWidget(chk_rec)
    cbs = []
    for i, nombre in enumerate(("Worship 4/4 (toms)", "Balada 4/4", "Worship 6/8", "Pop 4/4")):
        cb = QCheckBox(f"Ritmo: {nombre}")
        cb.setChecked(i < 2 and pack.voices[0].voice_type == "DRUM_KIT")
        cb.setProperty("ritmo", nombre)
        cbs.append(cb)
        l.addWidget(cb)
    rowb = hbox(None, 0, 8)
    rowb.addWidget(QLabel("BPM"))
    sp = QSpinBox()
    sp.setRange(50, 180)
    sp.setValue(76)
    rowb.addWidget(sp)
    rowb.addWidget(QLabel("Compases por ritmo"))
    spc = QSpinBox()
    spc.setRange(1, 16)
    spc.setValue(4)
    rowb.addWidget(spc)
    rowb.addStretch(1)
    l.addLayout(rowb)
    fmt = QComboBox()
    fmt.addItems(["MP3 (para WhatsApp y redes)", "WAV (calidad completa)"])
    if not demo.mp3_disponible():
        fmt.setCurrentIndex(1)
        fmt.model().item(0).setEnabled(False)
    l.addWidget(fmt)
    n = QLabel("La demo usa la simulación del PSR (no es una grabación del teclado).")
    n.setObjectName("Mut")
    n.setWordWrap(True)
    l.addWidget(n)
    rb = hbox(None, 0, 8)
    rb.addStretch(1)
    b_no = btn("Cancelar")
    b_no.clicked.connect(dlg.reject)
    b_ok = btn("Crear demo", "share", primary=True)
    b_ok.clicked.connect(dlg.accept)
    rb.addWidget(b_no)
    rb.addWidget(b_ok)
    l.addLayout(rb)
    from idioma import traducir_arbol
    traducir_arbol(dlg)
    dark_titlebar(dlg)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    ritmos = [cb.property("ritmo") for cb in cbs if cb.isChecked()]
    if not ritmos and not chk_rec.isChecked():
        ctx.toast("Elige al menos el recorrido o un ritmo.", "AVISO")
        return
    ext = ".mp3" if fmt.currentIndex() == 0 else ".wav"
    base = os.path.splitext(pack.path)[0] + "_demo" + ext
    out, _ = QFileDialog.getSaveFileName(ctx, "Guardar demo", base, "MP3 (*.mp3)" if ext == ".mp3" else "WAV (*.wav)")
    if not out:
        return
    bpm, comp, rec = float(sp.value()), spc.value(), chk_rec.isChecked()
    ctx.toast("Creando la demo…", "INFO", 6000)

    def job():
        e = motor.Engine(pack, pack.voices[0])
        x = demo.demo_kit(e, ritmos, bpm, comp, rec)
        return demo.guardar(out, x), len(x) / motor.SR

    def done(res):
        path, dur = res
        ctx.toast(f"Demo lista: {os.path.basename(path)} ({dur:.0f} s)", "OK", 5000)
        from qt_main import abrir_carpeta
        abrir_carpeta(os.path.dirname(path))
    ctx.run_bg(job, done)


# ==================================================================== asistente PSR
class PsrWizard(QDialog):
    """Asistente paso a paso para probar el kit en el PSR real."""

    PASOS = ["Conectar", "MIDI", "Audio", "Prueba", "Listo"]

    def __init__(self, ctx):
        super().__init__(ctx)
        self.ctx = ctx
        self.kb = ctx.keyboard
        self.setWindowTitle("Asistente de prueba en el PSR")
        self.resize(720, 520)
        self.res = {}
        root = vbox(self, 22, 14)
        self.steps = QLabel()
        root.addWidget(self.steps)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        for f in (self._p_conectar, self._p_midi, self._p_audio, self._p_prueba, self._p_listo):
            w = QWidget()
            f(vbox(w, 0, 10))
            self.stack.addWidget(w)
        nav = hbox(None, 0, 8)
        self.b_back = btn("Atrás")
        self.b_back.clicked.connect(lambda: self._go(self.stack.currentIndex() - 1))
        nav.addWidget(self.b_back)
        nav.addStretch(1)
        self.b_next = btn("Siguiente", "play", primary=True)
        self.b_next.clicked.connect(self._next)
        nav.addWidget(self.b_next)
        root.addLayout(nav)
        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self._audio_tick)
        from idioma import traducir_arbol
        traducir_arbol(self)
        dark_titlebar(self)
        self._go(0)

    # ---------------------------------------------------------------- páginas
    @staticmethod
    def _txt(l, html):
        t = QLabel(html)
        t.setWordWrap(True)
        t.setTextFormat(Qt.TextFormat.RichText)
        l.addWidget(t)
        return t

    def _p_conectar(self, l):
        self._txt(l, "<h3>1 · Conecta el teclado</h3>"
                     "<ol><li>Conecta el PSR al PC con un cable USB al puerto <b>USB TO HOST</b>.</li>"
                     "<li>Instala el pack en el PSR y elige la voz en <b>RIGHT 1</b>.</li>"
                     "<li>Para grabar lo que suena: conecta la salida <b>PHONES</b> del PSR a la entrada de tu interfaz de audio "
                     "(o a la entrada de línea del PC).</li></ol>")
        g = QGridLayout()
        g.addWidget(caption("Salida MIDI (el PSR)"), 0, 0)
        self.cb_midi = QComboBox()
        g.addWidget(self.cb_midi, 1, 0)
        g.addWidget(caption("Entrada de audio"), 0, 1)
        self.cb_in = QComboBox()
        g.addWidget(self.cb_in, 1, 1)
        g.addWidget(caption("Canal"), 0, 2)
        self.sp_ch = QSpinBox()
        self.sp_ch.setRange(1, 16)
        self.sp_ch.setValue(self.kb.sp_ch.value())
        g.addWidget(self.sp_ch, 1, 2)
        b = btn("Buscar dispositivos", "refresh")
        b.clicked.connect(self._fill)
        g.addWidget(b, 1, 3)
        l.addLayout(g)
        l.addStretch(1)
        self._fill()

    def _fill(self):
        self.kb.refresh()
        for src, dst in ((self.kb.cb_midi, self.cb_midi), (self.kb.cb_in, self.cb_in)):
            dst.clear()
            dst.addItems([src.itemText(i) for i in range(src.count())])
            dst.setCurrentIndex(src.currentIndex())

    def _p_midi(self, l):
        self._txt(l, "<h3>2 · Prueba de MIDI</h3><p>Pulsa el botón: el PSR debería tocar un bombo y una caja.</p>")
        b = btn("Tocar nota de prueba", "play", primary=True)
        b.clicked.connect(self._midi_test)
        l.addWidget(b)
        row = hbox(None, 0, 8)
        self.b_si = btn("Sí, sonó", "check")
        self.b_si.clicked.connect(lambda: self._midi_ok(True))
        self.b_nos = btn("No sonó", "stop")
        self.b_nos.clicked.connect(lambda: self._midi_ok(False))
        row.addWidget(self.b_si)
        row.addWidget(self.b_nos)
        row.addStretch(1)
        l.addLayout(row)
        self.midi_lbl = self._txt(l, "")
        l.addStretch(1)

    def _midi_test(self):
        try:
            port = int(self.cb_midi.currentText().split("]")[0].strip("["))
            midi = self.ctx.audio.midi(port)
            ch = self.sp_ch.value()
            midi.note(ch, 36, 110)
            QTimer.singleShot(400, lambda: (midi.off(ch, 36), midi.note(ch, 38, 110)))
            QTimer.singleShot(900, lambda: midi.off(ch, 38))
        except Exception as e:  # noqa: BLE001
            self.midi_lbl.setText(f"<span style='color:{C['ERROR']}'>No se pudo enviar MIDI: {e}</span>")

    def _midi_ok(self, ok):
        self.res["midi"] = ok
        self.midi_lbl.setText(f"<span style='color:{C['OK']}'>✔ MIDI correcto.</span>" if ok else
                              f"<span style='color:{C['AVISO']}'>Revisa:</span><ul><li>Que el cable esté en <b>USB TO HOST</b> (no en USB TO DEVICE).</li>"
                              "<li>Que elegiste el puerto del PSR (suele llamarse «Digital Keyboard» o «Yamaha»).</li>"
                              "<li>El canal: RIGHT 1 recibe por el canal 1 de fábrica (Menu → MIDI en el PSR).</li>"
                              "<li>Que la voz del pack esté elegida en RIGHT 1 y el volumen del PSR arriba.</li></ul>")

    def _p_audio(self, l):
        self._txt(l, "<h3>3 · Prueba de audio</h3><p>Toca unas notas en el PSR (o pulsa el botón). La barra debe moverse. "
                     "Si se pone roja, baja la ganancia de tu interfaz.</p>")
        self.meter = LevelMeter()
        self.meter.level_fn = lambda: self.ctx.audio.input_level()
        self.meter.setFixedHeight(22)
        l.addWidget(self.meter)
        b = btn("Tocar notas de prueba", "play")
        b.clicked.connect(self._midi_test)
        l.addWidget(b)
        self.audio_lbl = self._txt(l, "")
        self._peak = 0.0
        l.addStretch(1)

    def _audio_tick(self):
        lv = self.ctx.audio.input_level()
        self._peak = max(self._peak, lv)
        if self._peak > 0.98:
            self.audio_lbl.setText(f"<span style='color:{C['AVISO']}'>Satura: baja la ganancia de la entrada.</span>")
            self.res["audio"] = True
        elif self._peak > 0.03:
            self.audio_lbl.setText(f"<span style='color:{C['OK']}'>✔ Llega sonido del PSR ({20 * np.log10(self._peak):.0f} dBFS).</span>")
            self.res["audio"] = True
        else:
            self.audio_lbl.setText(f"<span style='color:{C['mut']}'>Esperando sonido…</span>")

    def _p_prueba(self, l):
        self._txt(l, "<h3>4 · Prueba completa</h3><p>La app toca cada tecla del kit a varias velocidades, graba lo que suena "
                     "y revisa que todas suenen, sin retrasos y con la dinámica correcta.</p>")
        self.b_run = btn("Iniciar la prueba", "play", primary=True)
        self.b_run.clicked.connect(self._run)
        l.addWidget(self.b_run)
        self.chk_cal = QCheckBox("Calibrar también la simulación con mi PSR")
        self.chk_cal.setChecked(True)
        l.addWidget(self.chk_cal)
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(6)
        self.pbar.setVisible(False)
        l.addWidget(self.pbar)
        self.run_lbl = text_view(120)
        l.addWidget(self.run_lbl, 1)

    def _run(self):
        import midi_test as M
        if not self.ctx.kits:
            return
        try:
            port = int(self.cb_midi.currentText().split("]")[0].strip("["))
        except ValueError:
            self.run_lbl.setHtml("Elige la salida MIDI en el paso 1.")
            return
        dev = int(self.cb_in.currentText().split("]")[0].strip("[")) if self.cb_in.currentText().startswith("[") else None
        ch = self.sp_ch.value()
        kit = self.ctx.kits[0]
        pack = self.ctx.pack
        wbn = {w.name: w for w in pack.waves.values()}
        self.b_run.setEnabled(False)
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(True)
        cal = self.chk_cal.isChecked() and dev is not None
        self.meter_timer.stop()

        def job():
            self.ctx.audio.close_live()
            hits, audio, sr = M.run_test(kit, wbn, port, ch, [40, 80, 127], dev, dev is not None)
            probs = M.evaluate(hits) if dev is not None else []
            c = None
            if cal:
                import calibracion
                import motor
                c = calibracion.calibrar(motor.Engine(pack, pack.voices[0]), kit, port, ch, dev)
            return hits, probs, c

        def done(res):
            import json
            hits, probs, c = res
            self.pbar.setVisible(False)
            self.b_run.setEnabled(True)
            self.res.update(hits=hits, probs=probs)
            mudos = [h for h in hits if h.latency_ms is None]
            html = (f"<p style='color:{C['OK']}'>✔ {len(hits) - len(mudos)} de {len(hits)} golpes sonaron.</p>" if hits else "")
            html += problems_html(probs, "Todo sonó bien y la dinámica es correcta.")
            if c:
                self.ctx.settings.setValue("calibracion", json.dumps({"eq": c["eq"], "vel": c["vel"]}))
                html += f"<p style='color:{C['OK']}'>✔ Simulación calibrada con tu PSR.</p>"
                self.res["cal"] = True
            self.run_lbl.setHtml(html)

        def err():
            self.pbar.setVisible(False)
            self.b_run.setEnabled(True)
        self.ctx.run_bg(job, done, err)

    def _p_listo(self, l):
        self.fin = self._txt(l, "")
        self.b_rep = btn("Guardar informe HTML", "doc", primary=True)
        self.b_rep.clicked.connect(self._report)
        l.addWidget(self.b_rep)
        l.addStretch(1)

    def _report(self):
        import reporte as R
        pack = self.ctx.pack
        out, _ = QFileDialog.getSaveFileName(self, "Informe", os.path.splitext(pack.path)[0] + "_prueba_psr.html", "HTML (*.html)")
        if not out:
            return
        R.write_report(out, pack, self.ctx.kits, self.ctx.waves, midi_problems=self.res.get("probs", []),
                       midi_hits=self.res.get("hits"), extra_title="(prueba en el PSR)")
        from qt_main import abrir_carpeta
        abrir_carpeta(out)

    # ---------------------------------------------------------------- navegación
    def _go(self, i):
        i = max(0, min(len(self.PASOS) - 1, i))
        self.stack.setCurrentIndex(i)
        self.steps.setText("  ›  ".join(f"<b style='color:{C['gold']}'>{p}</b>" if k == i else
                                        f"<span style='color:{C['mut']}'>{p}</span>" for k, p in enumerate(self.PASOS)))
        self.b_back.setEnabled(i > 0)
        self.b_next.setText("Cerrar" if i == len(self.PASOS) - 1 else "Siguiente")
        if i == 2:
            dev = self.cb_in.currentText()
            if dev.startswith("["):
                try:
                    self.ctx.audio.live(int(dev.split("]")[0].strip("[")))
                    self._peak = 0.0
                    self.meter_timer.start(100)
                except Exception as e:  # noqa: BLE001
                    self.audio_lbl.setText(f"<span style='color:{C['ERROR']}'>No se pudo abrir la entrada: {e}</span>")
            else:
                self.audio_lbl.setText(f"<span style='color:{C['mut']}'>Sin entrada de audio: puedes seguir; la prueba no grabará.</span>")
        else:
            self.meter_timer.stop()
        if i == len(self.PASOS) - 1:
            ok = lambda k: f"<span style='color:{C['OK']}'>✔</span>" if self.res.get(k) else f"<span style='color:{C['mut']}'>—</span>"  # noqa: E731
            probs = self.res.get("probs", [])
            self.fin.setText("<h3>5 · Resumen</h3>"
                             f"<p>{ok('midi')} MIDI &nbsp; {ok('audio')} Audio &nbsp; {ok('hits')} Prueba completa &nbsp; {ok('cal')} Calibración</p>"
                             + (problems_html(probs, "Sin problemas.") if self.res.get("hits") else
                                f"<p style='color:{C['mut']}'>La prueba completa no se hizo.</p>"))

    def _next(self):
        i = self.stack.currentIndex()
        if i == 0:
            self.kb.cb_midi.setCurrentIndex(self.cb_midi.currentIndex())
            self.kb.cb_in.setCurrentIndex(self.cb_in.currentIndex())
            self.kb.sp_ch.setValue(self.sp_ch.value())
        if i == len(self.PASOS) - 1:
            self.accept()
            return
        self._go(i + 1)

    def done(self, r):
        self.meter_timer.stop()
        super().done(r)
