"""Páginas Qt: Escuchar como en el teclado y Mejorar kit."""
from __future__ import annotations

import copy
import os
import threading

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QGridLayout, QLabel,
                               QMessageBox, QProgressBar, QSlider, QSpinBox, QVBoxLayout)

import mejora as Mj
import modelos
import motor as M
from ppf_format import load_pack, note_name
from qt_fx import GlowPiano, LevelMeter, MemoryBars, WaveView, caption, card
from qt_pages import Page, btn, cell, hbox, problems_html, table, text_view, vbox
from qt_theme import C

KEYS = list("asdfghjklñ") + list("qwertyuiop") + list("zxcvbnm")


def slider(lo, hi, val):
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    s.setCursor(Qt.CursorShape.PointingHandCursor)
    return s


# ==================================================================== escuchar
class ListenPage(Page):
    title = "Escuchar como en el teclado"
    subtitle = "Toca el kit con el ratón o con el teclado del PC. Compara original, simulación y PSR real."

    def __init__(self, ctx):
        super().__init__(ctx)
        self.engine = None
        self.keymap: dict[str, int] = {}
        self.held: set[str] = set()
        self.last = None
        self.recs = {}
        self.player = None

        root = vbox(self, 0, 14)
        pc = card()
        pl = vbox(pc, 14, 8)
        hint = QLabel("Más abajo en la tecla = más fuerte  ·  letras del teclado del PC sobre cada tecla  ·  Mayús = acento")
        hint.setObjectName("Mut")
        pl.addWidget(hint)
        self.piano = GlowPiano(height=130)
        self.piano.keyClicked.connect(self._piano_hit)
        pl.addWidget(self.piano)
        root.addWidget(pc)

        ctl = hbox(None, 0, 14)
        root.addLayout(ctl)
        # fuente
        c1 = card()
        l1 = vbox(c1, 16, 8)
        l1.addWidget(caption("Qué escuchar"))
        seg = hbox(None, 0, 0)
        self.src = QButtonGroup(self)
        for i, (k, t) in enumerate((("sim", "Simulación"), ("real", "PSR real"), ("orig", "Original"))):
            b = btn(t)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setProperty("key", k)
            r = "9px" if i in (0, 2) else "0"
            b.setStyleSheet(f"QPushButton#Seg {{ border-top-left-radius: {r if i == 0 else 0}; border-bottom-left-radius: {r if i == 0 else 0};"
                            f" border-top-right-radius: {r if i == 2 else 0}; border-bottom-right-radius: {r if i == 2 else 0}; }}")
            self.src.addButton(b, i)
            seg.addWidget(b)
        self.src.button(0).setChecked(True)
        self.src.idClicked.connect(lambda i: self._source_changed())
        l1.addLayout(seg)
        self.src_hint = QLabel("Aproximación del motor del PSR, sin el teclado.")
        self.src_hint.setObjectName("Mut")
        self.src_hint.setWordWrap(True)
        l1.addWidget(self.src_hint)
        ctl.addWidget(c1, 3)
        # toque
        c2 = card()
        l2 = vbox(c2, 16, 8)
        row = hbox(None, 0, 6)
        row.addWidget(caption("Velocidad"))
        row.addStretch(1)
        self.vel_lab = QLabel("100")
        self.vel_lab.setStyleSheet(f"color:{C['gold']}; font-weight:700")
        row.addWidget(self.vel_lab)
        l2.addLayout(row)
        self.vel = slider(1, 127, 100)
        self.vel.valueChanged.connect(lambda v: self.vel_lab.setText(str(v)))
        l2.addWidget(self.vel)
        self.vel_pos = QCheckBox("Según dónde pulses la tecla")
        self.vel_pos.setChecked(True)
        l2.addWidget(self.vel_pos)
        ctl.addWidget(c2, 2)
        # simulación
        c3 = card()
        l3 = vbox(c3, 16, 8)
        l3.addWidget(caption("Simulación"))
        self.chk_filter = QCheckBox("Filtro de la voz (paso-bajo del pack)")
        self.chk_filter.setChecked(True)
        self.chk_filter.toggled.connect(self._sim_changed)
        l3.addWidget(self.chk_filter)
        row = hbox(None, 0, 6)
        l = QLabel("Reverb")
        row.addWidget(l)
        row.addStretch(1)
        self.rev_lab = QLabel("0 %")
        self.rev_lab.setStyleSheet(f"color:{C['gold']}; font-weight:700")
        row.addWidget(self.rev_lab)
        l3.addLayout(row)
        self.rev = slider(0, 100, 0)
        self.rev.valueChanged.connect(self._rev_changed)
        l3.addWidget(self.rev)
        ctl.addWidget(c3, 2)
        # PSR real
        c4 = card()
        l4 = vbox(c4, 16, 8)
        l4.addWidget(caption("PSR real"))
        self.chk_mon = QCheckBox("Oír el PSR por el PC (monitor)")
        self.chk_mon.toggled.connect(self._live_changed)
        l4.addWidget(self.chk_mon)
        self.chk_rec = QCheckBox("Grabar cada golpe para comparar")
        self.chk_rec.setChecked(True)
        self.chk_rec.toggled.connect(self._live_changed)
        l4.addWidget(self.chk_rec)
        self.meter = LevelMeter()
        self.meter.level_fn = lambda: self.ctx.audio.input_level()
        l4.addWidget(self.meter)
        ctl.addWidget(c4, 2)

        # ritmos
        gc = card()
        gl = hbox(gc, 16, 12)
        gl.setContentsMargins(16, 10, 16, 10)
        gl.addWidget(caption("Ritmo de prueba"))
        import grooves as G
        self.G = G
        self.groove = QComboBox()
        self.groove.addItems(list(G.PATRONES))
        gl.addWidget(self.groove, 1)
        gl.addWidget(QLabel("BPM"))
        self.bpm = QSpinBox()
        self.bpm.setRange(40, 220)
        self.bpm.setValue(76)
        gl.addWidget(self.bpm)
        self.b_groove = btn("Tocar ritmo", "play", primary=True)
        self.b_groove.clicked.connect(self.toggle_groove)
        gl.addWidget(self.b_groove)
        root.addWidget(gc)

        # A/B
        ab = card()
        al = vbox(ab, 16, 10)
        top = hbox(None, 0, 8)
        self.ab_title = QLabel("Comparación A/B — toca una nota")
        self.ab_title.setObjectName("H2")
        top.addWidget(self.ab_title)
        top.addStretch(1)
        self.b_orig = btn("Original", "play")
        self.b_sim = btn("Simulación", "play")
        self.b_rec = btn("Grabación del PSR", "play", primary=True)
        b_stop = btn("Parar", "stop")
        for b, k in ((self.b_orig, "orig"), (self.b_sim, "sim"), (self.b_rec, "rec")):
            b.clicked.connect(lambda _=False, k=k: self._ab(k))
            b.setEnabled(False)
            top.addWidget(b)
        b_stop.clicked.connect(self.stop)
        top.addWidget(b_stop)
        al.addLayout(top)
        body = hbox(None, 0, 14)
        self.wave = WaveView(height=170)
        body.addWidget(self.wave, 3)
        self.info = text_view(120)
        body.addWidget(self.info, 2)
        al.addLayout(body, 1)
        root.addWidget(ab, 1)

    # ------------------------------------------------------------- carga
    def load(self, pack):
        self.stop_groove()
        self.recs.clear()
        self.last = None
        self.engine = M.Engine(pack, pack.voices[0]) if pack.voices else None
        if not self.engine:
            return
        self.engine.settings.use_filter = self.chk_filter.isChecked()
        r = round(self.engine.common["reverb"] / 127 * 100)
        self.rev.setValue(r)
        self._rev_changed(r)
        notes = sorted({n for _, _, lo, hi, _, _ in pack.voices[0].zones() for n in range(lo, min(hi, lo + 60) + 1)})
        self.keymap = dict(zip(KEYS, notes))
        self.piano.labels = {n: k.upper() for k, n in self.keymap.items()}
        self.piano.set_keys({n: "OK" for n in notes})
        threading.Thread(target=lambda: M._reverb_ir(M.SR, 0.8), daemon=True).start()
        self.wave.show_series([], "")
        self.info.setHtml(f"<p style='color:{C['mut']}'>Toca una nota para ver los parámetros que el teclado le aplica.</p>")

    def source(self):
        return self.src.checkedButton().property("key")

    def _source_changed(self):
        s = self.source()
        self.src_hint.setText({"sim": "Aproximación del motor del PSR, sin el teclado.",
                               "real": "La app toca tu PSR por USB-MIDI: es el sonido exacto.",
                               "orig": "La muestra tal cual está en el pack, sin procesar."}[s])
        if s == "real":
            try:
                self.ctx.audio.midi(self.ctx.keyboard.midi_port())
            except Exception as e:  # noqa: BLE001
                self.ctx.toast(str(e), "ERROR")
                self.src.button(0).setChecked(True)
                return
        self._live_changed()

    def _live_changed(self):
        need = self.chk_mon.isChecked() or (self.chk_rec.isChecked() and self.source() == "real")
        try:
            if need:
                self.ctx.audio.live(self.ctx.keyboard.in_dev(), self.chk_mon.isChecked())
            else:
                self.ctx.audio.close_live()
        except Exception as e:  # noqa: BLE001
            self.chk_mon.setChecked(False)
            self.ctx.toast(f"No se pudo abrir la entrada de audio: {e}", "ERROR")

    def _sim_changed(self):
        if self.engine:
            self.engine.settings.use_filter = self.chk_filter.isChecked()
            self.engine.invalidate()

    def _rev_changed(self, v):
        self.rev_lab.setText(f"{v} %")
        if self.engine:
            self.engine.settings.reverb = v / 100
            self.engine.invalidate()

    # ------------------------------------------------------------- tocar
    def _piano_hit(self, n, frac):
        if self.vel_pos.isChecked():
            vel = int(np.clip(20 + frac * 120, 1, 127))
            self.vel.setValue(vel)
        else:
            vel = self.vel.value()
        self.hit(n, vel)

    def key_press(self, e) -> bool:
        ch = (e.text() or "").lower()
        if ch not in self.keymap or e.isAutoRepeat():
            return False
        vel = 127 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else self.vel.value()
        self.hit(self.keymap[ch], vel)
        return True

    def _orig(self, n, vel):
        for _, kb in self.engine.zones_for(n, vel):
            w = self.engine.pack.waves.get(kb.samples[0].wave_uid)
            if w is not None:
                x = w.samples if w.channels == 2 else np.repeat(w.samples, 2, axis=1)
                return x.astype(np.float32), w.duration
        return None, 0.0

    def hit(self, n, vel):
        if not self.engine:
            return
        self.piano.flash(n)
        src = self.source()
        orig, dur = self._orig(n, vel)
        if orig is None:
            return
        sim, group = self.engine.render(n, vel)
        self.last = dict(note=n, vel=vel, orig=orig, sim=sim, rec=self.recs.get((n, vel)))
        try:
            if src == "sim":
                self.ctx.audio.play(sim, group, n)
            elif src == "orig":
                self.ctx.audio.play(orig, 0, n)
            else:
                self._play_real(n, vel, max(0.3, min(dur, 4.0)))
        except Exception as e:  # noqa: BLE001
            self.ctx.toast(f"Audio/MIDI: {e}", "ERROR")
        self._update_ab()

    def _play_real(self, n, vel, dur):
        midi = self.ctx.audio.midi(self.ctx.keyboard.midi_port())
        ch = self.ctx.keyboard.sp_ch.value()
        live = None
        if self.chk_rec.isChecked():
            live = self.ctx.audio.live(self.ctx.keyboard.in_dev(), self.chk_mon.isChecked())
            start = live.now() - int(0.05 * live.rate)
        midi.note(ch, n, vel)
        QTimer.singleShot(int(dur * 1000), lambda: midi.off(ch, n))
        if live is not None:
            def grab():
                rec = live.get(start, live.now())
                if len(rec):
                    self.recs[(n, vel)] = rec
                    if self.last and self.last["note"] == n and self.last["vel"] == vel:
                        self.last["rec"] = rec
                        self._update_ab()
            QTimer.singleShot(int((dur + 0.5) * 1000), grab)

    def _ab(self, which):
        if self.last and self.last.get(which) is not None:
            self.ctx.audio.play(self.last[which].astype(np.float32))

    def stop(self):
        self.ctx.audio.stop()
        try:
            if self.ctx.audio._midi is not None:
                self.ctx.audio._midi.all_off(self.ctx.keyboard.sp_ch.value())
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------- ritmos
    def stop_groove(self):
        if self.player is not None:
            self.player.stop()
            self.player = None
            self.b_groove.setText("  Tocar ritmo")

    def toggle_groove(self):
        if self.player is not None:
            self.stop_groove()
            return
        if not self.engine:
            return
        src = self.source()
        disp = set(self.keymap.values())
        audio = self.ctx.audio
        try:
            if src == "real":
                midi = audio.midi(self.ctx.keyboard.midi_port())
                ch = self.ctx.keyboard.sp_ch.value()

                def tocar(n, v):
                    midi.note(ch, n, v)
                    threading.Timer(0.08, lambda: midi.off(ch, n)).start()
            else:
                audio.mixer()
                if src == "sim":
                    for st, n, v in self.G.PATRONES[self.groove.currentText()][2]:
                        m = self.G.adaptar(n, disp)
                        if m is not None:
                            self.engine.render(m, v)

                def tocar(n, v):
                    if src == "sim":
                        buf, g = self.engine.render(n, v)
                    else:
                        buf, _d = self._orig(n, v)
                        g = 0
                    if buf is not None:
                        audio.play(buf, g, n)
                    self.piano.glow[n] = 1.0
            self.player = self.G.Reproductor(tocar, disp)
            self.player.start(self.groove.currentText(), float(self.bpm.value()))
            self.b_groove.setText("  Parar ritmo")
        except Exception as e:  # noqa: BLE001
            self.ctx.toast(str(e), "ERROR")

    # ------------------------------------------------------------- A/B
    def _update_ab(self):
        L = self.last
        if not L:
            return
        self.ab_title.setText(f"Comparación A/B — {note_name(L['note'])} · MIDI {L['note']} · velocidad {L['vel']}")
        self.b_orig.setEnabled(True)
        self.b_sim.setEnabled(True)
        self.b_rec.setEnabled(L.get("rec") is not None)
        series = [(M.align_onset(L["orig"]), "mut", "Original"), (M.align_onset(L["sim"]), "gold", "Simulación")]
        if L.get("rec") is not None:
            series.append((M.align_onset(L["rec"]), "blue", "PSR grabado"))
        self.wave.show_series(series)
        h = [f"<p style='color:{C['mut']}; margin:0 0 6px 0'>Parámetros de la voz</p>"]
        for line in self.engine.describe(L["note"]):
            h.append(f"<p style='margin:2px 0'>• {line}</p>")
        for el, _ in self.engine.zones_for(L["note"], L["vel"]):
            vdb = self.engine.velocity_db(self.engine.sound[el.number], L["vel"])
            h.append(f"<p style='margin:2px 0'>• Curva de velocidad: {vdb:+.1f} dB a velocidad {L['vel']}</p>")
            break
        rec = L.get("rec")
        if rec is not None:
            if np.abs(rec).max() < 10 ** (-55 / 20):
                h.append(f"<p style='color:{C['ERROR']}'><b>ERROR</b> No llegó sonido del PSR. Revisa la voz en RIGHT 1, el canal y el cable.</p>")
            else:
                c = M.compare(L["sim"], rec)
                o = M.compare(L["orig"], rec)
                h.append(f"<p style='color:{C['mut']}; margin:10px 0 4px 0'>Lo que suena en el PSR</p>")
                for pct, ref in ((o["brillo_pct"], "que la muestra original"), (c["brillo_pct"], "que la simulación")):
                    if pct < -15:
                        h.append(f"<p style='margin:2px 0'><b style='color:{C['AVISO']}'>AVISO</b> {abs(pct):.0f} % más opaco {ref}. "
                                 "Sube el corte del filtro de la nota si quieres más brillo.</p>")
                    elif pct > 15:
                        h.append(f"<p style='margin:2px 0'><b style='color:{C['INFO']}'>INFO</b> {pct:.0f} % más brillante {ref}.</p>")
                    else:
                        h.append(f"<p style='margin:2px 0'><b style='color:{C['OK']}'>OK</b> Mismo brillo {ref} ({pct:+.0f} %).</p>")
                if c["dur_rec"] < c["dur_sim"] * 0.75 and c["dur_sim"] > 0.3:
                    h.append(f"<p style='margin:2px 0'><b style='color:{C['AVISO']}'>AVISO</b> En el PSR se apaga antes "
                             f"({c['dur_rec']:.2f} s frente a {c['dur_sim']:.2f} s).</p>")
        elif self.source() != "real":
            h.append(f"<p style='color:{C['mut']}; margin-top:10px'>Para oír el sonido exacto, elige «PSR real» con «Grabar cada golpe».</p>")
        self.info.setHtml("".join(h))


