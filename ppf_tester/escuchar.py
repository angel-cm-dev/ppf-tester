"""Pestaña "Escuchar como en el teclado": toca el kit con el ratón o el teclado
del PC, con la simulación del PSR, con el PSR real por MIDI, o con la muestra
original, y compara A/B lo que suena en el teclado con la simulación.
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np

import motor as M
from ppf_format import note_name

KEYS = list("asdfghjklñ") + list("qwertyuiop") + list("zxcvbnm")


class ListenTab(ttk.Frame):
    def __init__(self, parent, app, T, FONT, Piano, text_widget):
        super().__init__(parent, style="Panel.TFrame")
        self.app, self.T, self.FONT = app, T, FONT
        self.engine: M.Engine | None = None
        self.mixer: M.Mixer | None = None
        self.live: M.LiveInput | None = None
        self.midi = None
        self.midi_port = None
        self.keymap: dict[str, int] = {}
        self.held: set[str] = set()
        self.last = None                    # dict con la última nota tocada
        self.recs: dict[tuple[int, int], np.ndarray] = {}

        self.source = tk.StringVar(value="sim")
        self.vel = tk.IntVar(value=100)
        self.vel_by_pos = tk.BooleanVar(value=True)
        self.rev = tk.IntVar(value=0)
        self.use_filter = tk.BooleanVar(value=True)
        self.monitor = tk.BooleanVar(value=False)
        self.record = tk.BooleanVar(value=True)

        ttk.Label(self, text="Toca el kit con el ratón (más abajo en la tecla = más fuerte) o con el teclado del PC "
                             "(letras sobre las teclas; Mayús = acento).", style="Mut.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        self.piano = Piano(self, self._piano_hit)
        self.piano.configure(height=120)
        self.piano.pack(fill="x", padx=12, pady=(0, 10))

        ctl = tk.Frame(self, bg=T["panel"])
        ctl.pack(fill="x", padx=14)
        # fuente
        src = tk.Frame(ctl, bg=T["panel2"], padx=12, pady=8)
        src.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(src, text="QUÉ ESCUCHAR", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).pack(anchor="w")
        for val, txt in (("sim", "Simulación del PSR  (aprox., sin el teclado)"),
                         ("real", "PSR real por MIDI  (sonido exacto)"),
                         ("orig", "Muestra original  (sin procesar)")):
            tk.Radiobutton(src, text=txt, value=val, variable=self.source, bg=T["panel2"], fg=T["fg"],
                           selectcolor=T["panel"], activebackground=T["panel2"], activeforeground=T["accent"],
                           font=(FONT, 10), anchor="w", highlightthickness=0, command=self._source_changed).pack(anchor="w")
        # toque
        tq = tk.Frame(ctl, bg=T["panel2"], padx=12, pady=8)
        tq.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        tk.Label(tq, text="TOQUE", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).pack(anchor="w")
        row = tk.Frame(tq, bg=T["panel2"])
        row.pack(anchor="w", fill="x")
        tk.Label(row, text="Velocidad", bg=T["panel2"], fg=T["fg"], font=(FONT, 10)).pack(side="left")
        self.vel_lab = tk.Label(row, text="100", bg=T["panel2"], fg=T["accent"], font=(FONT, 10, "bold"), width=4)
        self.vel_lab.pack(side="right")
        tk.Scale(tq, from_=1, to=127, orient="horizontal", variable=self.vel, showvalue=False, length=200,
                 bg=T["panel2"], fg=T["fg"], troughcolor=T["panel"], highlightthickness=0, sliderrelief="flat",
                 activebackground=T["accent"], command=lambda v: self.vel_lab.configure(text=str(int(float(v))))).pack(anchor="w")
        ttk.Checkbutton(tq, text="Según dónde pulses la tecla", variable=self.vel_by_pos, style="P2.TCheckbutton").pack(anchor="w")
        # simulacion
        sm = tk.Frame(ctl, bg=T["panel2"], padx=12, pady=8)
        sm.grid(row=0, column=2, sticky="nsew", padx=(0, 8))
        tk.Label(sm, text="SIMULACIÓN", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).pack(anchor="w")
        ttk.Checkbutton(sm, text="Filtro de la voz (paso-bajo del XML)", variable=self.use_filter,
                        style="P2.TCheckbutton", command=self._sim_changed).pack(anchor="w")
        row = tk.Frame(sm, bg=T["panel2"])
        row.pack(anchor="w", fill="x")
        tk.Label(row, text="Reverb (mixer del PSR)", bg=T["panel2"], fg=T["fg"], font=(FONT, 10)).pack(side="left")
        self.rev_lab = tk.Label(row, text="0 %", bg=T["panel2"], fg=T["accent"], font=(FONT, 10, "bold"), width=5)
        self.rev_lab.pack(side="right")
        tk.Scale(sm, from_=0, to=100, orient="horizontal", variable=self.rev, showvalue=False, length=200,
                 bg=T["panel2"], fg=T["fg"], troughcolor=T["panel"], highlightthickness=0, sliderrelief="flat",
                 activebackground=T["accent"], command=self._rev_changed).pack(anchor="w")
        # teclado real
        rl = tk.Frame(ctl, bg=T["panel2"], padx=12, pady=8)
        rl.grid(row=0, column=3, sticky="nsew")
        tk.Label(rl, text="PSR REAL", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).pack(anchor="w")
        ttk.Checkbutton(rl, text="Oír el PSR por el PC (monitor)", variable=self.monitor, style="P2.TCheckbutton",
                        command=self._live_changed).pack(anchor="w")
        ttk.Checkbutton(rl, text="Grabar cada golpe para comparar", variable=self.record, style="P2.TCheckbutton",
                        command=self._live_changed).pack(anchor="w")
        tk.Label(rl, text="Nivel de entrada", bg=T["panel2"], fg=T["mut"], font=(FONT, 8)).pack(anchor="w", pady=(4, 0))
        self.meter = tk.Canvas(rl, height=10, width=200, bg=T["panel"], highlightthickness=0)
        self.meter.pack(anchor="w")
        tk.Label(rl, text="Puerto MIDI y entrada: pestaña «Prueba en el teclado»", bg=T["panel2"], fg=T["mut"],
                 font=(FONT, 8)).pack(anchor="w")
        for c in range(4):
            ctl.columnconfigure(c, weight=1)

        # ritmos
        gr = tk.Frame(self, bg=T["panel"])
        gr.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(gr, text="RITMO DE PRUEBA", bg=T["panel"], fg=T["mut"], font=(FONT, 8, "bold")).pack(side="left", padx=(0, 10))
        import grooves as G
        self.G = G
        self.groove = ttk.Combobox(gr, state="readonly", values=list(G.PATRONES), width=22)
        self.groove.current(0)
        self.groove.pack(side="left")
        tk.Label(gr, text="BPM", bg=T["panel"], fg=T["fg"], font=(FONT, 10)).pack(side="left", padx=(12, 4))
        self.bpm = ttk.Spinbox(gr, from_=40, to=220, width=5)
        self.bpm.set(76)
        self.bpm.pack(side="left")
        self.b_groove = ttk.Button(gr, text="▶  Tocar ritmo", style="Accent.TButton", command=self.toggle_groove)
        self.b_groove.pack(side="left", padx=10)
        tk.Label(gr, text="Suena con la fuente elegida arriba (simulación, PSR real u original).", bg=T["panel"],
                 fg=T["mut"], font=(FONT, 9)).pack(side="left")
        self.player = None

        # A/B
        ab = tk.Frame(self, bg=T["panel"])
        ab.pack(fill="both", expand=True, padx=14, pady=10)
        ab.columnconfigure(0, weight=3)
        ab.columnconfigure(1, weight=2)
        ab.rowconfigure(2, weight=1)
        self.ab_title = tk.Label(ab, text="Comparación A/B — toca una nota", bg=T["panel"], fg=T["fg"],
                                 font=(FONT, 11, "bold"), anchor="w")
        self.ab_title.grid(row=0, column=0, columnspan=2, sticky="w")
        bar = tk.Frame(ab, bg=T["panel"])
        bar.grid(row=1, column=0, columnspan=2, sticky="w", pady=6)
        self.b_orig = ttk.Button(bar, text="▶  Original", command=lambda: self._ab("orig"), state="disabled")
        self.b_sim = ttk.Button(bar, text="▶  Simulación", command=lambda: self._ab("sim"), state="disabled")
        self.b_rec = ttk.Button(bar, text="▶  Grabación del PSR", style="Accent.TButton", command=lambda: self._ab("rec"), state="disabled")
        for b in (self.b_orig, self.b_sim, self.b_rec):
            b.pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="■  Parar", command=self.stop).pack(side="left")
        self.wave = tk.Canvas(ab, bg=T["panel2"], highlightthickness=0, height=150)
        self.wave.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        self.wave.bind("<Configure>", lambda e: self._draw_ab())
        self.info = text_widget(ab, 8)
        self.info.grid(row=2, column=1, sticky="nsew")
        self.after(80, self._tick)

    # ---------------------------------------------------------------- setup
    def load(self, pack):
        if getattr(self, "player", None) is not None:
            self.toggle_groove()
        self.stop()
        self.recs.clear()
        self.last = None
        if not pack.voices:
            self.engine = None
            return
        self.engine = M.Engine(pack, pack.voices[0])
        self.engine.settings.use_filter = self.use_filter.get()
        r = round(self.engine.common["reverb"] / 127 * 100)
        self.rev.set(r)
        self.rev_lab.configure(text=f"{r} %")
        self._rev_changed(r)
        notes = sorted({n for _, _, lo, hi, _, _ in pack.voices[0].zones() for n in range(lo, min(hi, lo + 60) + 1)})
        self.keymap = {k: n for k, n in zip(KEYS, notes)}
        self.piano.labels = {n: k.upper() for k, n in self.keymap.items()}
        self.piano.set_keys({n: "OK" for n in notes})
        threading.Thread(target=lambda: M._reverb_ir(M.SR, 0.8), daemon=True).start()   # precalcular
        self._draw_ab()

    def _ensure_mixer(self):
        if self.mixer is None:
            self.mixer = M.Mixer()
        return self.mixer

    def _in_dev(self):
        s = self.app.cb_in.get()
        return int(s.split("]")[0].strip("[")) if s.startswith("[") else None

    def _ensure_live(self):
        if self.live is None:
            dev = self._in_dev()
            if dev is None:
                raise RuntimeError("Elige la entrada de audio del teclado en la pestaña «Prueba en el teclado».")
            self.live = M.LiveInput(dev, monitor=self.monitor.get())
        self.live.monitor = self.monitor.get()
        return self.live

    def _ensure_midi(self):
        import midi_test
        s = self.app.cb_midi.get()
        if not s.startswith("["):
            raise RuntimeError("Elige la salida MIDI del PSR en la pestaña «Prueba en el teclado».")
        port = int(s.split("]")[0].strip("["))
        if self.midi is None or self.midi_port != port:
            if self.midi:
                self.midi.close()
            self.midi = midi_test.MidiOut(port)
            self.midi_port = port
        return self.midi

    def _live_changed(self):
        try:
            if self.monitor.get() or (self.record.get() and self.source.get() == "real"):
                self._ensure_live()
            elif self.live is not None:
                self.live.close()
                self.live = None
        except Exception as e:  # noqa: BLE001
            self.monitor.set(False)
            messagebox.showerror("PPF Tester", f"No se pudo abrir la entrada de audio:\n{e}")

    def _source_changed(self):
        if self.source.get() == "real":
            try:
                self._ensure_midi()
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("PPF Tester", str(e))
                self.source.set("sim")
                return
        self._live_changed()

    def _sim_changed(self):
        if self.engine:
            self.engine.settings.use_filter = self.use_filter.get()
            self.engine.invalidate()

    def _rev_changed(self, v):
        v = int(float(v))
        self.rev_lab.configure(text=f"{v} %")
        if self.engine:
            self.engine.settings.reverb = v / 100
            self.engine.invalidate()

    # ---------------------------------------------------------------- tocar
    def _piano_hit(self, n):
        frac = getattr(self.piano, "last_frac", 0.7)
        vel = int(np.clip(20 + frac * 120, 1, 127)) if self.vel_by_pos.get() else self.vel.get()
        if self.vel_by_pos.get():
            self.vel.set(vel)
            self.vel_lab.configure(text=str(vel))
        self.hit(n, vel)

    def key_press(self, e):
        ch = (e.char or "").lower()
        if ch not in self.keymap or ch in self.held:
            return False
        self.held.add(ch)
        vel = 127 if e.state & 0x1 else self.vel.get()
        self.hit(self.keymap[ch], vel)
        return True

    def key_release(self, e):
        self.held.discard((e.char or "").lower())

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
        src = self.source.get()
        orig, dur = self._orig(n, vel)
        if orig is None:
            return
        sim, group = self.engine.render(n, vel)
        self.last = dict(note=n, vel=vel, orig=orig, sim=sim, rec=self.recs.get((n, vel)), cmp=None)
        try:
            if src == "sim":
                self._ensure_mixer().play(sim, group, n)
            elif src == "orig":
                self._ensure_mixer().play(orig, 0, n)
            else:
                self._play_real(n, vel, max(0.3, min(dur, 4.0)))
        except Exception as e:  # noqa: BLE001
            self.app.set_status(f"Error de audio/MIDI: {e}")
        self._update_ab()

    def _play_real(self, n, vel, dur):
        midi = self._ensure_midi()
        ch = int(self.app.sp_ch.get())
        live = None
        if self.record.get():
            live = self._ensure_live()
            start = live.now() - int(0.05 * live.rate)
        midi.note(ch, n, vel)
        self.after(int(dur * 1000), lambda: midi.off(ch, n))
        if live is not None:
            def grab():
                rec = live.get(start, live.now())
                if len(rec):
                    self.recs[(n, vel)] = rec
                    if self.last and self.last["note"] == n and self.last["vel"] == vel:
                        self.last["rec"] = rec
                        self.last["cmp"] = None
                        self._update_ab()
            self.after(int((dur + 0.5) * 1000), grab)

    def _ab(self, which):
        if not self.last:
            return
        x = self.last.get(which)
        if x is None:
            return
        if which == "rec" and self.live is not None and self.monitor.get():
            self.app.set_status("Consejo: apaga el monitor para que no se mezcle con la grabación.")
        self._ensure_mixer().play(x.astype(np.float32), 0, -1)

    def stop(self):
        if self.mixer:
            self.mixer.stop()
        if self.midi:
            try:
                self.midi.all_off(int(self.app.sp_ch.get()))
            except Exception:  # noqa: BLE001
                pass

    # ---------------------------------------------------------------- ritmos
    def toggle_groove(self):
        if self.player is not None:
            self.player.stop()
            self.player = None
            self.b_groove.configure(text="▶  Tocar ritmo")
            return
        if not self.engine:
            return
        src = self.source.get()
        disp = set(self.keymap.values())
        try:
            if src == "real":
                midi = self._ensure_midi()
                ch = int(self.app.sp_ch.get())

                def tocar(n, v):
                    midi.note(ch, n, v)
                    threading.Timer(0.08, lambda: midi.off(ch, n)).start()
            else:
                mixer = self._ensure_mixer()
                if src == "sim":   # pre-renderizar para que el hilo no tenga que calcular
                    for st, n, v in self.G.PATRONES[self.groove.get()][2]:
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
                        mixer.play(buf, g, n)
            self.player = self.G.Reproductor(tocar, disp)
            self.player.start(self.groove.get(), float(self.bpm.get()))
            self.b_groove.configure(text="■  Parar ritmo")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("PPF Tester", str(e))

    # ---------------------------------------------------------------- A/B
    def _update_ab(self):
        L = self.last
        if not L:
            return
        T = self.T
        self.ab_title.configure(text=f"Comparación A/B — {note_name(L['note'])} (MIDI {L['note']}) · velocidad {L['vel']}")
        self.b_orig.configure(state="normal")
        self.b_sim.configure(state="normal")
        self.b_rec.configure(state="normal" if L.get("rec") is not None else "disabled")
        t = self.info
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", "Parámetros de la voz para esta nota\n", "mut")
        for line in self.engine.describe(L["note"]):
            t.insert("end", "• " + line + "\n")
        vel_db = None
        for el, _ in self.engine.zones_for(L["note"], L["vel"]):
            vel_db = self.engine.velocity_db(self.engine.sound[el.number], L["vel"])
        if vel_db is not None:
            t.insert("end", f"• Curva de velocidad: {vel_db:+.1f} dB a velocidad {L['vel']}\n")
        rec = L.get("rec")
        if rec is not None:
            if np.abs(rec).max() < 10 ** (-55 / 20):
                t.insert("end", "\nERROR  ", "ERROR")
                t.insert("end", "No llegó sonido del PSR. Revisa que la voz esté en RIGHT 1, el canal MIDI y el cable de audio.\n")
            else:
                c = M.compare(L["sim"], rec)
                o = M.compare(L["orig"], rec)
                L["cmp"] = c
                t.insert("end", "\nLo que suena en el PSR\n", "mut")
                self._verdict(t, o["brillo_pct"], "frente a la muestra original")
                self._verdict(t, c["brillo_pct"], "frente a la simulación")
                if c["dur_rec"] < c["dur_sim"] * 0.75 and c["dur_sim"] > 0.3:
                    t.insert("end", "AVISO  ", "AVISO")
                    t.insert("end", f"En el PSR la nota se apaga antes ({c['dur_rec']:.2f} s frente a {c['dur_sim']:.2f} s).\n")
                t.insert("end", f"Duración audible: PSR {c['dur_rec']:.2f} s · simulación {c['dur_sim']:.2f} s\n", "mut")
                t.insert("end", "El volumen absoluto depende de la ganancia de tu interfaz.\n", "mut")
        elif self.source.get() != "real":
            t.insert("end", "\nPara oír y comparar el sonido exacto del PSR, elige «PSR real por MIDI» con «Grabar cada golpe».\n", "mut")
        t.configure(state="disabled")
        self._draw_ab()

    def _verdict(self, t, pct, ref):
        if pct < -15:
            t.insert("end", "AVISO  ", "AVISO")
            t.insert("end", f"Suena {abs(pct):.0f} % más opaco {ref}. Si no quieres perder brillo, "
                            "sube el corte del filtro (Cutoff) de la nota en Expansion Manager.\n")
        elif pct > 15:
            t.insert("end", "INFO   ", "INFO")
            t.insert("end", f"Suena {pct:.0f} % más brillante {ref} (EQ del teclado o altavoces).\n")
        else:
            t.insert("end", "OK     ", "OK")
            t.insert("end", f"Mismo brillo {ref} ({pct:+.0f} %).\n")

    def _draw_ab(self):
        c = self.wave
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        T = self.T
        if w < 20:
            return
        if not self.last:
            c.create_text(w / 2, h / 2, text="Toca una nota para ver original, simulación y PSR", fill=T["mut"], font=(self.FONT, 10))
            return
        L = self.last
        series = [("orig", T["mut"], "Original"), ("sim", T["accent"], "Simulación"), ("rec", T["INFO"], "PSR grabado")]
        datas = {k: M.align_onset(L[k]) for k, _, _ in series if L.get(k) is not None}
        n = max(len(x) for x in datas.values())
        n = min(n, M.SR * 4)
        mid = h / 2
        for k, col, lab in series:
            x = datas.get(k)
            if x is None:
                continue
            m = np.abs(x[:n]).max(axis=1)
            m = m / max(m.max(), 1e-9)      # normalizado: compara forma, no nivel
            edges = np.linspace(0, len(m), max(2, int(w * len(m) / n)) + 1).astype(int)
            pk = np.maximum.reduceat(m, edges[:-1]) if len(m) >= len(edges) else m
            pts = []
            for i, v in enumerate(pk):
                pts += [i * w * len(m) / n / len(pk), mid - v * (mid - 10)]
            if len(pts) >= 4:
                c.create_line(*pts, fill=col, width=2 if k != "orig" else 1)
                pts2 = []
                for i, v in enumerate(pk):
                    pts2 += [i * w * len(m) / n / len(pk), mid + v * (mid - 10)]
                c.create_line(*pts2, fill=col, width=2 if k != "orig" else 1)
        x0 = 10
        for k, col, lab in series:
            if k in datas:
                c.create_rectangle(x0, 8, x0 + 10, 18, fill=col, outline="")
                c.create_text(x0 + 14, 13, text=lab, fill=T["fg"], anchor="w", font=(self.FONT, 8))
                x0 += 110
        c.create_text(w - 8, h - 8, text=f"{n / M.SR:.1f} s · envolvente normalizada", fill=T["mut"], anchor="e", font=(self.FONT, 8))

    def _tick(self):
        lv = self.live.level if self.live is not None else 0.0
        self.meter.delete("all")
        wdt = int(self.meter.winfo_width() or 200)
        db = 20 * np.log10(max(lv, 1e-6))
        frac = np.clip((db + 60) / 60, 0, 1)
        col = self.T["OK"] if db < -6 else (self.T["AVISO"] if db < -1 else self.T["ERROR"])
        self.meter.create_rectangle(0, 0, frac * wdt, 10, fill=col, outline="")
        self.after(80, self._tick)

    def close(self):
        if self.player is not None:
            self.player.stop()
        for obj in (self.mixer, self.live):
            if obj is not None:
                obj.close()
        if self.midi is not None:
            try:
                self.midi.close()
            except Exception:  # noqa: BLE001
                pass
