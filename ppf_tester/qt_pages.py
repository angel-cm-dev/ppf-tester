"""Páginas de la aplicación Qt: Muestras, Revisión y Prueba en el teclado."""
from __future__ import annotations

import copy
import os

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QVBoxLayout, QWidget)

import analisis as A
from ppf_format import note_name
from qt_fx import GlowPiano, LevelMeter, WaveView, caption, card, icon
from qt_theme import C, q

LV_COLOR = {"ERROR": C["ERROR"], "AVISO": C["AVISO"], "INFO": C["INFO"], "OK": C["OK"]}


def problems_html(probs, empty="Sin problemas detectados.") -> str:
    if not probs:
        return f"<p style='color:{C['OK']}'>✔&nbsp; {empty}</p>"
    rows = []
    for p in probs:
        col = LV_COLOR.get(p.level, C["fg"])
        fix = f" <span style='color:{C['mut']}'>· corregible</span>" if getattr(p, "fixable", False) else ""
        rows.append(f"<tr><td style='padding:5px 10px 5px 0; color:{col}; font-weight:700; white-space:nowrap'>{p.level}</td>"
                    f"<td style='padding:5px 0'>{p.text}{fix}</td></tr>")
    return "<table cellspacing=0>" + "".join(rows) + "</table>"


def text_view(min_h=80) -> QTextBrowser:
    t = QTextBrowser()
    t.setOpenExternalLinks(True)
    t.setMinimumHeight(min_h)
    t.setStyleSheet("QTextBrowser { padding: 4px; }")
    return t


def table(headers, widths=None) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.verticalHeader().setDefaultSectionSize(36)
    hh = t.horizontalHeader()
    hh.setHighlightSections(False)
    for i in range(len(headers)):
        if widths and i < len(widths) and widths[i]:
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            t.setColumnWidth(i, widths[i])
        else:
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
    return t


def cell(text, color=None, align=Qt.AlignmentFlag.AlignLeft, bold=False) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    if color:
        it.setForeground(q(color) if color in C else q(color))
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


def vbox(parent=None, m=18, s=12):
    l = QVBoxLayout(parent)
    l.setContentsMargins(m, m, m, m)
    l.setSpacing(s)
    return l


def hbox(parent=None, m=0, s=10):
    l = QHBoxLayout(parent)
    l.setContentsMargins(m, m, m, m)
    l.setSpacing(s)
    return l


def btn(text, ic=None, primary=False, tip=None) -> QPushButton:
    b = QPushButton(("  " + text) if ic and text else text)
    if ic:
        b.setIcon(icon(ic, "#1a1007" if primary else "fg", 16))
    if primary:
        b.setObjectName("Primary")
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class Page(QWidget):
    title = ""
    subtitle = ""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

    def load(self, pack):
        pass