# ===================================================================== mejorar
class ImprovePage(Page):
    title = "Mejorar kit"
    subtitle = "Procesado por pieza, balance, afinación, capas de velocidad y memoria según tu teclado."

    def __init__(self, ctx):
        super().__init__(ctx)
        self.result = None
        self.filas = []
        root = vbox(self, 0, 14)
        top = hbox(None, 0, 14)
        root.addLayout(top)
        # modelo
        c1 = card()
        l1 = vbox(c1, 16, 8)
        l1.addWidget(caption("Teclado destino"))
        self.modelo = QComboBox()
        self.modelo.addItems(list(modelos.MODELOS))
        self.modelo.currentIndexChanged.connect(self._model_info)
        l1.addWidget(self.modelo)
        self.model_lab = QLabel()
        self.model_lab.setObjectName("Mut")
        self.model_lab.setWordWrap(True)
        l1.addWidget(self.model_lab)
        l1.addStretch(1)
        top.addWidget(c1, 2)
        # opciones
        c2 = card()
        g = QGridLayout(c2)
        g.setContentsMargins(16, 16, 16, 16)
        g.setVerticalSpacing(10)
        g.addWidget(caption("Qué mejorar"), 0, 0, 1, 2)
        self.chk = {}
        for i, (k, t) in enumerate((("correcciones", "Limpieza (DC, clics, silencio final)"),
                                    ("procesado", "Procesado por pieza (EQ, ataque, compresión)"),
                                    ("balance", "Balance del kit"), ("afinar_toms", "Afinar toms y bombos repetidos"),
                                    ("hihat", "Hi-hat: el cerrado corta al abierto"), ("abrir_filtro", "Abrir el filtro de la voz"))):
            cb = QCheckBox(t)
            cb.setChecked(True)
            self.chk[k] = cb
            g.addWidget(cb, 1 + i % 3, i // 3)
        top.addWidget(c2, 4)
        # intensidad
        c3 = card()
        l3 = vbox(c3, 16, 8)
        row = hbox(None, 0, 6)
        row.addWidget(caption("Intensidad"))
        row.addStretch(1)
        self.int_lab = QLabel("100 %")
        self.int_lab.setStyleSheet(f"color:{C['gold']}; font-weight:700")
        row.addWidget(self.int_lab)
        l3.addLayout(row)
        self.inten = slider(0, 150, 100)
        self.inten.valueChanged.connect(lambda v: self.int_lab.setText(f"{v} %"))
        l3.addWidget(self.inten)
        l3.addWidget(caption("Capas de velocidad"))
        self.capas = QComboBox()
        self.capas.addItems(["Auto (según modelo)", "Sin capas", "2 capas", "3 capas"])
        l3.addWidget(self.capas)
        top.addWidget(c3, 2)

        bar = hbox(None, 0, 10)
        self.b_prev = btn("Mejorar (vista previa)", "sparkle", primary=True)
        self.b_prev.clicked.connect(self.preview)
        self.b_save = btn("Guardar .ppf mejorado", "save")
        self.b_save.clicked.connect(self.save)
        self.b_a = btn("Antes", "play")
        self.b_d = btn("Después", "play")
        self.b_a.clicked.connect(lambda: self._play("antes"))
        self.b_d.clicked.connect(lambda: self._play("despues"))
        for b in (self.b_prev, self.b_save, self.b_a, self.b_d):
            bar.addWidget(b)
        bar.addStretch(1)
        self.mem_lab = QLabel("")
        self.mem_lab.setStyleSheet("font-weight:700")
        bar.addWidget(self.mem_lab)
        root.addLayout(bar)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        body = hbox(None, 0, 14)
        root.addLayout(body, 1)
        c4 = card()
        l4 = vbox(c4, 14, 6)
        l4.addWidget(caption("Muestras"))
        self.tbl = table(["Muestra", "Tipo", "Teclas", "Cambios"], [150, 95, 120, None])
        self.tbl.cellDoubleClicked.connect(lambda r, c: self._play("despues"))
        l4.addWidget(self.tbl)
        body.addWidget(c4, 3)
        c5 = card()
        l5 = vbox(c5, 16, 8)
        l5.addWidget(caption("Memoria en la serie S"))
        self.bars = MemoryBars()
        l5.addWidget(self.bars)
        l5.addWidget(caption("Notas"))
        self.notes = text_view(80)
        l5.addWidget(self.notes, 1)
        body.addWidget(c5, 2)
        self._model_info()
        self._set_enabled(False)

    def _set_enabled(self, has_result):
        for b in (self.b_save, self.b_a, self.b_d):
            b.setEnabled(has_result)

    def _model_info(self):
        m = modelos.MODELOS[self.modelo.currentText()]
        self.model_lab.setText(f"Memoria de expansión: <b>{m.memoria_mb:.0f} MB</b><br>Recomendado por kit: ≤ {m.kit_max_mb:.0f} MB<br>{m.nota}")

    def load(self, pack):
        self.result = None
        self.filas = []
        self.tbl.setRowCount(0)
        self._set_enabled(False)
        self.mem_lab.setText("")
        mb = A_mb(pack)
        self.bars.set_rows([(n, mb, modelos.MODELOS[n].memoria_mb, st) for n, st, _ in modelos.compatibilidad(mb)])
        self.notes.setHtml(f"<p style='color:{C['mut']}'>Elige el teclado destino y pulsa «Mejorar». "
                           "Nada se guarda hasta que pulses «Guardar».</p>")

    def _opts(self):
        return Mj.OpcionesMejora(modelo=self.modelo.currentText(), intensidad=self.inten.value() / 100,
                                 capas=["auto", "0", "2", "3"][self.capas.currentIndex()],
                                 **{k: cb.isChecked() for k, cb in self.chk.items()})

    def preview(self):
        src = self.ctx.pack
        if src is None:
            return
        op = self._opts()
        self.b_prev.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)

        def job():
            pack = copy.deepcopy(src)
            filas, avisos, mb0, mb1 = Mj.mejorar(pack, op)
            return pack, filas, avisos, mb0, mb1, op

        def done(res):
            self.progress.setVisible(False)
            self.b_prev.setEnabled(True)
            self.result = res
            pack, filas, avisos, mb0, mb1, op = res
            self.filas = filas
            self.tbl.setRowCount(0)
            for f in filas:
                i = self.tbl.rowCount()
                self.tbl.insertRow(i)
                self.tbl.setItem(i, 0, cell(f.nombre, bold=True))
                self.tbl.setItem(i, 1, cell(Mj.NOMBRE_TIPO[f.tipo], "gold"))
                self.tbl.setItem(i, 2, cell(", ".join(note_name(n) for n in f.notas), "mut"))
                it = cell(" · ".join(f.cambios), "mut")
                it.setToolTip("\n".join(f.cambios))
                self.tbl.setItem(i, 3, it)
            if filas:
                self.tbl.selectRow(0)
            m = modelos.MODELOS[op.modelo]
            col = C["OK"] if mb1 <= m.kit_max_mb else C["AVISO"] if mb1 <= m.memoria_mb else C["ERROR"]
            self.mem_lab.setText(f"<span style='color:{col}'>Audio: {mb0:.2f} → {mb1:.2f} MB · {mb1 / m.memoria_mb * 100:.1f} % del {m.nombre}</span>")
            self.bars.set_rows([(n, mb1, modelos.MODELOS[n].memoria_mb, st) for n, st, _ in modelos.compatibilidad(mb1)])
            self.notes.setHtml(problems_html([type("P", (), dict(level="INFO", text=a))() for a in avisos], "Sin notas.") +
                               f"<p style='color:{C['mut']}; margin-top:10px'>Selecciona una muestra y compara Antes / Después. "
                               "Luego guarda y escúchalo en «Escuchar» (simulación o PSR real).</p>")
            self._set_enabled(True)
            self.ctx.toast("Vista previa lista — aún no se ha guardado nada", "INFO")

        def err():
            self.progress.setVisible(False)
            self.b_prev.setEnabled(True)

        self.ctx.run_bg(job, done, err)

    def _play(self, which):
        r = self.tbl.currentRow()
        if not (0 <= r < len(self.filas)):
            return
        f = self.filas[r]
        x = f.antes if which == "antes" else f.despues
        if x is None:
            return
        x = x if x.shape[1] == 2 else np.repeat(x, 2, axis=1)
        self.ctx.audio.play(x.astype(np.float32))

    def save(self):
        if not self.result:
            return
        pack, *_rest, op = self.result
        src = self.ctx.pack.path
        mod = op.modelo.replace("PSR-", "")
        out, _ = QFileDialog.getSaveFileName(self, "Guardar pack mejorado",
                                             os.path.join(os.path.dirname(src), os.path.splitext(os.path.basename(src))[0] + f"_PRO_{mod}.ppf"),
                                             "Yamaha Expansion Manager (*.ppf)")
        if not out:
            return
        if os.path.abspath(out) == os.path.abspath(src):
            self.ctx.toast("Por seguridad no se sobrescribe el archivo original.", "AVISO")
            return
        pack.path = out
        pack.save(out)
        chk = load_pack(out)
        if chk.errors:
            QMessageBox.warning(self, "PPF Tester", "El archivo guardado no pasó la verificación:\n" + "\n".join(chk.errors))
            return
        self.ctx.add_recent(out)
        if QMessageBox.question(self, "PPF Tester", f"Guardado: {os.path.basename(out)}\n\n¿Abrirlo ahora para escucharlo?\n\n"
                                "Ábrelo también en Yamaha Expansion Manager antes de instalarlo en el teclado.") == QMessageBox.StandardButton.Yes:
            self.ctx.open_file(out)
        else:
            self.ctx.toast(f"Guardado: {os.path.basename(out)}", "OK")


def A_mb(pack) -> float:
    return sum(w.frames * w.channels * 2 for w in pack.waves.values()) / 1e6