# =================================================================== muestras
class SamplesPage(Page):
    title = "Muestras"
    subtitle = "Cada tecla del kit, su forma de onda, espectro, medidas y parámetros."

    def __init__(self, ctx):
        super().__init__(ctx)
        root = vbox(self, 0, 14)
        pc = card()
        pl = vbox(pc, 14, 8)
        from qt_import import DropPiano
        self.piano = DropPiano(height=80)
        self.piano.keyClicked.connect(lambda n, y: self.select_note(n, play=True))
        self.piano.dropped.connect(self._dropped)
        self.piano.setToolTip("Arrastra una fila de la tabla hasta otra tecla para mover (o intercambiar) su sonido")
        pl.addWidget(self.piano)
        root.addWidget(pc)

        body = hbox(None, 0, 14)
        root.addLayout(body, 1)
        left = card()
        ll = vbox(left, 12, 6)
        ll.addWidget(caption("Teclas del kit"))
        self.tbl = table(["Tecla", "Muestra", "Pico", "Estado"], [64, None, 70, 72])
        self.tbl.setDragEnabled(True)
        self.tbl.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.tbl.startDrag = self._start_drag
        self.tbl.itemSelectionChanged.connect(self._on_select)
        self.tbl.cellDoubleClicked.connect(lambda r, c: self.play())
        ll.addWidget(self.tbl)
        left.setFixedWidth(390)
        body.addWidget(left)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget#RightCol { background: transparent; }")
        rc = QWidget()
        rc.setObjectName("RightCol")
        right = QVBoxLayout(rc)
        right.setContentsMargins(0, 0, 4, 0)
        right.setSpacing(14)
        scroll.setWidget(rc)
        scroll.viewport().setAutoFillBackground(False)
        rc.setAutoFillBackground(False)
        body.addWidget(scroll, 1)
        wc = card()
        wl = vbox(wc, 12, 10)
        self.wave = WaveView(height=150)
        wl.addWidget(self.wave)
        bar = hbox(None, 0, 8)
        self.b_play = btn("Escuchar", "play", primary=True)
        self.b_play.clicked.connect(self.play)
        b_stop = btn("Parar", "stop")
        b_stop.clicked.connect(lambda: self.ctx.audio.stop())
        self.b_spec = btn("Espectro", "wave")
        self.b_spec.clicked.connect(lambda: self.b_spec.setText("  Forma de onda" if self.wave.toggle() == "espectro" else "  Espectro"))
        self.b_imp = btn("Reemplazar con WAV", "folder")
        self.b_imp.clicked.connect(self.import_wav)
        for b in (self.b_play, b_stop):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.b_spec)
        bar.addWidget(self.b_imp)
        wl.addLayout(bar)
        # recortes y fades manuales
        tr = hbox(None, 0, 8)
        tr.addWidget(caption("Recorte"))
        self.trim = {}
        for k, lab, mx in (("ini", "Inicio ms", 60000), ("fin", "Fin ms", 60000), ("fi", "Fade in ms", 2000), ("fo", "Fade out ms", 5000)):
            l = QLabel(lab)
            l.setObjectName("Mut")
            tr.addWidget(l)
            sp = QSpinBox()
            sp.setRange(0, mx)
            sp.setFixedWidth(78)
            sp.valueChanged.connect(self._trim_preview)
            tr.addWidget(sp)
            self.trim[k] = sp
        tr.addStretch(1)
        self.b_trim = btn("Aplicar recorte", "check")
        self.b_trim.setToolTip("Clic izquierdo en la onda = inicio · clic derecho = final")
        self.b_trim.clicked.connect(self.apply_trim)
        tr.addWidget(self.b_trim)
        wl.addLayout(tr)
        self.wave.editable = True
        self.wave.marksChanged.connect(self._marks_from_wave)
        right.addWidget(wc)

        # capas de velocidad de la tecla
        vc = card()
        self.vel_l = vbox(vc, 14, 6)
        rowv = hbox(None, 0, 8)
        rowv.addWidget(caption("Capas de velocidad de la tecla"))
        rowv.addStretch(1)
        self.b_vel = btn("Aplicar rangos", "check")
        self.b_vel.clicked.connect(self.apply_ranges)
        rowv.addWidget(self.b_vel)
        self.vel_l.addLayout(rowv)
        self.vel_rows = QGridLayout()
        self.vel_l.addLayout(self.vel_rows)
        self.vel_spins = []
        right.addWidget(vc)

        mc = card()
        ml = QGridLayout(mc)
        ml.setContentsMargins(14, 12, 14, 12)
        ml.setHorizontalSpacing(18)
        ml.setVerticalSpacing(8)
        self.metrics = {}
        for i, (k, lab) in enumerate((("dur", "Duración"), ("ch", "Canales"), ("pk", "Pico"), ("rms", "RMS"),
                                      ("dc", "DC offset"), ("lead", "Silencio inicial"), ("tail", "Silencio final"), ("sr", "Frecuencia"))):
            box = QVBoxLayout()
            box.setSpacing(2)
            box.addWidget(caption(lab))
            v = QLabel("—")
            v.setObjectName("Big")
            box.addWidget(v)
            self.metrics[k] = v
            ml.addLayout(box, i // 4, i % 4)
        right.addWidget(mc)

        ec = card()
        el = vbox(ec, 14, 8)
        el.addWidget(caption("Parámetros de la tecla"))
        row = QGridLayout()
        row.setHorizontalSpacing(10)
        row.setVerticalSpacing(6)
        self.ed = {}
        for k, lab, lo, hi, st, dec in (("tune", "Afinación (st)", -48, 48, 1, 0), ("vol", "Volumen (dB)", -96, 12, 0.5, 1),
                                        ("pan", "Paneo", -64, 63, 1, 0), ("cut", "Filtro (Hz)", 20, 20000, 100, 0),
                                        ("grp", "Grupo de corte", 0, 127, 1, 0)):
            col = QVBoxLayout()
            col.setSpacing(4)
            l = QLabel(lab)
            l.setObjectName("Mut")
            col.addWidget(l)
            sp = QDoubleSpinBox() if dec else QSpinBox()
            sp.setRange(lo, hi)
            sp.setSingleStep(st)
            if dec:
                sp.setDecimals(dec)
            col.addWidget(sp)
            idx = len(self.ed)
            row.addLayout(col, idx // 3, idx % 3)
            self.ed[k] = sp
        self.b_apply = btn("Aplicar", "check")
        self.b_apply.clicked.connect(self.apply_params)
        row.addWidget(self.b_apply, 1, 2, Qt.AlignmentFlag.AlignBottom)
        el.addLayout(row)
        el.addStretch(1)
        bottom = hbox(None, 0, 14)
        bottom.addWidget(ec, 3)
        pcard = card()
        pl2 = vbox(pcard, 14, 6)
        pl2.addWidget(caption("Diagnóstico"))
        self.probs = text_view(60)
        pl2.addWidget(self.probs)
        bottom.addWidget(pcard, 2)
        right.addLayout(bottom)
        right.addStretch(1)
        self.zones = []

    def load(self, pack):
        self.zones = []
        self.tbl.setRowCount(0)
        status = {}
        order = ("OK", "INFO", "AVISO", "ERROR")
        for k in self.ctx.kits:
            for z in k.zones:
                r = self.ctx.rep_by_uid.get(z["uid"])
                st = r.worst if r else "ERROR"
                key = note_name(z["note_lo"]) if z["note_lo"] == z["note_hi"] else f"{note_name(z['note_lo'])}–{note_name(z['note_hi'])}"
                if z["vel_lo"] != 1 or z["vel_hi"] != 127:
                    key += f"  v{z['vel_lo']}-{z['vel_hi']}"
                i = self.tbl.rowCount()
                self.tbl.insertRow(i)
                self.tbl.setItem(i, 0, cell(key, bold=True))
                self.tbl.setItem(i, 1, cell(", ".join(sorted(set(z["samples"]))) or "(falta)"))
                self.tbl.setItem(i, 2, cell(f"{r.peak_db:.1f}" if r else "", "mut", Qt.AlignmentFlag.AlignRight))
                self.tbl.setItem(i, 3, cell(st, st if st != "OK" else "OK", Qt.AlignmentFlag.AlignCenter, True))
                self.zones.append(z)
                for n in range(z["note_lo"], min(z["note_hi"], z["note_lo"] + 127) + 1):
                    prev = status.get(n)
                    status[n] = st if prev is None or order.index(st) > order.index(prev) else prev
        self.piano.set_keys(status)
        if self.zones:
            self.tbl.selectRow(0)

    def current(self):
        r = self.tbl.currentRow()
        return self.zones[r] if 0 <= r < len(self.zones) else None

    def select_note(self, n, play=False):
        for i, z in enumerate(self.zones):
            if z["note_lo"] <= n <= z["note_hi"]:
                self.tbl.selectRow(i)
                if play:
                    self.play()
                return

    def _on_select(self):
        z = self.current()
        pack = self.ctx.pack
        if z is None or pack is None:
            return
        w = pack.waves.get(z["uid"])
        r = self.ctx.rep_by_uid.get(z["uid"])
        self.piano.selected = z["note_lo"]
        self.piano.update()
        if w is not None:
            self.wave.show_wave(w.samples, w.rate, w.name, r.lead_silence_ms if r else 0, r.tail_silence_ms if r else 0)
        if r:
            m = self.metrics
            m["dur"].setText(f"{r.duration:.2f} s")
            m["ch"].setText("Estéreo" if r.channels > 1 else ("Mono (L+R)" if z["fake_stereo"] else "Mono"))
            m["pk"].setText(f"{r.peak_db:.1f} dB")
            m["pk"].setStyleSheet(f"color:{C['ERROR']}" if r.clipped else "")
            m["rms"].setText(f"{r.rms_db:.1f} dB")
            m["dc"].setText(f"{r.dc_pct:+.2f} %")
            m["lead"].setText(f"{r.lead_silence_ms:.0f} ms")
            m["tail"].setText(f"{r.tail_silence_ms:.0f} ms")
            m["sr"].setText(f"{r.rate / 1000:.1f} kHz")
            self.probs.setHtml(problems_html(r.problems))
        self._fill_params(z)
        self._fill_trim(w)
        self._fill_ranges(z)

    def _fill_params(self, z):
        import motor
        pack = self.ctx.pack
        if not pack.voices:
            return
        el = next((e for e in pack.voices[0].elements if e.number == z["element"]), None)
        if el is None:
            return
        snd, _ = motor.parse_sound(pack.voices[0])
        es = snd.get(el.number)
        self.ed["tune"].setValue(el.tune_coarse)
        self.ed["vol"].setValue(es.vol_db if es else 0)
        self.ed["pan"].setValue(round(el.pan if abs(el.pan) > 1 else el.pan * 64))
        self.ed["cut"].setValue(int(es.lpf_hz) if es and es.lpf_hz else 20000)
        self.ed["grp"].setValue(el.alternate_group)

    def play(self):
        z = self.current()
        if z is None:
            return
        w = self.ctx.pack.waves.get(z["uid"])
        if w is None:
            return
        x = w.samples if w.channels == 2 else np.repeat(w.samples, 2, axis=1)
        self.piano.flash(z["note_lo"])
        self.ctx.audio.play(x.astype(np.float32))

    # ------------------------------------------------------------ mapeo
    def _start_drag(self, actions):
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDrag
        from qt_import import MIME
        r = self.tbl.currentRow()
        if r < 0:
            return
        md = QMimeData()
        md.setData(MIME, f"row:{r}".encode())
        d = QDrag(self.tbl)
        d.setMimeData(md)
        d.exec(Qt.DropAction.MoveAction)

    def _dropped(self, nota, data):
        from ppf_format import mover_tecla, reparse_voices
        pack = self.ctx.pack
        if not data.startswith("row:") or pack is None or not pack.voices:
            return
        if pack.voices[0].voice_type != "DRUM_KIT":
            self.ctx.toast("Mover teclas solo está disponible en drum kits.", "AVISO")
            return
        z = self.zones[int(data[4:])]
        src = z["element"]
        if src == nota:
            return
        self.ctx.snapshot()
        if mover_tecla(pack, pack.voices[0], src, nota):
            reparse_voices(pack)
            self.ctx.mark_modified(f"{note_name(src)} ⇄ {note_name(nota)}")
            self.select_note(nota)

    def _fill_ranges(self, z):
        from ppf_format import capas_de
        while self.vel_rows.count():
            it = self.vel_rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.vel_spins = []
        pack = self.ctx.pack
        if not pack or not pack.voices:
            return
        capas = capas_de(pack.voices[0], z["element"])
        for i, (lo, hi, uid) in enumerate(capas):
            w = pack.waves.get(uid)
            lab = QLabel(f"Capa {i + 1} · {w.name if w else '?'}")
            self.vel_rows.addWidget(lab, i, 0)
            a, b = QSpinBox(), QSpinBox()
            for sp, v in ((a, lo), (b, hi)):
                sp.setRange(1, 127)
                sp.setValue(v)
                sp.setFixedWidth(70)
            self.vel_rows.addWidget(QLabel("de"), i, 1)
            self.vel_rows.addWidget(a, i, 2)
            self.vel_rows.addWidget(QLabel("a"), i, 3)
            self.vel_rows.addWidget(b, i, 4)
            self.vel_spins.append((a, b))
        self.b_vel.setEnabled(len(capas) > 0)

    def apply_ranges(self):
        from ppf_format import fijar_rangos, reparse_voices
        z = self.current()
        pack = self.ctx.pack
        if z is None or not self.vel_spins:
            return
        rangos = [(a.value(), b.value()) for a, b in self.vel_spins]
        if any(lo > hi for lo, hi in rangos):
            self.ctx.toast("Cada rango debe ir de menor a mayor.", "AVISO")
            return
        self.ctx.snapshot()
        if fijar_rangos(pack, pack.voices[0], z["element"], rangos):
            reparse_voices(pack)
            self.ctx.mark_modified(f"Rangos de velocidad de {note_name(z['note_lo'])}")

    # ------------------------------------------------------------ recortes
    def _fill_trim(self, w):
        if w is None:
            return
        dur_ms = int(w.duration * 1000)
        for sp in self.trim.values():
            sp.blockSignals(True)
        self.trim["ini"].setRange(0, dur_ms)
        self.trim["fin"].setRange(0, dur_ms)
        self.trim["ini"].setValue(0)
        self.trim["fin"].setValue(dur_ms)
        self.trim["fi"].setValue(0)
        self.trim["fo"].setValue(0)
        for sp in self.trim.values():
            sp.blockSignals(False)
        self._trim_preview()

    def _trim_preview(self, *_):
        t = {k: sp.value() / 1000 for k, sp in self.trim.items()}
        self.wave.marks = (t["ini"], t["fin"], t["fi"], t["fo"])
        self.wave.update()

    def _marks_from_wave(self, t0, t1):
        self.trim["ini"].setValue(int(t0 * 1000))
        self.trim["fin"].setValue(int(t1 * 1000))

    def apply_trim(self):
        import copy as _copy
        from ppf_format import replace_wave, reparse_voices
        z = self.current()
        pack = self.ctx.pack
        if z is None or pack is None:
            return
        w = pack.waves.get(z["uid"])
        sr = w.rate
        a, b = int(self.trim["ini"].value() / 1000 * sr), int(self.trim["fin"].value() / 1000 * sr)
        if b - a < 64:
            self.ctx.toast("El recorte es demasiado corto.", "AVISO")
            return
        x = w.samples[a:b].copy()
        fi, fo = int(self.trim["fi"].value() / 1000 * sr), int(self.trim["fo"].value() / 1000 * sr)
        if fi > 1:
            n = min(fi, len(x))
            x[:n] *= (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n)))[:, None]
        if fo > 1:
            n = min(fo, len(x))
            x[-n:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, n)))[:, None]
        self.ctx.snapshot()
        nw = _copy.copy(w)
        nw.samples = x
        nw.markers = {k: (len(x) if pos >= w.frames else max(0, min(pos - a, len(x))), nm) for k, (pos, nm) in w.markers.items()}
        replace_wave(pack, z["uid"], nw)
        reparse_voices(pack)
        self.ctx.mark_modified(f"'{w.name}' recortada a {len(x) / sr:.2f} s")

    def apply_params(self):
        from ppf_format import edit_element, reparse_voices
        z = self.current()
        pack = self.ctx.pack
        if z is None or pack is None:
            return
        self.ctx.snapshot()
        v = pack.voices[0]
        n = z["element"]
        edit_element(pack, v, n, "pitchBlock", "tuneCoarse", int(self.ed["tune"].value()))
        edit_element(pack, v, n, None, "volume", float(self.ed["vol"].value()))
        edit_element(pack, v, n, "panBlock", "pan", float(self.ed["pan"].value()))
        edit_element(pack, v, n, "filterBlock", "dcfCutoff", float(self.ed["cut"].value()))
        edit_element(pack, v, n, "drumSetup", "alternateGroup", int(self.ed["grp"].value()))
        reparse_voices(pack)
        self.ctx.mark_modified(f"Parámetros de {note_name(z['note_lo'])} actualizados")

    def import_wav(self):
        import copy as _copy
        import wave as wavelib
        import dsp
        from ppf_format import replace_wave, reparse_voices
        z = self.current()
        if z is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "WAV para reemplazar la muestra", "", "WAV (*.wav)")
        if not path:
            return
        try:
            with wavelib.open(path, "rb") as f:
                ch, sw, sr, n = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
                raw = f.readframes(n)
            if sw == 2:
                x = np.frombuffer(raw, "<i2").astype(np.float64) / 32768
            elif sw == 3:
                b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
                v24 = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
                x = np.where(v24 >= 1 << 23, v24 - (1 << 24), v24) / 8388608.0
            elif sw == 4:
                x = np.frombuffer(raw, "<i4").astype(np.float64) / 2147483648
            else:
                raise ValueError(f"{sw * 8} bits no soportado")
            x = x.reshape(-1, ch)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "PPF Tester", f"No se pudo leer el WAV (usa PCM 16/24/32 bits):\n{e}")
            return
        pack = self.ctx.pack
        self.ctx.snapshot()
        old = pack.waves[z["uid"]]
        x = dsp.to_rate(x, sr, 44100)
        x = x[:, :1] if old.channels == 1 else (x if x.shape[1] == 2 else np.repeat(x, 2, axis=1))
        nw = _copy.copy(old)
        nw.samples = np.clip(x, -1, 32767 / 32768)
        nw.markers = {k: (len(x) if pos >= old.frames else min(pos, len(x)), nm) for k, (pos, nm) in old.markers.items()}
        replace_wave(pack, z["uid"], nw)
        reparse_voices(pack)
        self.ctx.mark_modified(f"'{old.name}' reemplazada por {os.path.basename(path)}")


# =================================================================== revisión
class ReviewPage(Page):
    title = "Revisión del kit"
    subtitle = "Mapa de teclas, velocidades, muestras repetidas y balance."

    def __init__(self, ctx):
        super().__init__(ctx)
        root = vbox(self, 0, 14)
        top = hbox(None, 0, 14)
        self.tiles = {}
        for k, lab, col in (("ERROR", "Errores", "ERROR"), ("AVISO", "Avisos", "AVISO"), ("INFO", "Notas", "INFO"), ("OK", "Muestras OK", "OK")):
            c = card()
            l = vbox(c, 16, 4)
            l.addWidget(caption(lab))
            v = QLabel("—")
            v.setStyleSheet(f"font-size: 26pt; font-weight: 300; color: {C[col]}")
            l.addWidget(v)
            self.tiles[k] = v
            top.addWidget(c)
        root.addLayout(top)
        mid = hbox(None, 0, 14)
        c = card()
        l = vbox(c, 18, 8)
        l.addWidget(caption("Kit"))
        self.kit = text_view(120)
        l.addWidget(self.kit)
        mid.addWidget(c, 2)
        cc = card()
        lc = vbox(cc, 18, 8)
        rowc = hbox(None, 0, 8)
        rowc.addWidget(caption("Compatibilidad por modelo"))
        rowc.addStretch(1)
        b_em = btn("Expansion Manager", "export", primary=True, tip="Abre este kit en Yamaha Expansion Manager")
        b_em.clicked.connect(self.open_em)
        rowc.addWidget(b_em)
        b_how = btn("Instalar en el PSR", "info")
        b_how.clicked.connect(self.how_install)
        rowc.addWidget(b_how)
        lc.addLayout(rowc)
        self.compat = text_view(120)
        lc.addWidget(self.compat)
        mid.addWidget(cc, 3)
        root.addLayout(mid, 1)
        c3 = card()
        l3 = vbox(c3, 18, 8)
        rowr = hbox(None, 0, 8)
        rowr.addWidget(caption("Comparar con un kit de referencia"))
        rowr.addStretch(1)
        b_ref = btn("Elegir kit de referencia…", "folder")
        b_ref.clicked.connect(self.compare_ref)
        rowr.addWidget(b_ref)
        l3.addLayout(rowr)
        self.ref = text_view(90)
        self.ref.setHtml(f"<p style='color:{C['mut']}'>Elige un .ppf que te guste cómo suena y te digo qué cambiar en el tuyo "
                         "(balance entre piezas, brillo y largo de las colas).</p>")
        l3.addWidget(self.ref)
        root.addWidget(c3, 1)
        c2 = card()
        l2 = vbox(c2, 18, 8)
        l2.addWidget(caption("Muestras con observaciones"))
        self.samples = text_view(120)
        l2.addWidget(self.samples)
        root.addWidget(c2, 1)

    def load(self, pack):
        kits, waves = self.ctx.kits, self.ctx.waves
        kp = [A.Problem("ERROR", "lectura", e) for e in pack.errors] + [p for k in kits for p in k.problems]
        allp = kp + [p for w in waves for p in w.problems]
        for lv in ("ERROR", "AVISO", "INFO"):
            self.tiles[lv].setText(str(sum(p.level == lv for p in allp)))
        self.tiles["OK"].setText(f"{sum(w.worst == 'OK' for w in waves)}/{len(waves)}")
        self.kit.setHtml(problems_html(kp, "El mapa del kit está correcto."))
        parts = []
        for w in waves:
            if w.problems:
                parts.append(f"<p style='margin:10px 0 2px 0; font-weight:700'>{w.name}</p>" + problems_html(w.problems))
        self.samples.setHtml("".join(parts) or problems_html([], "Todas las muestras están bien."))
        import compat
        rows = []
        for r in compat.revisar(pack):
            col = LV_COLOR.get(r.estado, C["fg"])
            rows.append(f"<tr><td style='padding:4px 12px 4px 0; font-weight:700; white-space:nowrap'>{r.modelo}</td>"
                        f"<td style='padding:4px 12px 4px 0; color:{col}; white-space:nowrap'>{r.resumen}</td>"
                        f"<td style='padding:4px 0'>{'<br>'.join(r.detalles)}</td></tr>")
        self.compat.setHtml("<table cellspacing=0>" + "".join(rows) + "</table>"
                            f"<p style='color:{C['mut']}'>Según la memoria de cada modelo y lo recomendado para que el kit suene bien. "
                            "Pruébalo siempre en el teclado.</p>")

    def open_em(self):
        import compat
        if self.ctx.modified and QMessageBox.question(self, "PPF Tester", "Hay cambios sin guardar: Expansion Manager abrirá el archivo "
                                                      "guardado. ¿Continuar?") != QMessageBox.StandardButton.Yes:
            return
        ok, msg = compat.abrir_em(self.ctx.pack.path if self.ctx.pack else None)
        if ok and self.ctx.pack:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.ctx.pack.path)
            msg += " (la ruta del .ppf quedó copiada)"
        self.ctx.toast(msg, "OK" if ok else "AVISO", 6000)

    def how_install(self):
        import compat
        QMessageBox.information(self, "Instalar en el PSR", "Cómo pasar el kit al teclado:\n\n" +
                                "\n".join(f"{i + 1}. {p}" for i, p in enumerate(compat.PASOS_EM)) +
                                "\n\nEl archivo de instalación lo crea Expansion Manager porque va cifrado para tu teclado; "
                                "esta app prepara y revisa el .ppf.")

    def compare_ref(self):
        import referencia
        from ppf_format import load_pack
        path, _ = QFileDialog.getOpenFileName(self, "Kit de referencia", "", "Yamaha Expansion Manager (*.ppf)")
        if not path or self.ctx.pack is None:
            return
        mio = self.ctx.pack

        def done(filas):
            def celda(v):
                return "—" if not v else f"{v['rel']:+.1f} dB · {v['brillo'] / 1000:.1f} kHz · {v['dur']:.1f} s"
            rows = "".join(
                f"<tr><td style='padding:4px 12px 4px 0; font-weight:700'>{f['tipo']}</td><td style='padding-right:12px'>{celda(f['mio'])}</td>"
                f"<td style='padding-right:12px'>{celda(f['ref'])}</td>"
                f"<td style='color:{C['AVISO'] if f['consejos'] else C['OK']}'>{', '.join(f['consejos']) or 'parecido'}</td></tr>" for f in filas)
            self.ref.setHtml(f"<p style='color:{C['mut']}'>Referencia: {os.path.basename(path)} · nivel relativo al bombo · brillo · duración</p>"
                             f"<table cellspacing=0><tr style='color:{C['mut']}'><td>Pieza</td><td>Tu kit</td><td>Referencia</td><td>Sugerencia</td></tr>{rows}</table>")
            self.ctx.toast("Comparación lista", "OK")

        self.ctx.run_bg(lambda: referencia.comparar(mio, load_pack(path)), done)


# ==================================================================== teclado
class KeyboardPage(Page):
    title = "Prueba en el teclado"
    subtitle = "Toca todas las notas en el PSR por USB-MIDI y graba lo que suena."

    def __init__(self, ctx):
        super().__init__(ctx)
        root = vbox(self, 0, 14)
        c = card()
        g = QGridLayout(c)
        g.setContentsMargins(18, 16, 18, 16)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        hint = QLabel("1. Conecta el PSR por USB TO HOST, instala el pack y elige la voz en RIGHT 1.   "
                      "2. Conecta la salida de auriculares del PSR a tu interfaz de audio.   3. Pulsa Iniciar.")
        hint.setObjectName("Mut")
        hint.setWordWrap(True)
        g.addWidget(hint, 0, 0, 1, 6)
        g.addWidget(caption("Salida MIDI"), 1, 0)
        self.cb_midi = QComboBox()
        g.addWidget(self.cb_midi, 2, 0, 1, 2)
        g.addWidget(caption("Canal"), 1, 2)
        self.sp_ch = QSpinBox()
        self.sp_ch.setRange(1, 16)
        g.addWidget(self.sp_ch, 2, 2)
        g.addWidget(caption("Velocidades"), 1, 3)
        self.e_vel = QLineEdit("40,80,127")
        g.addWidget(self.e_vel, 2, 3)
        g.addWidget(caption("Entrada de audio"), 3, 0)
        self.cb_in = QComboBox()
        g.addWidget(self.cb_in, 4, 0, 1, 2)
        self.chk_rec = QCheckBox("Grabar la salida del teclado")
        self.chk_rec.setChecked(True)
        g.addWidget(self.chk_rec, 4, 2, 1, 2)
        b_ref = btn("Buscar dispositivos", "refresh")
        b_ref.clicked.connect(self.refresh)
        g.addWidget(b_ref, 2, 4)
        b_wiz = btn("Asistente paso a paso", "sparkle")
        b_wiz.setToolTip("Te guía para conectar el PSR, comprobar MIDI y audio, probar el kit y calibrar")
        b_wiz.clicked.connect(self.wizard)
        g.addWidget(b_wiz, 3, 4)
        self.b_test = btn("Iniciar prueba", "play", primary=True)
        self.b_test.clicked.connect(self.run)
        g.addWidget(self.b_test, 4, 4)
        g.addWidget(caption("Nivel de entrada"), 1, 5)
        self.meter = LevelMeter()
        self.meter.level_fn = lambda: self.ctx.audio.input_level()
        g.addWidget(self.meter, 2, 5)
        g.setColumnStretch(0, 2)
        g.setColumnStretch(5, 1)
        root.addWidget(c)

        rc = card()
        rl = vbox(rc, 18, 8)
        rl.addWidget(caption("Resultado"))
        self.result = text_view(80)
        rl.addWidget(self.result)
        self.tbl = table(["Tecla", "Vel", "Muestra", "Pico", "Retardo"], [80, 60, None, 90, 90])
        rl.addWidget(self.tbl, 1)
        root.addWidget(rc, 1)
        self.refresh()

    def refresh(self):
        try:
            import midi_test as M
            outs = M.midi_outputs()
            cur = self.cb_midi.currentText()
            self.cb_midi.clear()
            self.cb_midi.addItems([f"[{i}] {n}" for i, n in enumerate(outs)])
            kb = M.find_keyboard_port()
            if outs:
                self.cb_midi.setCurrentIndex(kb if kb is not None else max(0, self.cb_midi.findText(cur)))
        except Exception as e:  # noqa: BLE001
            self.cb_midi.clear()
            self.cb_midi.addItem(f"(MIDI no disponible: {e})")
        try:
            import sounddevice as sd
            cur = self.cb_in.currentText()
            self.cb_in.clear()
            items = []
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0:
                    api = sd.query_hostapis(d["hostapi"])["name"]
                    items.append(f"[{i}] {d['name']} · {api}")
            self.cb_in.addItems(items)
            idx = self.cb_in.findText(cur)
            if idx < 0:
                idx = next((k for k, s in enumerate(items) if ("M-Track" in s or "Line" in s) and "MME" in s), 0)
            self.cb_in.setCurrentIndex(idx)
        except Exception:  # noqa: BLE001
            self.cb_in.clear()
            self.cb_in.addItem("(instala sounddevice para grabar)")

    def wizard(self):
        if self.ctx.pack is None:
            return
        from qt_pages3 import PsrWizard
        PsrWizard(self.ctx).exec()

    def midi_port(self):
        s = self.cb_midi.currentText()
        return int(s.split("]")[0].strip("[")) if s.startswith("[") else None

    def in_dev(self):
        s = self.cb_in.currentText()
        return int(s.split("]")[0].strip("[")) if s.startswith("[") else None

    def run(self):
        import midi_test as M
        from ppf_tester import _safe, _write_wav
        if not self.ctx.kits:
            return
        port = self.midi_port()
        if port is None:
            self.ctx.toast("Elige la salida MIDI del PSR.", "AVISO")
            return
        try:
            vels = [int(v) for v in self.e_vel.text().split(",") if v.strip()]
        except ValueError:
            self.ctx.toast("Revisa las velocidades (ej.: 40,80,127).", "AVISO")
            return
        ch = self.sp_ch.value()
        rec = self.chk_rec.isChecked() and self.in_dev() is not None
        kit = self.ctx.kits[0]
        if QMessageBox.question(self, "PPF Tester", f"Selecciona la voz «{kit.voice}» en RIGHT 1 del teclado (canal {ch}).\n\n¿Empezar la prueba?") != QMessageBox.StandardButton.Yes:
            return
        self.b_test.setEnabled(False)
        self.result.setHtml(f"<p style='color:{C['mut']}'>Tocando el kit…</p>")
        pack = self.ctx.pack
        waves_by_name = {w.name: w for w in pack.waves.values()}
        dev = self.in_dev()

        def job():
            self.ctx.audio.close_live()
            hits, audio, sr = M.run_test(kit, waves_by_name, port, ch, vels, dev, rec)
            probs = M.evaluate(hits) if rec else []
            folder = None
            if rec:
                folder = os.path.splitext(pack.path)[0] + "_grabacion"
                os.makedirs(folder, exist_ok=True)
                _write_wav(os.path.join(folder, "sesion_completa.wav"), audio, sr)
                for h in hits:
                    if h.audio is not None:
                        _write_wav(os.path.join(folder, f"{h.note:03d}_{note_name(h.note).replace('#', 's')}_v{h.vel:03d}_{_safe(h.name)}.wav"), h.audio, sr)
            return hits, probs, folder, rec

        def done(res):
            hits, probs, folder, rec = res
            self.b_test.setEnabled(True)
            if not rec:
                self.result.setHtml(f"<p style='color:{C['OK']}'>Prueba terminada (sin grabación).</p>")
                return
            ok = not [p for p in probs if p.level != "INFO"]
            head = f"<p style='color:{C['OK']}'>✔&nbsp; Todas las notas sonaron y la dinámica es correcta.</p>" if ok else ""
            self.result.setHtml(head + problems_html(probs, "") + f"<p style='color:{C['mut']}'>Grabaciones en: {folder}</p>")
            self.tbl.setRowCount(0)
            for h in hits:
                i = self.tbl.rowCount()
                self.tbl.insertRow(i)
                self.tbl.setItem(i, 0, cell(note_name(h.note), bold=True))
                self.tbl.setItem(i, 1, cell(h.vel, "mut"))
                self.tbl.setItem(i, 2, cell(h.name))
                self.tbl.setItem(i, 3, cell(f"{h.peak_db:.1f} dB", "mut", Qt.AlignmentFlag.AlignRight))
                lat = f"{h.latency_ms:.0f} ms" if h.latency_ms is not None else "MUDO"
                self.tbl.setItem(i, 4, cell(lat, None if h.latency_ms is not None else "ERROR", Qt.AlignmentFlag.AlignRight))
            self.ctx.toast("Prueba en el teclado terminada", "OK")

        self.ctx.run_bg(job, done, lambda: self.b_test.setEnabled(True))
